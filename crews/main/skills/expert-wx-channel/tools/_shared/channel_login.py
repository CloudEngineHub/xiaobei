"""Shared, screenshot-verified login for the managed wechat-channel session."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from urllib.parse import urlsplit

SESSION = "wechat-channel"
HOME_URL = "https://channels.weixin.qq.com/platform/home"
BACKEND_PATHS = ("/platform/home", "/platform/post", "/platform/data", "/platform/interaction", "/platform/live")
RUNTIME_HOME = Path(os.environ.get("XIAOBEI_BROWSER_HOME", "~/.camoufox-cli")).expanduser()
STATE_FILE = RUNTIME_HOME / "login" / "wechat-channel.json"

# Intersect every clipping ancestor: innerText and the node's own computed style
# alone can report a refresh message that is outside an overflow:hidden region.
PAGE_PROBE = r"""(() => {
  const rect = e => {
    let b=e.getBoundingClientRect(), x=Math.max(0,b.left), y=Math.max(0,b.top),
      right=Math.min(innerWidth,b.right), bottom=Math.min(innerHeight,b.bottom);
    for(let p=e;p;p=p.parentElement) {
      const s=getComputedStyle(p);
      if(s.display==='none'||s.visibility==='hidden'||s.visibility==='collapse'||Number(s.opacity)===0) return null;
      if(p!==e) {
        const r=p.getBoundingClientRect();
        if(/hidden|clip|scroll|auto/.test(s.overflowX)) {x=Math.max(x,r.left);right=Math.min(right,r.right);}
        if(/hidden|clip|scroll|auto/.test(s.overflowY)) {y=Math.max(y,r.top);bottom=Math.min(bottom,r.bottom);}
      }
    }
    return right>x&&bottom>y ? {x,y,width:right-x,height:bottom-y} : null;
  };
  const regions=[];
  for(const frame of document.querySelectorAll('iframe')) {
    const a=document.createElement('a');a.href=frame.src;
    const r=rect(frame);
    if(a.protocol==='https:'&&a.hostname==='open.weixin.qq.com'&&a.pathname==='/connect/qrconnect'&&r) regions.push(r);
  }
  for(const image of document.images) {
    const r=rect(image);
    if(image.complete&&image.naturalWidth>=100&&r&&r.width>=100&&r.height>=100) regions.push(r);
  }
  const errors=[...document.querySelectorAll('p,span,div')].filter(e=>e.children.length===0&&/加载失败|二维码.*失效|二维码.*过期/.test(e.textContent||'')&&rect(e)).map(e=>(e.textContent||'').trim().slice(0,120)).slice(0,5);
  const app=document.querySelector('wujie-app');
  const body=app?.shadowRoot?.querySelector('body');
  const text=body?.innerText||'';
  const backendContent=!!body&&!!rect(app)&&(/作品管理|视频管理|发表视频|发表动态/.test(text)||!!body.querySelector('[data-placeholder="添加描述"]'));
  return {url:location.href,regions,errors,backendContent,viewport:{width:innerWidth,height:innerHeight}};
})()"""


class LoginError(RuntimeError):
    def __init__(self, code, message, exit_code=1, **details):
        super().__init__(message)
        self.code, self.exit_code, self.details = code, exit_code, details


def backend_url(url):
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == "https" and parsed.netloc == "channels.weixin.qq.com"
                and "login" not in parsed.path.lower()
                and (parsed.path.rstrip("/") == "/platform" or any(
                    parsed.path == p or parsed.path.startswith(p + "/") for p in BACKEND_PATHS)))
    except ValueError:
        return False


def backend_ready(probe):
    return isinstance(probe, dict) and backend_url(probe.get("url", "")) and probe.get("backendContent") is True


def login_page(url):
    parsed = urlsplit(url)
    return parsed.scheme == "https" and parsed.netloc == "channels.weixin.qq.com" and parsed.path in ("/login.html", "/platform/login")


def verify_qr(path, probe):
    """Decode only the visible login region; never return or persist the QR token."""
    if not login_page(probe.get("url", "")):
        return False
    try:
        import cv2
    except ImportError as exc:
        raise LoginError("QR_DECODER_MISSING", "缺少仓根 requirements.txt 中的 OpenCV 依赖") from exc
    image = cv2.imread(str(path))
    viewport = probe.get("viewport", {})
    width, height = viewport.get("width", 0), viewport.get("height", 0)
    if image is None or width <= 0 or height <= 0:
        return False
    scale_x, scale_y = image.shape[1] / width, image.shape[0] / height
    detector = cv2.QRCodeDetector()
    for region in probe.get("regions", [])[:10]:
        x, y = max(0, math.floor(region["x"] * scale_x)), max(0, math.floor(region["y"] * scale_y))
        right = min(image.shape[1], math.ceil((region["x"] + region["width"]) * scale_x))
        bottom = min(image.shape[0], math.ceil((region["y"] + region["height"]) * scale_y))
        if right <= x or bottom <= y:
            continue
        try:
            value, _, _ = detector.detectAndDecode(image[y:bottom, x:right])
        except cv2.error:
            continue
        if value:
            parsed = urlsplit(value)
            if parsed.scheme == "https" and parsed.netloc == "open.weixin.qq.com" and parsed.path.startswith("/connect/"):
                return True
    return False


class Browser:
    def __init__(self):
        self.token = None
        self.generation = None
        self.waiting = False
        self.owned = False
        self.tab_id = None

    def command(self, *args):
        command = [os.environ.get("CAMOUFOX_CLI", "camoufox-cli"), "--session", SESSION, "--persistent", "--json"]
        if self.token:
            command += ["--lease-token", self.token]
        result = subprocess.run(command + list(args), text=True, capture_output=True, timeout=35)
        try:
            envelope = json.loads(result.stdout)
        except ValueError as exc:
            raise LoginError("BROWSER_RESPONSE_INVALID", "受管浏览器未返回有效 JSON") from exc
        if result.returncode or envelope.get("success") is False or envelope.get("ok") is False:
            # Do not echo IPC authorization or raw page/token data in errors.
            raise LoginError("SESSION_BUSY" if result.returncode == 4 else "BROWSER_COMMAND_FAILED",
                             "受管浏览器命令失败；保留原会话，检查是否被其他任务占用", 3 if result.returncode == 4 else 1)
        data = envelope.get("data", envelope)
        return data.get("result", data) if isinstance(data, dict) else data

    def probe(self):
        probe = self.command("eval", PAGE_PROBE)
        if not isinstance(probe, dict):
            raise LoginError("PAGE_PROBE_INVALID", "登录页面检查结果无效")
        return probe

    def acquire(self, *, confirm=False, refresh=False):
        status = self.command("status")
        pending = None
        if STATE_FILE.exists():
            if STATE_FILE.is_symlink() or STATE_FILE.stat().st_mode & 0o077:
                raise LoginError("LOGIN_STATE_INVALID", "登录续接文件权限异常，保留会话交 IT 核查")
            pending = json.loads(STATE_FILE.read_text("utf-8"))
            if not isinstance(pending, dict) or pending.get("session") != SESSION or not pending.get("leaseToken"):
                raise LoginError("LOGIN_STATE_INVALID", "登录续接文件无效，保留会话交 IT 核查")
            if not status.get("running") or status.get("generation") != pending.get("generation"):
                if confirm:
                    raise LoginError("LOGIN_SESSION_LOST", "原扫码页面已关闭，请重新执行 login 获取二维码", 2)
                STATE_FILE.unlink()
                pending = None
        if pending:
            self.token = pending["leaseToken"]
            self.generation = pending["generation"]
            self.command("lease", "renew")
            self.owned = True
            tabs = self.command("tabs")["tabs"]
            active = next((t for t in tabs if t.get("active")), {})
            self.tab_id = active.get("tabId")
            if self.tab_id != pending.get("tabId"):
                self.command("lease", "wait")
                self.waiting = True
                raise LoginError("LOGIN_TAB_CHANGED", "原扫码标签已切换或关闭，保留会话交 IT 核查", 2)
            if not confirm and not refresh:
                self.command("lease", "wait")
                self.waiting = True
                raise LoginError("LOGIN_PENDING", "已有二维码等待扫码，请先执行 login-confirm；不自动刷新原二维码", 2)
            if refresh:
                self.command("open", HOME_URL)
        else:
            if not status.get("running"):
                if confirm:
                    raise LoginError("LOGIN_SESSION_LOST", "扫码会话未运行，请先执行 login", 2)
                self.command("open", HOME_URL)
                status = self.command("status")
                opened = True
            else:
                opened = False
            self.generation = status["generation"]
            self.token = self.command("lease", "acquire")["leaseToken"]
            self.owned = True
            if not confirm and not opened:
                self.command("open", HOME_URL)
            tabs = self.command("tabs")["tabs"]
            self.tab_id = next((t.get("tabId") for t in tabs if t.get("active")), None)
            if not self.tab_id:
                raise LoginError("LOGIN_TAB_MISSING", "当前登录标签不可用", 2)

    def wait(self):
        STATE_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=STATE_FILE.parent, prefix=".wechat-channel-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"session": SESSION, "generation": self.generation, "leaseToken": self.token, "tabId": self.tab_id}, handle)
            os.replace(temporary, STATE_FILE)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        self.command("lease", "wait")
        self.waiting = True

    def finish(self, *, close=False):
        if self.owned and not self.waiting:
            try:
                self.command("close" if close else "lease", *([] if close else ["release"]))
            finally:
                self.token = None
                self.owned = False
            STATE_FILE.unlink(missing_ok=True)


def login(*, reset=False, refresh=False, qr_dir=None, timeout=15):
    browser = Browser()
    try:
        # Reset remains explicit; never delete a profile while another task owns it.
        if reset:
            status = browser.command("status")
            if status.get("running"):
                browser.acquire(confirm=True)
                browser.finish(close=True)
            elif status.get("state") not in ("stopped", "stale"):
                raise LoginError("SESSION_BUSY", "会话状态不明，不能重置 profile", 3)
            STATE_FILE.unlink(missing_ok=True)
            shutil.rmtree(RUNTIME_HOME / "profiles" / SESSION, ignore_errors=True)
            browser = Browser()
        browser.acquire(refresh=refresh)
        directory = Path(qr_dir or os.environ.get("WX_CHANNEL_QR_DIR", Path.cwd() / "wx_channel" / "login")).expanduser().resolve()
        directory.mkdir(parents=True, exist_ok=True)
        fd, filename = tempfile.mkstemp(prefix="login-", suffix=".png", dir=directory)
        os.close(fd)
        path = Path(filename)
        deadline = time.monotonic() + timeout
        last = {}
        while time.monotonic() < deadline:
            last = browser.probe()
            if backend_ready(last):
                path.unlink(missing_ok=True)
                browser.finish(close=True)
                return {"ok": True, "already_logged_in": True, "message": "登录态有效，无需扫码"}
            if last.get("regions"):
                browser.command("screenshot", str(path))
                # A visible error wins over even a still-decodable stale image.
                after = browser.probe()
                if (after.get("url") == last.get("url") and after.get("regions") == last.get("regions")
                        and not last.get("errors") and not after.get("errors") and verify_qr(path, last)):
                    browser.wait()
                    return {"ok": True, "state": "awaiting_scan", "qr_verified": True, "qr_path": str(path),
                            "message": "已验证标准页面内的微信登录二维码，请扫码并确认后执行 login-confirm"}
            time.sleep(0.5)
        browser.command("screenshot", str(path))
        raise LoginError("QR_NOT_READY", "未验证到可解码的微信二维码；保留原页，不发送诊断图作为二维码", 2,
                         diagnostic_path=str(path), visible_errors=last.get("errors", []))
    finally:
        browser.finish()


def login_confirm(*, keep_open=False, timeout=30):
    browser = Browser()
    try:
        browser.acquire(confirm=True)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            probe = browser.probe()
            if backend_ready(probe):
                browser.finish(close=not keep_open)
                return {"ok": True, "state": "logged_in", "message": "已核验视频号后台内容，登录态就位"}
            time.sleep(0.5)
        browser.wait()
        raise LoginError("LOGIN_NOT_CONFIRMED", "登录尚未就位；请在微信确认登录，再执行 login-confirm，保留原二维码页", 2)
    finally:
        browser.finish()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p_login = sub.add_parser("login")
    mode = p_login.add_mutually_exclusive_group()
    mode.add_argument("--reset", action="store_true")
    mode.add_argument("--refresh", action="store_true", help="显式换码，保留同一 profile")
    sub.add_parser("login-confirm").add_argument("--keep-open", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = login(reset=args.reset, refresh=args.refresh) if args.command == "login" else login_confirm(keep_open=args.keep_open)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except LoginError as exc:
        print(json.dumps({"ok": False, "error": exc.code, "message": str(exc), **exc.details}, ensure_ascii=False))
        return exc.exit_code
    except (OSError, ValueError, subprocess.SubprocessError):
        print(json.dumps({"ok": False, "error": "LOGIN_RUNTIME_ERROR", "message": "登录检查失败，保留原会话交 IT 核查"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
