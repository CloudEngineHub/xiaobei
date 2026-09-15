#!/usr/bin/env python3
"""Audio noise reduction — only for poor-quality user footage.

用 ffmpeg `afftdn`（频域降噪）或 `arnndn`（RNN 降噪）给音频去环境噪声。
只在用户素材音质差（环境噪声大、空调嗡、键盘吱）时用——AI 生成视频的音轨
是干净的，不需要降噪。

⚠️ 可选步骤，不是必跑。通用制作流程默认不做降噪处理。
**仅当用户素材音质明显差**（用户抱怨"听不清"/"有杂音"/"噪音大"，
或 review.py 报噪声指标异常）时才跑。

arnndn vs afftdn 怎么选：
- `arnndn`（Acoustic RNN Noise Suppress Network）：质量高，对人声保真，
  但要 RNN 模型文件（.rnn）。适合素材主要传人声的情况
- `afftdn`（Audio FFT-based Noise Suppressor）：纯频域降噪，无外部模型依赖，
  适合环境噪声 dominant、人声次要的情况。本脚本默认走 afftdn 避依赖

落点：在素材处理阶段（Step 3 用户素材预处理）跑——素材降噪后再进 assemble.py。
不是合成产物后跑（合成后再降噪会伤及片段间衔接处的环境音一致性）。

干湿分离：输出 `<stem>_denoised.mp4`，不覆盖输入。

Usage:
  video-producer denoise <video.mp4>
  video-producer denoise <video.mp4> --output <out.mp4>
  video-producer denoise <video.mp4> --method arnndn --rnn-model /path/to/model.rnn
  video-producer denoise <video.mp4> --noise-floor -40 --nr 12

Exit codes:
  0  ok，降噪完成
  1  参数错 / ffmpeg 缺失 / 输入不存在 / arnndn 要的 RNN 模型没给
  2  ffmpeg 渲染失败（音频损坏 / arnndn 模型加载失败）
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# 默认走 afftdn 避外部模型依赖
DEFAULT_METHOD = "afftdn"
# afftdn 默认参数——保守不伤人声：noise floor -40dB，noise reduction 12dB（默认）
DEFAULT_NOISE_FLOOR_DB = -40.0
DEFAULT_NR_DB = 12.0       # noise_reduction 强度，0.01-97，默认 12 已够用
DEFAULT_NOISE_TYPE = "white"   # white/vinyl/shellac/custom，多数环境噪走 white


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


def check_method(method: str, rnn_model: str | None) -> str:
    """确认 ffmpeg 带目标滤镜 + arnndn 需要的 RNN 模型."""
    rc, out, _ = run(["ffmpeg", "-hide_banner", "-filters"], timeout=30)
    if rc != 0:
        die("ffmpeg -filters 探测失败，ffmpeg 异常")

    if method == "afftdn":
        if "afftdn" not in out:
            die("ffmpeg 不带 afftdn 滤镜，换 ffmpeg-full 或改用 arnndn")
        return "afftdn"
    elif method == "arnndn":
        if "arnndn" not in out:
            die("ffmpeg 不带 arnndn 滤镜，换 ffmpeg-full 或改用 afftdn")
        if not rnn_model:
            die("arnndn 要 RNN 模型文件路径，传 --rnn-model <model.rnn>")
        if not Path(rnn_model).is_file():
            die(f"RNN 模型文件不存在: {rnn_model}")
        return "arnndn"
    else:
        die(f"unknown method: {method}; valid: afftdn, arnndn")


def probe_audio(video: str) -> dict | None:
    """ffprobe 数音频轨，没声轨降噪没意义."""
    import json
    rc, out, _ = run([
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-select_streams", "a", video,
    ], timeout=30)
    if rc != 0:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def denoise(video: str, output: str, method: str,
            noise_floor: float, nr: float, noise_type: str,
            rnn_model: str | None) -> dict:
    """ffmpeg afftdn / arnndn 降噪. 返回渲染元数据."""
    if method == "afftdn":
        # afftdn 真参数（ffmpeg 6+）：nf=noise floor（dB），nr=noise reduction 强度，
        # nt=noise type（white/vinyl/shellac/custom）。conservative 不伤人声
        af = f"afftdn=nf={noise_floor}:nr={nr}:nt={noise_type}"
    else:  # arnndn
        af = f"arnndn=m='{rnn_model}'"

    cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-y",
        "-i", video,
        "-af", af,
        "-c:v", "copy",                  # 视频轨原样不动
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output,
    ]
    rc, _, err = run(cmd, timeout=900)
    if rc != 0:
        die(f"ffmpeg {method} 渲染失败: {err.strip()[:500]}", code=2)

    return {
        "input": video,
        "output": output,
        "method": method,
        "noise_floor_db": noise_floor,
        "nr_db": nr,
        "noise_type": noise_type,
        "rnn_model": rnn_model,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audio noise reduction via ffmpeg afftdn/arnndn (optional, poor footage only)."
    )
    parser.add_argument("video", help="输入视频路径（含要降噪的声轨）")
    parser.add_argument("--output", default=None,
                        help="输出路径，默认输入旁加 _denoised 后缀")
    parser.add_argument("--method", default=DEFAULT_METHOD, choices=["afftdn", "arnndn"],
                        help=f"降噪方法，默认 {DEFAULT_METHOD}（afftdn 频域，arnndn 需 RNN 模型）")
    parser.add_argument("--noise-floor", type=float, default=DEFAULT_NOISE_FLOOR_DB,
                        dest="noise_floor",
                        help=f"afftdn noise floor dB，默认 {DEFAULT_NOISE_FLOOR_DB}")
    parser.add_argument("--nr", type=float, default=DEFAULT_NR_DB,
                        help=f"afftdn noise reduction 强度（0.01-97），默认 {DEFAULT_NR_DB}")
    parser.add_argument("--noise-type", default=DEFAULT_NOISE_TYPE,
                        dest="noise_type", choices=["white", "vinyl", "shellac", "custom"],
                        help=f"afftdn noise type，默认 {DEFAULT_NOISE_TYPE}")
    parser.add_argument("--rnn-model", default=None, dest="rnn_model",
                        help="arnndn RNN 模型文件路径（method=arnndn 时必传）")
    args = parser.parse_args()

    video_path = Path(args.video).resolve()
    if not video_path.is_file():
        die(f"输入视频不存在: {video_path}")

    audio_info = probe_audio(str(video_path))
    if not audio_info or not audio_info.get("streams"):
        die("视频无声轨，降噪没意义")

    check_method(args.method, args.rnn_model)

    if args.output:
        out_path = Path(args.output).resolve()
    else:
        stem = video_path.stem
        out_path = video_path.with_name(f"{stem}_denoised.mp4")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[info] input:     {video_path}")
    print(f"[info] method:    {args.method}")
    print(f"[info] output:    {out_path}")
    if args.method == "afftdn":
        print(f"[info] params:    noise_floor={args.noise_floor}dB nr={args.nr}dB noise_type={args.noise_type}")

    result = denoise(str(video_path), str(out_path), args.method,
                    args.noise_floor, args.nr, args.noise_type, args.rnn_model)

    print(f"\n[done] denoised: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
