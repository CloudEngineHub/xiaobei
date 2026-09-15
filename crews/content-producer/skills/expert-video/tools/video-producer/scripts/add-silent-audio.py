#!/usr/bin/env python3
"""add-silent-audio — 给无音频的视频片段补静音音轨。

原子工具，不写死 Workflow。agent 按 SKILL.md 场景化组合调用。

concat 前各段音轨连续的必要前置：AIGC i2v 产物常无音频流，
直拼后整片音轨断续。assemble 内部也会自动调本能力，本子命令
供 agent 在复杂场景显式补齐。

Usage:
  python3 scripts/add-silent-audio.py --input gen.mp4 --output gen-audio.mp4
  python3 scripts/add-silent-audio.py --input gen.mp4 --output gen-audio.mp4 --duration 5.0
  python3 scripts/add-silent-audio.py --input gen.mp4 --output gen-audio.mp4 --sample-rate 48000 --channels stereo

参数说明：
  --input        输入视频路径
  --output       输出视频路径（含静音音轨）
  --duration     强制静音轨时长（秒，可选；默认取输入视频时长，对齐到视频）
  --sample-rate  静音轨采样率（默认 24000，与 awk-tts 输出对齐）
  --channels     静音轨声道（默认 mono；可选 stereo）

实现：
  - 先 ffprobe 探测输入是否已有音频流；有则直接 copy 输出（idempotent）
  - 无音频流时：anullsrc 生成静音 lavfi 源 + 视频 -i 合流 -shortest 对齐
  - anullsrc channel_layout=mono:sample_rate=24000，时长用 -t 控制（--duration 或视频时长）
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


def has_audio(path: Path) -> bool:
    """ffprobe 探测是否有音频流。"""
    p = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "a:0",
         "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return p.stdout.strip() == "audio"


def probe_duration(path: Path) -> float:
    p = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
        capture_output=True, text=True,
    )
    if p.returncode != 0:
        return 0.0
    try:
        return float(json.loads(p.stdout).get("format", {}).get("duration", 0) or 0)
    except Exception:
        return 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="add-silent-audio 补静音音轨")
    parser.add_argument("--input", required=True, help="输入视频路径")
    parser.add_argument("--output", required=True, help="输出视频路径（含静音音轨）")
    parser.add_argument("--duration", type=float, default=None,
                        help="强制静音轨时长（秒，可选；默认取输入视频时长）")
    parser.add_argument("--sample-rate", type=int, default=24000,
                        help="静音轨采样率（默认 24000，与 awk-tts 输出对齐）")
    parser.add_argument("--channels", default="mono", choices=["mono", "stereo"],
                        help="静音轨声道（默认 mono）")
    args = parser.parse_args()

    src = Path(args.input).resolve()
    dst = Path(args.output).resolve()
    if not src.is_file():
        die(f"输入不存在: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)

    # idempotent：已有音频流则直接 copy 输出，避免重复补轨
    if has_audio(src):
        run(["ffmpeg", "-y", "-i", str(src), "-c", "copy", str(dst)])
        print(f"[done] {src.name} 已有音频流，直 copy → {dst.name}")
        return

    video_dur = probe_duration(src)
    target_dur = args.duration if args.duration is not None else video_dur
    if target_dur <= 0:
        die(f"无法确定静音轨时长：--duration 未传且视频时长探测为 {video_dur}")

    layout = "mono" if args.channels == "mono" else "stereo"
    # anullsrc 生成静音 lavfi 源，sample_rate + channel_layout 指定规格
    # -t 限制静音轨时长（--duration 或视频时长），-shortest 对齐视频
    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-f", "lavfi", "-t", str(target_dur),
        "-i", f"anullsrc=channel_layout={layout}:sample_rate={args.sample_rate}",
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(dst),
    ]
    run(cmd)
    print(f"[done] 静音音轨已补 → {dst.name}")
    print(f"  - 采样率 {args.sample_rate}Hz，声道 {args.channels}")
    print(f"  - 时长 {target_dur:.3f}s（{'--duration 指定' if args.duration is not None else '视频时长对齐'}）")


if __name__ == "__main__":
    main()
