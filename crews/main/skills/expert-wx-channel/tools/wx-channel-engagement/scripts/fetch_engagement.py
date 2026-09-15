#!/usr/bin/env python3
"""fetch_engagement.py - 微信视频号 engagement 数据抓取

通过 camoufox-cli + 视频号助手后台爬虫拿 wx_channel 视频的播放数 / 点赞数 /
评论数 / 分享数 / 收藏数，写入 published-track 的 pub_wx_channel 表。

与 wx-mp-engagement 同源方法：camoufox 打开创作者后台 → 解析 innerText →
按完整视频描述匹配 → 提行内数字。视频号助手后台使用 wujie 微前端，shadow DOM 内
文本需用 eval 手写 document.querySelector('wujie-app').shadowRoot.innerText。

CLI 形态：
    probe                          打开视频号助手后台 + dump DOM/截图，调试用
    list                           列出后台所有视频 + 行内 metrics
    fetch   --row-id <id>          抓单篇（按 title 在作品管理页匹配）
    fetch-all                      批量刷新（打开首页一次，解析页内全部作品，匹配
                                   pub_wx_channel 全部行写库；不翻页，首页没有的行报 unmatched 跳过）
    login                          camoufox 无头截 QR PNG
    login-confirm                  确认登录 + close session

依赖：
- camoufox-cli（npm 全局）
- published-track skill（同 crew 私有）
- python3 stdlib
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ── 常量 ─────────────────────────────────────────────────────────────────────

PLATFORM = "wx_channel"                          # published-track 表名前缀
SESSION_NAME = "wechat-channel"                  # 与 wechat-channels-publish 共管的 session 名

# 视频号助手后台入口（登录后跳转到这里）
CREATOR_CENTER_URL = os.environ.get(
    "WX_CHANNEL_CREATOR_CENTER_URL", "https://channels.weixin.qq.com/platform/"
)
# 作品管理页（已发布视频 + 行内 engagement 数据）
POST_LIST_URL = os.environ.get(
    "WX_CHANNEL_POST_LIST_URL",
    "https://channels.weixin.qq.com/platform/post/list",
)

PUBLISHED_TRACK_ROOT = Path(
    os.environ.get("PUBLISHED_TRACK_ROOT", "./db")
).expanduser()
PUBLISHED_TRACK_DB = PUBLISHED_TRACK_ROOT / "published_track.db"
PUBLISHED_TRACK_SCRIPTS = Path(
    os.environ.get(
        "PUBLISHED_TRACK_SCRIPTS",
        "~/.openclaw/workspace-main/skills/published-track/scripts",
    )
).expanduser()
UPDATE_METRICS_SH = PUBLISHED_TRACK_SCRIPTS / "update-metrics.sh"

CAMOUFOX_BIN = os.environ.get("CAMOUFOX_CLI", "camoufox-cli")
FETCH_TIMEOUT_S = 30
SESSION_CLEANUP_ON_EXIT = True  # 仅 close camoufox session，不动中央存储

# 视频号助手后台真路径（登录成功后 redirect 落点）；裸 /platform/ 是入口 URL，不算就位
BACKEND_PATHS = (
    "/platform/home", "/platform/post", "/platform/data",
    "/platform/interaction", "/platform/live",
)
# 持久化 profile 目录（登录态落盘位置）
PROFILE_DIR = Path.home() / ".camoufox-cli" / "profiles" / SESSION_NAME

# 登录流程常量（本工具自管 wechat-channel session 的扫码登录）
QR_FILE = "/tmp/qr-wx-channel.png"
# Stop-and-wait 模式（对齐 login-manager）：agent 在对话里等用户「已扫码/已完成」
# 信号后才调 login-confirm；confirm 只做短窗口 settle 验证（吸收扫码确认后
# 可能经一两个中间页才稳定的尾巴），不承担「等用户」职责；不就位 → exit 2 交回对话。
LOGIN_CONFIRM_SETTLE_MAX_S = 30
LOGIN_CONFIRM_POLL_INTERVAL_S = 3

# probe dump 输出目录
PROBE_OUT_DIR = Path(
    os.environ.get("PROBE_OUT_DIR", "./wx-channel-engagement-probe")
).expanduser()


# ── 平台行查询 / 更新 ───────────────────────────────────────────────────────

def lookup_published_row(row_id: int) -> dict | None:
    if not PUBLISHED_TRACK_DB.exists():
        return None
    conn = sqlite3.connect(str(PUBLISHED_TRACK_DB))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            f"SELECT id, title, publish_url, publish_date, source_folder "
            f"FROM pub_{PLATFORM} WHERE id = ?",
            (row_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_all_wx_channel_rows() -> list[int]:
    """取 pub_wx_channel 全部行 id。

    不按日期/指标过滤——作品管理页首页本身就是天然窗口：页内有什么解析什么，
    匹配上的行写库，匹配不上的报 unmatched 跳过（老作品不在首页是常态，非错误）。"""
    if not PUBLISHED_TRACK_DB.exists():
        return []
    conn = sqlite3.connect(str(PUBLISHED_TRACK_DB))
    try:
        cur = conn.execute(
            f"SELECT id FROM pub_{PLATFORM} ORDER BY id DESC",
        )
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def update_metrics_row(row_id: int, metrics: dict) -> dict:
    """调 published-track 的 update-metrics.sh 写库"""
    if not UPDATE_METRICS_SH.exists():
        return {"ok": False, "error": f"update-metrics.sh not found at {UPDATE_METRICS_SH}"}
    cmd = [
        str(UPDATE_METRICS_SH),
        "--platform", PLATFORM,
        "--id", str(row_id),
        "--plays", str(metrics.get("plays", 0)),
        "--likes", str(metrics.get("likes", 0)),
        "--comments", str(metrics.get("comments", 0)),
        "--shares", str(metrics.get("shares", 0)),
        "--favorites", str(metrics.get("favorites", 0)),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
    if result.returncode != 0:
        return {"ok": False, "error": result.stderr.strip(), "stdout": result.stdout.strip()}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"ok": True, "stdout": result.stdout.strip()}


# ── camoufox-cli 集成 ───────────────────────────────────────────────────────
#
# 本工具与 wechat-channels-publish 共管 wechat-channel 持久化 session：
# - 靠 session 名字符串约定共享同一 profile 目录与登录态
# - fail-first 队列串行拒绝（不自动排队、不自动 close 正在跑的 session）
# - 登录态在 wechat-channel session profile 里就位即可，不导出 cookie/UA/token
# ────────────────────────────────────────────────────────────────────────────

def session_name() -> str:
    """返回本工具与 wechat-channels-publish 共管的固定 session 名。"""
    return SESSION_NAME


def camoufox_run(args: list[str], *, timeout: int = FETCH_TIMEOUT_S) -> subprocess.CompletedProcess:
    # --persistent 固定带：所有 camoufox-cli 命令复用同一 daemon + 同一 profile，
    # 避免每次命令重起 daemon 不带 profile（cookie/登录态不恢复）+ 多 daemon
    # 同 session 冲突互杀（SIGKILL）。--persistent 是 per-call flag，必须每次都带。
    cmd = [CAMOUFOX_BIN, "--persistent", "--json"] + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)


def camoufox_open(session: str, url: str) -> None:
    """打开 URL。camoufox-cli 默认 headless，不需要 --headless 参数。"""
    args = ["--session", session, "open", url]
    result = camoufox_run(args)
    if result.returncode != 0:
        raise RuntimeError(f"camoufox-cli open failed: {result.stderr.strip()}")


def camoufox_eval(session: str, expr: str) -> str:
    """在 session 内 eval JS，返回字符串结果"""
    result = camoufox_run(["--session", session, "eval", expr])
    if result.returncode != 0:
        return ""
    try:
        env = json.loads(result.stdout)
        data = env.get("data", "")
        if isinstance(data, dict) and "result" in data:
            # camoufox-cli eval 返回 {data: {result: "..."}}
            return data["result"]
        return data if isinstance(data, str) else json.dumps(data)
    except json.JSONDecodeError:
        return result.stdout


def camoufox_get_url(session: str) -> str:
    """获取当前页面 URL"""
    result = camoufox_run(["--session", session, "url"])
    if result.returncode != 0:
        return ""
    try:
        env = json.loads(result.stdout)
        return env.get("data", {}).get("url", "")
    except json.JSONDecodeError:
        return ""


def camoufox_screenshot(session: str, out_path: Path) -> bool:
    """截图。camoufox-cli 语法：screenshot <file>，不需要 --path。"""
    result = camoufox_run(
        ["--session", session, "screenshot", str(out_path)],
        timeout=FETCH_TIMEOUT_S,
    )
    return result.returncode == 0


def camoufox_close(session: str) -> None:
    """关闭 camoufox session"""
    camoufox_run(["--session", session, "close"], timeout=10)


# ── 登录流程（本工具自管 wechat-channel session）─────────────────────────────
#
# 本工具自己负责 wechat-channel session 的扫码登录 + 验登录就位。
# 登录态在 wechat-channel session profile 里就位即可，不导出 cookie/UA/token。
# 与 wechat-channels-publish 共 session——任一技能登录后另一个不需重登。

def cmd_login(args) -> None:
    """camoufox 无头打开视频号助手后台首页 → 截 QR PNG。

    agent 拿 QR_FILE 发用户扫码，用户回复「已扫码」后调 login-confirm。

    --reset：先 close session + 删 profile 目录再 open，用于上一次扫码污染了
    cookie（如用错账户扫码）后强制从干净状态重来。不加 --reset 时不碰已有
    登录态，避免把还有效的 session 清掉。

    open 后先等 redirect 落点：落到后台路径 = 已登录，直接报 already_logged_in
    不出 QR；落到登录页 = 正常出 QR。
    """
    # --reset：清掉污染的 profile（close daemon + 删磁盘 profile 目录）
    if getattr(args, "reset", False):
        camoufox_close(SESSION_NAME)
        if PROFILE_DIR.exists():
            shutil.rmtree(PROFILE_DIR, ignore_errors=True)

    # camoufox-cli open 视频号助手后台首页
    camoufox_open(SESSION_NAME, CREATOR_CENTER_URL)

    # 等 redirect 落点（最多 8s），区分「已登录」vs「需扫码」
    deadline = time.time() + 8
    current_url = ""
    while time.time() < deadline:
        current_url = camoufox_get_url(SESSION_NAME)
        if current_url and (
            any(p in current_url for p in BACKEND_PATHS)
            or "login" in current_url
            or "scanloginqrcode" in current_url
        ):
            break
        time.sleep(0.5)

    # 已落到后台路径 = 登录态有效，不出 QR
    if current_url and any(p in current_url for p in BACKEND_PATHS):
        camoufox_close(SESSION_NAME)
        sys.stdout.write(json.dumps({
            "ok": True,
            "already_logged_in": True,
            "message": "登录态有效，无需扫码，可直接执行后续命令",
        }, ensure_ascii=False, indent=2))
        sys.stdout.write("\n")
        return

    # 落到登录页 → 等二维码 <img> 出现再截图
    deadline = time.time() + 10
    qr_ready = False
    while time.time() < deadline:
        raw = camoufox_eval(
            SESSION_NAME,
            "(() => { const imgs = document.querySelectorAll('img'); "
            "for (const i of imgs) { if (i.src && i.src.startsWith('data:image')) return '1'; } "
            "return String(imgs.length); })()",
        )
        if raw == "1":
            qr_ready = True
            break
        time.sleep(0.5)
    if not qr_ready:
        # 兜底等固定时间（onload + JS 注入完成），即使 eval 没拿到 QR img
        camoufox_run(
            ["--session", SESSION_NAME, "wait", "3000"],
            timeout=10,
        )

    # screenshot 截 QR PNG
    r = camoufox_run(
        ["--session", SESSION_NAME, "screenshot", QR_FILE],
        timeout=FETCH_TIMEOUT_S,
    )
    if r.returncode != 0:
        sys.stderr.write(f"error: camoufox screenshot failed: {r.stderr.strip()}\n")
        sys.exit(1)

    sys.stdout.write(json.dumps({
        "ok": True,
        "qr_path": QR_FILE,
        "message": "二维码已截，请用微信扫码确认，完成后回复「已扫码」",
    }, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")


def cmd_login_confirm(args) -> None:
    """验登录就位（用户在对话里给信号后调用）→ close session。Stop-and-wait 模式，对齐 login-manager。

    对话层 stop-and-wait：agent 发二维码 PNG 给用户后**停下等用户信号**（「已扫码」/
    「已完成」），收到信号才调本命令。本命令不承担「等用户」职责，只做短窗口
    settle 验证（LOGIN_CONFIRM_SETTLE_MAX_S，吸收扫码确认后可能先跳一两个中间页
    如 /platform/index、/platform/main 才稳定的尾巴），不就位即 exit 2 交回对话，
    不长时间阻塞：
    - 用户只扫了码、还没在手机上点「确认登录」→ 提示用户点确认，再重跑本命令
      （二维码页还活着，无需重新扫码）
    - 已确认仍未就位 / 二维码过期 → 重新调 login 生成新二维码

    不导出 cookie/UA/token——登录态在 wechat-channel session profile 里就位即可。

    就位判定走 url_at_backend（与 _ensure_login 同源）：URL 含真后台路径
    （BACKEND_PATHS）且不含 login；登录页 login.html 也含 /platform/ 段，
    login 检查优先。

    历史：旧实现不读当前页直接轮询 240s，期间 daemon 若被 6 并发上限驱逐或
    手动 close，ensureDaemon 新起 fresh daemon，page 停在 about:blank，
    轮询必超时 → 误判「未就位」（与 wx-mp-engagement 2026-08-16 同根因）。
    现先读 url 分支：仅空/about:blank（fresh daemon）才 ``open`` 后台首页
    触发 redirect；活着的登录页绝不导航走——导航走用户手里的二维码 PNG 作废。
    """
    # 先读当前 url 决定是否 open-first——不盲目导航：
    # - 在登录页 → daemon 活着，二维码页正等用户扫码/确认 → 只轮询不导航
    # - 已就位（真后台路径 / wujie 已渲染）→ 轮询第一轮即判定，不导航
    # - 其余（空/about:blank —— daemon 被驱逐/close，ensureDaemon 新起，
    #   page 没执行过 open）→ 先 open 后台首页触发 redirect 再轮询
    current_url = camoufox_get_url(SESSION_NAME)
    on_login_page = "login" in current_url or "scanloginqrcode" in current_url
    if not on_login_page and not url_at_backend(SESSION_NAME, current_url):
        try:
            camoufox_open(SESSION_NAME, CREATOR_CENTER_URL)
        except RuntimeError as e:
            sys.stderr.write(f"error: camoufox 打开后台首页失败: {e}\n")
            sys.exit(2)

    deadline = time.time() + LOGIN_CONFIRM_SETTLE_MAX_S
    logged_in = False
    stable_url = ""

    while time.time() < deadline:
        current_url = camoufox_get_url(SESSION_NAME)
        if current_url:
            # 显式还在登录页 → 继续等
            if "login" in current_url or "scanloginqrcode" in current_url:
                time.sleep(LOGIN_CONFIRM_POLL_INTERVAL_S)
                continue
            # 跳到后台真路径 = 登录就位（login 检查已在上面 continue 掉）
            if url_at_backend(SESSION_NAME, current_url):
                logged_in = True
                stable_url = current_url
                break
        time.sleep(LOGIN_CONFIRM_POLL_INTERVAL_S)

    if not logged_in:
        # 失败不 close（对齐 login-manager「失败时保留 session」）：daemon + 二维码页
        # 留着，用户在手机上补点「确认登录」后，agent 直接重跑 login-confirm 即可，
        # 无需重新扫码。最后 URL 给调用方诊断信息。
        last_url = camoufox_get_url(SESSION_NAME)
        sys.stderr.write(
            f"error: 登录态未就位（最后 URL: {last_url[:120]}）\n"
            f"  - 若用户只扫了码、还没在手机上点「确认登录」→ 提示用户点确认后"
            f"重跑 login-confirm（二维码页还活着，无需重新生成）\n"
            f"  - 若已确认仍未就位 / 二维码已过期 → 重新调 login 生成新二维码\n"
        )
        sys.exit(2)

    # 已从轮询 URL 拿到登录就位信号，证明登录态已就位。
    # 登录态在 profile 里就位，close session 不影响 profile 持久化
    camoufox_close(SESSION_NAME)

    sys.stdout.write(json.dumps({
        "ok": True,
        "message": "登录成功，登录态已在 wechat-channel session profile 就位",
    }, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")


# ── 登录态校验 ──────────────────────────────────────────────────────────────

def url_at_backend(session: str, url: str) -> bool:
    """判 URL 是否已到视频号助手真后台（_ensure_login / cmd_login_confirm 共用）。

    - 空 url / 登录页（login.html、scanloginqrcode）→ False
    - 真后台路径 BACKEND_PATHS（/platform/home、/platform/post、...）→ True
    - 其余（含根路径 /platform/：入口 URL 本身含 /platform/，登录成功后页面
      也可能停在根路径「wujie 已加载但 URL 未跳转」）→ fallback 探
      wujie-app shadow 容器是否渲染。
    """
    if not url or "login" in url or "scanloginqrcode" in url:
        return False
    if any(p in url for p in BACKEND_PATHS):
        return True
    probe = camoufox_eval(
        session,
        '(() => { try { return !!document.querySelector("wujie-app"); } catch(e) { return false; } })()',
    )
    return probe in (True, "true", "True")


def _ensure_login() -> None:
    """判登录态：camoufox 打开视频号助手后台首页，轮询 redirect URL。

    - 跳 /platform/home 或 /platform/post/list 等后台路径 = 就位，return
    - 跳 login / 扫码页 / 超时仍无后台路径 = 失效，exit 2

    关键：camoufox-cli ``open`` 是「打开 + 立刻返回」，不等页面 redirect 完成。
    视频号助手首页在有登录态时会 redirect 到 /platform/home，但这个 redirect
    是浏览器拿到 HTML 后 JS 触发的，需要时间。open 后立刻读 URL 会读到首页 URL
    （无 token），误判失效。故 open 后轮询 URL，等后台路径出现或超时判真失效。

    登录态在 wechat-channel session profile 里就位即可，不导出 cookie/UA/token。
    """
    session = SESSION_NAME
    try:
        camoufox_open(session, CREATOR_CENTER_URL)
    except RuntimeError as e:
        sys.stderr.write(f"error: camoufox 打开后台首页失败: {e}\n")
        sys.exit(2)

    # 轮询 redirect URL，等后台路径出现（最多 15s）
    # 就位判定走 url_at_backend：真后台路径是 BACKEND_PATHS（/platform/home 等）；
    # 登录页 login.html 也含 /platform/ 段（域名段 channels.weixin.qq.com/platform/login.html），
    # login 检查优先；初始 URL 本身含 /platform/，不能拿 "/platform/" in url 判就位。
    deadline = time.time() + 15
    current_url = ""
    while time.time() < deadline:
        current_url = camoufox_get_url(session)
        # 显式跳登录页 → 真失效，不等
        if "login" in current_url or "scanloginqrcode" in current_url:
            break
        # 就位判定（BACKEND_PATHS 真路径 + 根路径 wujie 渲染 fallback）
        if url_at_backend(session, current_url):
            return
        time.sleep(0.5)

    sys.stderr.write(
        f"error: wechat-channel session 失效，请走 wx-channel-engagement login 流程重登\n"
        f"  (final url: {current_url[:100]})\n"
    )
    sys.exit(2)


def _prepare_session() -> str:
    """复用 wechat-channel 持久化 session。

    不再开独立 nonce session、不再 import cookie——wechat-channel session profile
    里登录态已就位（由本工具 login 流程或 wechat-channels-publish login 流程落），
    camoufox-cli 直接用即可。返回固定 session 名 SESSION_NAME。"""
    return SESSION_NAME


def _cleanup_session(session: str) -> None:
    """用完即 close——登录态在磁盘 profile，不留进程占内存。
    下次 fetch 按需重起无头 session，profile 桥接登录态。"""
    camoufox_close(session)


# ── innerText 解析 JS ─────────────────────────────────────────────────────────
#
# 视频号助手后台使用 wujie 微前端，所有内容在 <wujie-app>::shadow-root 内。
# document.body.innerText 不穿透 shadow DOM，需用 eval 手写
# document.querySelector('wujie-app').shadowRoot.innerText 拿 shadow 内文本。
#
# 具体结构需 probe 实测确认。下方 JS 是模板，probe 后据实调整。

# 读 wujie shadow 内 innerText 的 JS
_INNER_TEXT_JS = r"""
(() => {
  const wujie = document.querySelector('wujie-app');
  if (!wujie || !wujie.shadowRoot) {
    return JSON.stringify({error: 'wujie-app or shadowRoot not found', body_text: document.body.innerText.slice(0, 2000)});
  }
  // wujie shadow 内套完整 HTML 文档（children[0] = <html>），作品数据在 inner HTML 的 body.innerText
  const sr = wujie.shadowRoot;
  const innerHtml = sr.children[0];
  const innerBody = innerHtml && innerHtml.querySelector ? innerHtml.querySelector('body') : null;
  if (!innerBody) {
    return JSON.stringify({error: 'shadow inner body not found', childCount: sr.children.length});
  }
  const text = innerBody.innerText || '';
  return JSON.stringify({text: text, len: text.length});
})()
"""

# 解析作品管理页 innerText 的 JS（probe 实测后据实调整）
# 实测确认：wujie shadow 内套完整 HTML 文档，作品数据在 inner HTML 的 body.innerText
# body.innerText 结构（实测样本，每条作品占多行，字段顺序固定）：
#   "视频管理\n特效创作工具\n视频 (10)\n合集 (0)\n..."  ← 页头菜单（跳过）
#   "<作品1描述>\n<发表时间>\n<播放>\n<点赞>\n<评论>\n<分享>\n<收藏>\n[置顶|作者修改过...]\n分享\n[弹幕管理\n]评论管理\n修改描述和封面\n可见权限\n删除\n"
#   "<作品2描述>\n..."
# 每条作品以"删除"行结尾，下一行是新作品描述。发表时间格式：YYYY年MM月DD日 HH:MM。
# 行内 engagement 字段顺序：播放、点赞、评论、分享、收藏（5 个数字行连续）。
# 部分作品在数字行前多一行"已声明原创"或"仅自己可见"等状态——需跳过非数字行。
_LIST_PARSE_JS = r"""
(() => {
  const wujie = document.querySelector('wujie-app');
  if (!wujie || !wujie.shadowRoot) {
    return JSON.stringify({error: 'wujie-app or shadowRoot not found'});
  }
  const sr = wujie.shadowRoot;
  const innerHtml = sr.children[0];
  const innerBody = innerHtml && innerHtml.querySelector ? innerHtml.querySelector('body') : null;
  if (!innerBody) {
    return JSON.stringify({error: 'shadow inner body not found'});
  }
  const text = innerBody.innerText || '';
  const lines = text.split('\n').map(l => l.trim()).filter(l => l);
  if (lines.length === 0) {
    return JSON.stringify({lines: [], total: 0, error: 'empty innerText'});
  }
  // 跳过页头菜单：找第一个发表时间行作为首条作品起点
  // 发表时间格式：YYYY年MM月DD日 HH:MM
  const timeRe = /^\d{4}年\d{2}月\d{2}日\s+\d{2}:\d{2}$/;
  // 数字行正则：允许纯数字（5494）或带中文单位（14.7万、3.2亿）
  // 视频号助手对大播放量会显示"XX.X万"格式，需兼容
  const numRe = /^\d+(\.\d+)?(万|亿)?$/;
  let startIdx = -1;
  for (let i = 0; i < lines.length; i++) {
    if (timeRe.test(lines[i])) { startIdx = i; break; }
  }
  if (startIdx < 0) {
    return JSON.stringify({lines: lines.slice(0, 50), total: lines.length, error: 'no time line found'});
  }
  // 倒推：发表时间行的前一行是作品描述（可能跨多行，但实测每条描述占一行）
  // 故首条作品描述在 startIdx-1
  // 解析策略：以"删除"行作为作品分隔符，每条作品块 = [描述, 时间, 数字行×5, 状态/操作行...]
  const posts = [];
  let i = startIdx - 1;
  while (i < lines.length) {
    const desc = lines[i];
    if (!desc || desc === '删除') { i++; continue; }
    // 找发表时间
    let timeLine = null, j = i + 1;
    while (j < lines.length && !timeRe.test(lines[j])) {
      // 描述可能跨多行（实测每条占一行，但兜底：连续非时间非数字行视为描述延续）
      if (numRe.test(lines[j])) { timeLine = null; break; }
      j++;
    }
    if (j >= lines.length) break;
    // lines[j] = 发表时间
    // 后续连续数字行 = engagement（播放/点赞/评论/分享/收藏），可能前面有"已声明原创"等状态行
    let k = j + 1;
    // 跳过状态行（非数字）
    while (k < lines.length && !numRe.test(lines[k]) && lines[k] !== '删除') k++;
    const nums = [];
    while (k < lines.length && numRe.test(lines[k]) && nums.length < 6) {
      nums.push(lines[k]); k++;
    }
    // 找到下一条作品描述或结尾
    posts.push({
      desc: desc,
      published_at: lines[j],
      plays: nums[0] || '',
      likes: nums[1] || '',
      comments: nums[2] || '',
      shares: nums[3] || '',
      favorites: nums[4] || '',
    });
    // 跳到下一个发表时间 +1 的描述位置（"删除"行后）
    i = k;
    while (i < lines.length && lines[i] !== '删除') i++;
    i++;
  }
  return JSON.stringify({posts: posts.slice(0, 50), total: posts.length});
})()
"""


def fetch_post_list(session: str) -> list[dict]:
    """打开作品管理页，eval JS 解析作品列表"""
    # 1. 先访问后台首页预热 wujie 微前端框架（直接跳作品管理页会导致 wujie-app 未初始化）
    camoufox_open(session, CREATOR_CENTER_URL)
    time.sleep(3)
    # 2. 打开作品管理页
    camoufox_open(session, POST_LIST_URL)
    # 等页面加载（wujie 初始化 + shadow DOM 渲染）
    time.sleep(5)
    # 3. eval JS 解析 innerText
    raw = camoufox_eval(session, _LIST_PARSE_JS)
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, str):
            data = json.loads(data)
        if isinstance(data, dict):
            return data.get("posts", [])
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def normalize_title(s: str) -> str:
    """标题归一化用于匹配：去空白 + 去常见前缀符号"""
    return re.sub(r"\s+", "", s).strip("·*- ").lower()


# 后台行 published_at 形如「2026年08月03日 12:06」→ 解析成 ISO 日期「2026-08-03」
_BACKEND_DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")


def _parse_backend_date(s: str) -> str | None:
    """后台 published_at 字符串 → ISO 日期 YYYY-MM-DD（解析失败返回 None）"""
    m = _BACKEND_DATE_RE.search(s or "")
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _within_days(row_date: str, target_date: str, days: int) -> bool:
    """row_date 是否落在 target_date ± days 天内（ISO 日期字符串）"""
    try:
        rd = datetime.strptime(row_date, "%Y-%m-%d").date()
        td = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        return False
    return abs((rd - td).days) <= days


def _extract_metrics(row: dict) -> dict:
    """从解析后的 post dict 中提取 metrics 字段（JS 解析结果是顶层字段，不是嵌套在 metrics key 下）"""
    return {
        "plays": row.get("plays", 0),
        "likes": row.get("likes", 0),
        "comments": row.get("comments", 0),
        "shares": row.get("shares", 0),
        "favorites": row.get("favorites", 0),
    }


def match_post(rows: list[dict], target_desc: str, target_date: str | None = None) -> dict | None:
    """按完整视频描述在后台列表里找最匹配的行，返回 {desc, metrics}

    视频号作品管理页只展示完整视频描述（desc）；发布页虽可另填短标题，但管理页不展示、抓不到——DB 里 title 列存的
    也应是完整 desc（见 main AGENTS.md 发布工作流）。匹配策略（小贝建议）：
    1. 用发布日期±1天筛同日候选（后台行 published_at 形如「2026年08月03日 12:06」）
    2. 拿 desc 前 60 字归一化包含匹配——避开 hashtag 噪声，够区分
    3. 兜底：不按日期筛，全列表前 60 字归一化包含
    """
    norm_target = normalize_title(target_desc[:60])
    if not norm_target:
        return None

    def _row_norm(row: dict) -> str:
        return normalize_title((row.get("desc") or "")[:60])

    def _try_match(pool: list[dict]) -> dict | None:
        # 精确：前 60 字归一化相等
        for row in pool:
            if _row_norm(row) == norm_target:
                return {"desc": row.get("desc", ""), "metrics": _extract_metrics(row)}
        # 模糊：归一化包含
        for row in pool:
            nt = _row_norm(row)
            if nt and (norm_target in nt or nt in norm_target):
                return {"desc": row.get("desc", ""), "metrics": _extract_metrics(row)}
        return None

    # 1. 发布日期±1天筛
    if target_date:
        for row in rows:
            row["_date"] = _parse_backend_date(row.get("published_at", ""))
        same_day = [
            r for r in rows
            if r.get("_date") and _within_days(r["_date"], target_date, 1)
        ]
        if same_day:
            m = _try_match(same_day)
            if m:
                return m

    # 2. 兜底：全列表
    return _try_match(rows)


# ── CLI 子命令 ──────────────────────────────────────────────────────────────

def cmd_probe(args) -> None:
    """打开视频号助手后台 + 作品管理页，dump DOM/截图/innerText/解析 JSON

    probe 是 Plan A 可行性验证的核心动作：
    1. 确认 camoufox 能稳定打开 channels.weixin.qq.com/platform/
    2. dump 后台 DOM + 截图 + wujie shadow innerText，确认数据是否在 innerText 里
    3. 跑解析 JS，确认能从 innerText 里提结构化作品列表
    """
    _ensure_login()
    PROBE_OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = _prepare_session()
    try:
        # 1. 访问后台首页截图
        camoufox_open(session, CREATOR_CENTER_URL)
        time.sleep(3)
        camoufox_screenshot(session, PROBE_OUT_DIR / "01_home.png")
        home_url = camoufox_get_url(session)

        # 2. 打开作品管理页
        camoufox_open(session, POST_LIST_URL)
        time.sleep(5)  # wujie 初始化 + shadow DOM 渲染
        camoufox_screenshot(session, PROBE_OUT_DIR / "02_post_list.png")

        # 3. dump wujie shadow innerText（Plan A 关键）
        inner_text_raw = camoufox_eval(session, _INNER_TEXT_JS)
        (PROBE_OUT_DIR / "03_inner_text.json").write_text(
            inner_text_raw if inner_text_raw else "{}", encoding="utf-8"
        )

        # 4. dump body innerText（对照——看 wujie 外是否有内容）
        body_text_raw = camoufox_eval(session, "document.body.innerText.slice(0, 5000)")
        (PROBE_OUT_DIR / "04_body_inner_text.txt").write_text(
            body_text_raw if body_text_raw else "", encoding="utf-8"
        )

        # 5. dump 外层 HTML（看 wujie-app 结构 + shadow root 引用）
        outer_html_raw = camoufox_eval(
            session,
            "(() => { const w = document.querySelector('wujie-app'); "
            "return w ? w.outerHTML.slice(0, 3000) : 'wujie-app not found'; })()",
        )
        (PROBE_OUT_DIR / "05_wujie_outer.html").write_text(
            outer_html_raw if outer_html_raw else "", encoding="utf-8"
        )

        # 6. 跑解析 JS（probe 后据实调整）
        parse_raw = camoufox_eval(session, _LIST_PARSE_JS)
        (PROBE_OUT_DIR / "06_parsed.json").write_text(
            parse_raw if parse_raw else "{}", encoding="utf-8"
        )

        # 7. dump 完整 outerHTML（调试用，可能很大）
        full_html_raw = camoufox_eval(session, "document.documentElement.outerHTML")
        (PROBE_OUT_DIR / "07_full_outer.html").write_text(
            full_html_raw if full_html_raw else "", encoding="utf-8"
        )

        # 解析 inner_text JSON 拿 len
        inner_text_len = 0
        inner_text_error = None
        try:
            it_data = json.loads(inner_text_raw) if inner_text_raw else {}
            inner_text_len = it_data.get("len", 0)
            inner_text_error = it_data.get("error")
        except json.JSONDecodeError:
            inner_text_error = "json decode failed"

        result = {
            "ok": True,
            "session": session,
            "home_url": home_url,
            "out_dir": str(PROBE_OUT_DIR),
            "inner_text_len": inner_text_len,
            "inner_text_error": inner_text_error,
            "files": [
                "01_home.png",
                "02_post_list.png",
                "03_inner_text.json",
                "04_body_inner_text.txt",
                "05_wujie_outer.html",
                "06_parsed.json",
                "07_full_outer.html",
            ],
            "next_step": "查看 03_inner_text.json 确认 wujie shadow 内是否有结构化作品数据；"
                         "如有，调整 _LIST_PARSE_JS 提字段；如无，考虑 Plan B（fetch hook 注入）或降级",
        }
    finally:
        _cleanup_session(session)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")


def cmd_list(args) -> None:
    """列出后台所有视频 + 行内 metrics"""
    _ensure_login()
    session = _prepare_session()
    try:
        rows = fetch_post_list(session)
        result = {"ok": True, "session": session, "total": len(rows), "posts": rows}
    finally:
        _cleanup_session(session)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")


def cmd_fetch(args) -> None:
    """抓单篇：按 row.title 在作品管理页匹配，拿行内 metrics 写库"""
    if not args.row_id:
        sys.stderr.write("error: must pass --row-id\n")
        sys.exit(1)
    _ensure_login()

    row = lookup_published_row(args.row_id)
    if row is None:
        sys.stderr.write(f"error: pub_{PLATFORM} id={args.row_id} not found\n")
        sys.exit(1)

    session = _prepare_session()
    try:
        rows = fetch_post_list(session)
        matched = match_post(rows, row["title"] or "", row.get("publish_date"))
        if matched is None:
            sys.stderr.write(
                f"error: 作品管理页未找到描述匹配的 row id={row['id']} title={row['title']!r}\n"
                f"hint: 跑 probe 子命令检查页面是否正常加载；确认 DB title 存的是完整 desc\n"
            )
            sys.exit(1)
        metrics = matched["metrics"]
        update_result = update_metrics_row(row["id"], metrics)
        result = {
            "ok": True,
            "row_id": row["id"],
            "title": row["title"],
            "matched_desc": matched["desc"],
            "publish_url": row["publish_url"],
            "session": session,
            "metrics": metrics,
            "update": update_result,
        }
    finally:
        _cleanup_session(session)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")


def cmd_fetch_all(args) -> None:
    """批量刷新：打开首页一次，解析页内全部作品，匹配 pub_wx_channel 全部行写库。

    不翻页——作品管理页首页本身就是天然窗口：页内有什么解析什么，
    匹配上的行写库，匹配不上的报 unmatched 跳过（老作品不在首页是常态，非错误）。
    少操作一次页面就少一次风控暴露。
    """
    row_ids = list_all_wx_channel_rows()
    if not row_ids:
        sys.stdout.write(json.dumps({"ok": True, "total": 0, "matched": 0, "unmatched": 0, "results": []}, indent=2))
        sys.stdout.write("\n")
        return

    _ensure_login()
    session = _prepare_session()
    results = []
    n_matched = 0
    try:
        rows = fetch_post_list(session)
        for rid in row_ids:
            row = lookup_published_row(rid)
            if row is None:
                results.append({"row_id": rid, "ok": False, "error": "row not found"})
                continue
            matched = match_post(rows, row["title"] or "", row.get("publish_date"))
            if matched is None:
                # 不在首页（老作品超出首页范围/已删除）——跳过，非错误
                results.append({"row_id": rid, "ok": False, "error": "NOT_ON_FIRST_PAGE", "title": row["title"]})
                continue
            upd = update_metrics_row(rid, matched["metrics"])
            n_matched += 1
            results.append({"row_id": rid, "ok": upd.get("ok", True), "metrics": matched["metrics"]})
    finally:
        _cleanup_session(session)
    sys.stdout.write(json.dumps({
        "ok": True,
        "total": len(row_ids),
        "matched": n_matched,
        "unmatched": len(row_ids) - n_matched,
        "results": results,
    }, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")


# ── main ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fetch_engagement",
        description="WeChat Channels (视频号) engagement fetcher",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("probe", help="打开视频号助手后台 dump DOM/截图/innerText").set_defaults(func=cmd_probe)
    sub.add_parser("list", help="列出后台所有视频 + 行内 metrics").set_defaults(func=cmd_list)

    p_login = sub.add_parser("login", help="camoufox 无头截 QR PNG")
    p_login.add_argument("--reset", action="store_true", help="先删 profile 目录再 open（上一次扫码污染 cookie 后强制重来）")
    p_login.set_defaults(func=cmd_login)
    sub.add_parser("login-confirm", help="确认登录 + close session").set_defaults(func=cmd_login_confirm)

    p_fetch = sub.add_parser("fetch", help="抓单篇 engagement（按 title 在作品管理页匹配）")
    p_fetch.add_argument("--row-id", type=int, required=True)
    p_fetch.set_defaults(func=cmd_fetch)

    sub.add_parser("fetch-all", help="批量刷新（打开首页一次，匹配 pub_wx_channel 全部行写库；不翻页）").set_defaults(func=cmd_fetch_all)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except SystemExit as e:
        return int(e.code) if e.code is not None else 0
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"error: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
