#!/usr/bin/env python3
"""Frame interpolation — 补帧到 30/60fps，仅低 fps 源材用.

用 ffmpeg `minterpolate` 滤镜补帧。只在低 fps 源材（如 24fps AI 生成片、
15fps 用户素材）补到 30fps 顺滑——发布平台播放器默认 30fps 起，低于这
画面会卡。

⚠️ 可选步骤，不是必跑。通用制作流程默认不动 fps。
**仅当源 fps < target fps** 且用户要"补帧"/"顺滑"/"提升帧率"时才跑。

minterpolate mode 怎么选：
- `blend`（默认）：纯加权混合，快、无鬼影，但运动糊——保守首选
- `mci`（motion compensated interpolation）：运动补偿，更顺但慢且
  高运动场景易出鬼影（ffmpeg mci 算法不如商业方案稳）

落点：合成产物（output_normalized.mp4 或上一步产物）之后、交付前。
干湿分离：输出 `<stem>_interp.mp4`，不覆盖输入。

Usage:
  video-producer interp <video.mp4>
  video-producer interp <video.mp4> --target-fps 30 --output <out.mp4>
  video-producer interp <video.mp4> --target-fps 60 --mode mci

Exit codes:
  0  ok，补帧完成（含源 fps ≥ target fps 自动跳过拷贝的 exit 0）
  1  参数错 / ffmpeg 缺失 / 输入不存在 / ffmpeg 不带 minterpolate
  2  ffmpeg 渲染失败（mci 出鬼影也归这档——退 blend 模式重试）
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_TARGET_FPS = 30       # 发布平台播放器默认起点
DEFAULT_MODE = "blend"        # 保守首选，无鬼影


def die(msg: str, code: int = 1) -> None:
    print(f"[error] {msg}", file=sys.stderr)
    sys.exit(code)


def run(cmd: list[str], timeout: int = 60) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        die(f"missing binary: {cmd[0]}")
    except subprocess.TimeoutExpired:
        die(f"timeout running: {' '.join(cmd[:3])}...")


def check_minterpolate() -> None:
    """ffmpeg -filters 确认带 minterpolate 滤镜."""
    rc, out, _ = run(["ffmpeg", "-hide_banner", "-filters"], timeout=30)
    if rc != 0:
        die("ffmpeg -filters 探测失败，ffmpeg 异常")
    if "minterpolate" not in out:
        die("ffmpeg 不带 minterpolate 滤镜，换 ffmpeg-full 完整版")


def probe_fps(video: str) -> float | None:
    """ffprobe 取视频帧率（r_frame_rate），返 float 或 None."""
    import json
    rc, out, _ = run([
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-select_streams", "v", video,
    ], timeout=30)
    if rc != 0:
        return None
    try:
        data = json.loads(out)
        s = data.get("streams", [{}])[0]
        rfr = s.get("r_frame_rate", "0/1")
        num, den = rfr.split("/")
        den_f = float(den)
        if den_f == 0:
            return None
        return float(num) / den_f
    except (json.JSONDecodeError, ValueError, IndexError):
        return None


def interp(video: str, output: str, target_fps: int,
           mode: str) -> dict:
    """ffmpeg minterpolate 补帧. 返回渲染元数据."""
    # fps=p 内部先把源升到 target_fps（minterpolate 输出按 fps 滤镜设定）
    # mode=blend/mci 决定补帧算法
    vf = f"minterpolate=fps={target_fps}:mi_mode={mode}"
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-y",
        "-i", video,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "copy",                  # 音轨原样不动
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        output,
    ]
    rc, _, err = run(cmd, timeout=1800)
    if rc != 0:
        die(f"ffmpeg minterpolate 渲染失败: {err.strip()[:500]}", code=2)

    return {
        "input": video,
        "output": output,
        "target_fps": target_fps,
        "mode": mode,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"Frame interpolation via ffmpeg minterpolate (optional, low-fps source only)."
    )
    parser.add_argument("video", help="输入视频路径")
    parser.add_argument("--target-fps", type=int, default=DEFAULT_TARGET_FPS,
                        help=f"目标帧率，默认 {DEFAULT_TARGET_FPS}")
    parser.add_argument("--mode", default=DEFAULT_MODE, choices=["blend", "mci"],
                        help=f"补帧模式：blend=加权混合（默认，快无鬼影但运动糊） / mci=运动补偿（更顺但慢，高运动易出鬼影）")
    parser.add_argument("--output", default=None,
                        help="输出路径，默认输入旁加 _interp 后缀")
    args = parser.parse_args()

    video_path = Path(args.video).resolve()
    if not video_path.is_file():
        die(f"输入视频不存在: {video_path}")

    check_minterpolate()

    src_fps = probe_fps(str(video_path))
    if src_fps is None:
        die("ffprobe 取源帧率失败，检查视频是否损坏")

    # 源 fps ≥ target fps → 不补帧，直接拷贝避浪费 + 避不必要重压缩
    if src_fps >= args.target_fps:
        print(f"[ok] src_fps={src_fps:.2f} ≥ target {args.target_fps}，跳过补帧直接拷贝")
        if args.output:
            out_path = Path(args.output).resolve()
        else:
            out_path = video_path.with_name(f"{video_path.stem}_interp.mp4")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(video_path, out_path)
        sys.exit(0)

    if args.output:
        out_path = Path(args.output).resolve()
    else:
        stem = video_path.stem
        out_path = video_path.with_name(f"{stem}_interp.mp4")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[info] input:       {video_path}")
    print(f"[info] src_fps:     {src_fps:.2f}")
    print(f"[info] target_fps:  {args.target_fps}")
    print(f"[info] mode:        {args.mode}")
    print(f"[info] output:      {out_path}")

    try:
        result = interp(str(video_path), str(out_path), args.target_fps, args.mode)
    except SystemExit as e:
        # mci 模式渲染失败（出鬼影/算法崩）→ 退 blend 模式重试
        if args.mode == "mci" and e.code == 2:
            print("[warn] mci 模式渲染失败，退 blend 模式重试（更稳但运动糊）", file=sys.stderr)
            result = interp(str(video_path), str(out_path), args.target_fps, "blend")
        else:
            raise

    print(f"\n[done] interpolated: {out_path}", file=sys.stderr)
    print(f"[info] {src_fps:.2f}fps → {args.target_fps}fps via {result['mode']}", file=sys.stderr)


if __name__ == "__main__":
    main()
