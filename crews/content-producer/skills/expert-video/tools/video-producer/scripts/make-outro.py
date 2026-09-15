#!/usr/bin/env python3
"""make-outro — 片尾制作一步出片。

原子工具，不写死 Workflow。agent 按 SKILL.md 场景化组合调用。

片尾制作涉及：AIGC 生成形象视频 + 补黑边到标准比例 + 烧录字幕（指定颜色/字体/淡入）。
本子命令封装"形象图 → 标准比例片尾"全流程。

Usage:
  python3 scripts/make-outro.py <project_dir> --image <形象图路径> --slogan <slogan 文本>
    [--color color.json] [--duration 5] [--width 1080] [--fps 30] [--output outro.mp4]

参数说明：
  --image     形象图路径（PNG/JPG，相对 project_dir 或绝对）
  --slogan    slogan 文本（烧录到画面中央）
  --color     颜色配置 JSON 路径（默认黑色背景白色文字）
              JSON 结构：{"bg": "#000000", "text": "#ffffff", "font": "Noto Sans CJK SC", "size": 48, "fadein": 0.5}
  --duration  片尾时长（秒，默认 5）
  --width     输出宽度（默认 1080，高度按 16:9 算）
  --fps       输出帧率（默认 30）
  --output    输出文件名（相对 project_dir，默认 render/outro/outro.mp4）

实现：
  1. 形象图 scale 到目标宽度 + pad 16:9（黑边补到标准比例）
  2. 烧录 slogan 字幕（drawtext，颜色/字体/字号按 color.json，淡入动画）
  3. 加静音音轨（anullsrc，与片尾时长对齐）
  4. 输出到 render/outro/outro.mp4，assemble 自动收段纳入
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def die(msg: str) -> None:
    print(f"[error] {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    print(f"[cmd] {cmd[0]} ... ({len(cmd)} args)")
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        die(f"命令失败 (rc={p.returncode}): {p.stderr[:500] or p.stdout[:500]}")
    return p


def load_color_config(color_path: Path | None) -> dict:
    """加载颜色配置 JSON。默认黑底白字、Noto Sans CJK SC、48px、0.5s 淡入。"""
    default = {
        "bg": "#000000",
        "text": "#ffffff",
        "font": "Noto Sans CJK SC",
        "size": 48,
        "fadein": 0.5,
    }
    if color_path is None or not color_path.is_file():
        return default
    try:
        cfg = json.loads(color_path.read_text(encoding="utf-8"))
        default.update(cfg)
        return default
    except (json.JSONDecodeError, OSError) as e:
        print(f"[warn] 颜色配置解析失败 ({e})，用默认")
        return default


def hex_to_ffmpeg_color(hex_color: str) -> str:
    """#RRGGBB → 0xRRGGBB（ffmpeg drawtext color 格式）。"""
    h = hex_color.lstrip("#")
    if len(h) == 6:
        return f"0x{h}"
    return "0xFFFFFF"


def main() -> None:
    parser = argparse.ArgumentParser(description="make-outro 片尾制作")
    parser.add_argument("project_dir", help="项目目录（CP 自建工作区 output_videos/<topic-en-slug>/）")
    parser.add_argument("--image", required=True, help="形象图路径（PNG/JPG）")
    parser.add_argument("--slogan", required=True, help="slogan 文本（烧录到画面中央）")
    parser.add_argument("--color", default=None, help="颜色配置 JSON 路径")
    parser.add_argument("--duration", type=float, default=5.0, help="片尾时长（秒，默认 5）")
    parser.add_argument("--width", type=int, default=1080, help="输出宽度（默认 1080）")
    parser.add_argument("--fps", type=int, default=30, help="输出帧率（默认 30）")
    parser.add_argument("--output", default="render/outro/outro.mp4",
                        help="输出文件名（相对 project_dir，默认 render/outro/outro.mp4）")
    args = parser.parse_args()

    project = Path(args.project_dir).resolve()
    img_path = Path(args.image)
    if not img_path.is_absolute():
        img_path = project / args.image
    if not img_path.is_file():
        die(f"形象图不存在: {img_path}")

    out_path = project / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)

    color_cfg = load_color_config(
        Path(args.color) if args.color else None
    )

    height = round(args.width * 9 / 16)
    bg_color = hex_to_ffmpeg_color(color_cfg["bg"])
    text_color = hex_to_ffmpeg_color(color_cfg["text"])
    font_name = color_cfg["font"]
    font_size = int(color_cfg["size"])
    fadein_dur = float(color_cfg["fadein"])

    # 1. 形象图 scale + pad 16:9
    # 2. 烧录 slogan（drawtext，居中，淡入）
    # 3. 加静音音轨（anullsrc + 视频合流）
    # 全部一条 ffmpeg 命令完成

    # drawtext：slogan 文本居中，淡入动画用 alphaexpr
    # 文本需转义（空格/冒号/单引号）
    slogan_escaped = args.slogan.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    drawtext = (
        f"drawtext=text='{slogan_escaped}':"
        f"font='{font_name}':fontsize={font_size}:"
        f"fontcolor={text_color}:"
        f"x=(w-text_w)/2:y=(h-text_h)/2:"
        f"alpha='if(lt(t,{fadein_dur}),t/{fadein_dur},1)'"
    )

    # 视频滤镜：scale + pad + drawtext
    vf = (
        f"scale={args.width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={args.width}:{height}:(ow-iw)/2:(oh-ih)/2:color={bg_color},"
        f"setsar=1,fps={args.fps},format=yuv420p,"
        f"{drawtext}"
    )

    # 静音音轨：anullsrc 生成，与视频合流
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(img_path),
        "-f", "lavfi", "-t", f"{args.duration:.3f}",
        "-i", "anullsrc=channel_layout=mono:sample_rate=24000",
        "-vf", vf,
        "-t", str(args.duration),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(out_path),
    ]
    print(f"[outro] 形象图 {img_path.name} → 标准比例片尾")
    print(f"  - 尺寸 {args.width}x{height}@{args.fps}fps，时长 {args.duration}s")
    print(f"  - slogan「{args.slogan}」烧录居中，{fadein_dur}s 淡入")
    run(cmd)

    print(f"[done] 片尾已落：{out_path}")
    print(f"  - assemble 自动收段纳入（render/outro/ 命名子目录）")


if __name__ == "__main__":
    main()
