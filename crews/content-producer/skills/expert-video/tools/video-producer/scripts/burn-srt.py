#!/usr/bin/env python3
"""Burn SRT subtitles into MP4 — optional, user-requested only.

把 SRT 字幕硬烧进视频画面（不可关、跟着成片走）。跟软字幕（.srt 外挂、
平台播放器可开关）不同——硬烧适合"平台不支持外挂字幕"或"想保证画面字
一定显示"的场景。

⚠️ 可选步骤，不是必跑。通用制作流程默认不烧字幕
（assemble.py / exportMp4 都不烧）；**仅当用户明确说"要字幕"/"烧字幕"/
"hardcode subtitles"时才跑**。

落点：合成产物（output.mp4 或 output_normalized.mp4）之后、交付前。
干湿分离：输出 `<stem>_burned.mp4`，不覆盖输入。

ffmpeg subtitles 滤镜要点：
- 用 `subtitles=filename='...'` 滤镜，需 libass 编译进去（Ubuntu 默认 ffmpeg 带）
- 字体：默认 libass 拿 fontconfig 找，中文字幕要 `force_style='FontName=...'` 强制
- 字幕样式由 SRT 内 cue style 或 force_style 覆盖，本脚本默认给一套可读样式

Usage:
  video-producer burn-srt <video.mp4> <subs.srt>
  video-producer burn-srt <video.mp4> <subs.srt> --output <out.mp4>
  video-producer burn-srt <video.mp4> <subs.srt> --font-name "<已安装中文字体>" --font-size 24

Exit codes:
  0  ok，字幕烧完
  1  参数错 / ffmpeg 缺失 / 输入不存在 / ffmpeg 不带 libass
  2  ffmpeg 渲染失败（SRT 损坏 / 字体缺 / 渲染中断）
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'deck-render' / 'scripts'))
from font_policy import font_family

# 默认字幕样式——黑白配 + 半透底框，短视频通用可读样式
DEFAULT_FONT_NAME = font_family()
DEFAULT_FONT_SIZE = 24
DEFAULT_FORCE_STYLE = (
    "FontName={font},FontSize={size},"
    "PrimaryColour=&H00FFFFFF&,OutlineColour=&H00000000&,"
    "BackColour=&H80000000&,BorderStyle=4,"
    "Outline=2,Shadow=1,Alignment=2,MarginV=40"
)


def die(msg: str, code: int = 1) -> None:
    print(f"[error] {msg}", file=sys.stderr)
    sys.exit(code)


def run(cmd: list[str], timeout: int = 60, cwd=None) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        die(f"missing binary: {cmd[0]}")
    except subprocess.TimeoutExpired:
        die(f"timeout running: {' '.join(cmd[:3])}...")


def check_libass() -> None:
    """ffmpeg subtitles 滤镜依赖 libass。启动时探一次，没带则报错不白跑."""
    rc, out, _ = run(["ffmpeg", "-hide_banner", "-filters"], timeout=30)
    if rc != 0:
        die("ffmpeg -filters 探测失败，ffmpeg 异常")
    if "subtitles" not in out:
        die("ffmpeg 不带 libass（subtitles 滤镜缺席），无法烧字幕；换 ffmpeg-full 完整版")


def validate_srt(srt_path: str) -> None:
    """基本 SRT 校验：非空 + 至少一条 cue + timestamp 格式."""
    try:
        content = Path(srt_path).read_text(encoding="utf-8").strip()
    except OSError as e:
        die(f"读 SRT 失败: {e}")
    if not content:
        die("SRT 文件空")
    # 至少含一个 "-->" 时间戳分隔符（SRT 格式的硬标志）
    if "-->" not in content:
        die("SRT 不含任何 `-->` 时间戳分隔符，格式错")


def validate_ass(path: str) -> None:
    """Validate ASS structure/times without rewriting styles or drawing overrides."""
    try:
        content = Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as e:
        die(f"读 ASS 失败: {e}")
    section = ""
    sections = set()
    fields = []
    cues = 0

    def timestamp(value: str) -> float:
        if not re.fullmatch(r"[0-9]+:[0-9]{2}:[0-9]{2}[.][0-9]{2}", value.strip()):
            die(f"ASS 时间戳格式错: {value}")
        h, m, s = value.strip().split(":")
        if int(m) >= 60 or float(s) >= 60:
            die(f"ASS 时间戳越界: {value}")
        return int(h) * 3600 + int(m) * 60 + float(s)

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line.lower()
            sections.add(section)
        elif section == "[events]" and line.lower().startswith("format:"):
            fields = [x.strip().lower() for x in line.split(":", 1)[1].split(",")]
            if not {"start", "end", "text"}.issubset(fields) or fields[-1] != "text":
                die("ASS Events Format 缺少 Start/End/Text 或 Text 不在末尾")
        elif section == "[events]" and line.lower().startswith("dialogue:"):
            if not fields:
                die("ASS Dialogue 前缺少 Events Format")
            values = line.split(":", 1)[1].split(",", len(fields) - 1)
            if len(values) != len(fields):
                die("ASS Dialogue 字段数量错")
            cue = dict(zip(fields, values))
            if timestamp(cue["end"]) <= timestamp(cue["start"]):
                die("ASS Dialogue 结束时间必须大于开始时间")
            if not cue["text"].strip():
                die("ASS Dialogue 文本为空")
            cues += 1
    if not {"[script info]", "[v4+ styles]", "[events]"}.issubset(sections) or not cues:
        die("ASS 缺少 Script Info/V4+ Styles/Events 或有效 Dialogue")


def validate_subtitles(path: str) -> None:
    # Explicit extension dispatch: never accept malformed SRT as ASS.
    if Path(path).suffix.lower() == ".ass":
        validate_ass(path)
    else:
        validate_srt(path)


def burn(video: str, srt: str, output: str, font_name: str,
         font_size: int, force_style: str | None) -> dict:
    """ffmpeg subtitles 滤镜烧 SRT. 返回渲染元数据."""
    style = (
        force_style if force_style is not None
        else ("" if Path(srt).suffix.lower() == ".ass"
              else DEFAULT_FORCE_STYLE.format(font=font_name, size=font_size))
    )
    # Keep source paths out of the filter expression: shell quoting is not
    # libavfilter quoting. A local ASCII filename also handles quotes/colons.
    with tempfile.TemporaryDirectory(prefix='.burn-', dir=Path(output).parent) as folder:
        work = Path(folder)
        subtitle_name = 'subtitles' + ('.ass' if Path(srt).suffix.lower() == '.ass' else '.srt')
        shutil.copyfile(srt, work / subtitle_name)
        style_value = style.replace('\\', '\\\\').replace("'", "'\\''")
        vf = f"subtitles=filename={subtitle_name}"
        if style:
            vf += f":force_style='{style_value}'"
        dest = work / 'burned.mp4'
        cmd = [
        "nice", "-n", "19", "ffmpeg", "-hide_banner", "-nostats", "-y",
        "-filter_threads", "2",
        "-i", str(Path(video).resolve()),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-threads", "2",
        "-c:a", "copy",                  # 音轨原样不动
        "-movflags", "+faststart",
        str(dest),
        ]
        rc, _, err = run(cmd, timeout=900, cwd=work)
        if rc != 0:
            die(f"ffmpeg subtitles 渲染失败: {err.strip()[:500]}", code=2)
        dest.replace(output)

    return {
        "input": video,
        "srt": srt,
        "output": output,
        "font_name": font_name,
        "font_size": font_size,
        "force_style": style,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Burn SRT subtitles into MP4 (optional, user-requested only)."
    )
    parser.add_argument("video", help="输入视频（合成产物，含声轨）")
    parser.add_argument("srt", help="SRT 或 ASS 字幕文件路径（ASS 保留原生样式及绘图）")
    parser.add_argument("--output", default=None,
                        help="输出路径，默认在输入旁加 _burned 后缀")
    parser.add_argument("--font-name", default=DEFAULT_FONT_NAME,
                        help=f"字体名，默认 {DEFAULT_FONT_NAME}")
    parser.add_argument("--font-size", type=int, default=DEFAULT_FONT_SIZE,
                        help=f"字体大小，默认 {DEFAULT_FONT_SIZE}")
    parser.add_argument("--force-style", default=None,
                        help="Override libass force_style 字串（覆盖默认样式）")
    args = parser.parse_args()

    video_path = Path(args.video).resolve()
    if not video_path.is_file():
        die(f"输入视频不存在: {video_path}")

    srt_path = Path(args.srt).resolve()
    if not srt_path.is_file():
        die(f"SRT 文件不存在: {srt_path}")

    if args.output:
        out_path = Path(args.output).resolve()
    else:
        stem = video_path.stem
        out_path = video_path.with_name(f"{stem}_burned.mp4")
    if out_path in (video_path, srt_path) or out_path.exists() and any(out_path.samefile(p) for p in (video_path, srt_path)):
        die("输出不得覆盖输入视频或字幕")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    check_libass()
    validate_subtitles(str(srt_path))

    print(f"[info] input:   {video_path}")
    print(f"[info] srt:     {srt_path}")
    print(f"[info] output:  {out_path}")
    print(f"[info] font:    {args.font_name} @ {args.font_size}px")

    result = burn(str(video_path), str(srt_path), str(out_path),
                  args.font_name, args.font_size, args.force_style)

    print(f"\n[done] burned: {out_path}", file=sys.stderr)
    print(f"[info] style used: {result['force_style'][:80]}...", file=sys.stderr)


if __name__ == "__main__":
    main()
