#!/usr/bin/env python3
"""BGM ducking — narration/dialog drives BGM auto-ducking via sidechain.

把 BGM 轨在旁白/对话出现时自动压低，旁白停了再放开——专业混音的标配。
只在声画同出模式（gen.py 出的片旁白+BGM 同轨）且用户要专业混音时用。

⚠️ 可选步骤，不是必跑。通用制作流程默认不做混音处理——
assemble.py / normalize.py 都只碰整体响度，不动轨间电平。
**仅当用户明确说"要混音"/"做 ducking"/"BGM 压旁白"/"professional mix"时才跑**。

前置：要有可分离的 BGM 轨和旁白轨。AI 声画同出模式 gen.py 出的片是
**混轨单声道**——duck.py 没法从混轨里分离 BGM 和旁白。所以本脚本实际
只在以下场景能用：
1. assemble.py 走 Stock Footage + TTS 模式：素材视频（含 BGM/环境音）+
   外挂 speech.mp3 旁白——BGM 在视频轨、旁白在音频轨，可分离
2. 用户人工提供了 BGM.mp3 和 narration.mp3 两份独立文件
3. tts.py 生成的旁白是独立文件，BGM 也是独立文件

输入要两份音频 + 一份视频（或只视频，duck.py 只处音频轨再合回去）。
落点：assemble.py 之后、normalize.py 之前——ducking 改的是轨间电平，
normalize 改的是整体响度，先 duck 再 normalize 顺序不能反。

ffmpeg sidechaincompress 滤镜要点：
- 把旁白轨作 sidechain input 触发 BGM 轨压缩
- 阈值约 -25 dB（旁白起来才触），比例 8:1（压狠），起 5ms 放 300ms（自然）
- attack/release 不能太短，短了BGM抖；不能太长，长了旁白起了 BGM 没压下去

Usage:
  video-producer duck <video.mp4> <narration.mp3> --bgm-track audio:0
  video-producer duck <video.mp4> <narration.mp3> --bgm-source bgm.mp3 --output mixed.mp4
  video-producer duck <video.mp4> <narration.mp3> --threshold -25 --ratio 8

Exit codes:
  0  ok，ducking 完成
  1  参数错 / ffmpeg 缺失 / 输入不存在
  2  ffmpeg 渲染失败（音频轨配置错 / 渲染中断）
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Sidechain 压缩参数——专业混音通用起点，用户要调可传 override
# ⚠️ ffmpeg sidechaincompress 的 threshold / makeup 参数要归一化振幅（[0,1] 范），
# 不是 dB。我们把 dB 入参转线性振幅再塞给 ffmpeg：linear = 10^(dB/20)
DEFAULT_THRESHOLD_DB = -25.0      # 旁白起来到这 dB 才触 BGM 压
DEFAULT_RATIO = 8.0                # 8:1 压狠
DEFAULT_ATTACK_MS = 5              # 起得快但不抖
DEFAULT_RELEASE_MS = 300           # 放得慢，旁白停了 BGM 缓升
DEFAULT_MAKEUP_DB = 3.0            # BGM 被压后补点 makeup 避免整体偏轻


def db_to_linear(db: float) -> float:
    """dB → 线性振幅（ffmpeg sidechaincompress threshold/makeup 要这套）."""
    return 10 ** (db / 20.0)


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


def probe_audio_streams(video: str) -> int:
    """ffprobe 数音频轨数，caller 用它判断 BGM 轨存在."""
    rc, out, _ = run([
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-select_streams", "a", video,
    ], timeout=30)
    if rc != 0:
        return 0
    import json
    try:
        data = json.loads(out)
        return len(data.get("streams", []))
    except json.JSONDecodeError:
        return 0


def duck(video: str, narration: str, output: str,
         bgm_source: str | None, bgm_track: str,
         threshold: float, ratio: float,
         attack_ms: int, release_ms: int, makeup_db: float) -> dict:
    """ffmpeg sidechaincompress ducking. 返回渲染元数据."""
    # BGM 来源：外挂 bgm.mp3 或视频自带音轨
    # threshold / makeup 要从 dB 转线性振幅塞给 ffmpeg sidechaincompress
    threshold_lin = db_to_linear(threshold)
    makeup_lin = db_to_linear(makeup_db)
    # ⚠️ 滤镜图要点（ffmpeg 严要求，错一个出空片或报错）：
    # 1. sidechaincompress 吃两输入（main + sidechain）输出一份——BGM 给 main、旁白给 sidechain
    # 2. BGM 不用 split（整个给 sidechaincompress 的 main 输入，输出一份被压过的 BGM）
    # 3. 旁白要 split=2：一份作 sidechain 触发源（被 sidechaincompress 内部消费），一份最终混入
    # 4. 每个 split/asplit 输出都要被下游滤镜消费，否则报 unconnected output
    if bgm_source:
        # 外挂 BGM 模式：ffmpeg -i video -i narration -i bgm
        # [1:a] 旁白 split：side 那份触发 BGM 压（被 sidechaincompress 消费），nar 那份最终混入
        # [2:a] BGM 整个给 sidechaincompress 的 main 输入 → 被 sidechain 压 → [mixed]
        # [nar] + [mixed] amix 出最终音轨
        inputs = ["-i", video, "-i", narration, "-i", bgm_source]
        af = (
            f"[1:a]asplit=2[side][nar];"
            f"[2:a][side]sidechaincompress="
            f"threshold={threshold_lin}:ratio={ratio}:"
            f"attack={attack_ms}:release={release_ms}:"
            f"makeup={makeup_lin}[mixed];"
            f"[nar][mixed]amix=inputs=2:duration=longest:dropout_transition=0[a]"
        )
        mapping = ["-map", "0:v", "-map", "[a]"]
    else:
        # 视频自带 BGM 模式：BGM 在 [0:a]，旁白作外挂 [1:a]
        # [0:a] BGM 整个给 sidechaincompress 的 main 输入（不 split，省一个闲输出）
        # [1:a] 旁白 split：nar_side 那份作 sidechain 触发源（被 sidechaincompress 内部消费），nar_main 那份最终混入
        # [0:a] + [nar_side] → sidechaincompress → [bgm_ducked]
        # [nar_main] + [bgm_ducked] amix 出最终音轨
        inputs = ["-i", video, "-i", narration]
        af = (
            f"[1:a]asplit=2[nar_side][nar_main];"
            f"[0:a][nar_side]sidechaincompress="
            f"threshold={threshold_lin}:ratio={ratio}:"
            f"attack={attack_ms}:release={release_ms}:"
            f"makeup={makeup_lin}[bgm_ducked];"
            f"[nar_main][bgm_ducked]amix=inputs=2:duration=longest:dropout_transition=0[a]"
        )
        mapping = ["-map", "0:v", "-map", "[a]"]

    cmd = [
        "ffmpeg", "-hide_banner", "-nostats", "-y",
        *inputs,
        "-filter_complex", af,
        *mapping,
        "-c:v", "copy",                  # 视频轨原样不动
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output,
    ]
    rc, _, err = run(cmd, timeout=900)
    if rc != 0:
        die(f"ffmpeg sidechaincompress 渲染失败: {err.strip()[:500]}", code=2)

    return {
        "input": video,
        "narration": narration,
        "bgm_source": bgm_source or "video_internal",
        "output": output,
        "threshold_db": threshold,
        "ratio": ratio,
        "attack_ms": attack_ms,
        "release_ms": release_ms,
        "makeup_db": makeup_db,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="BGM ducking via sidechaincompress (optional, professional mix only)."
    )
    parser.add_argument("video", help="输入视频（合成产物）")
    parser.add_argument("narration", help="旁白轨独立文件（mp3/wav/opus 等）")
    parser.add_argument("--bgm-source", default=None,
                        help="外挂 BGM 文件路径；不传则用视频自带音轨作 BGM")
    parser.add_argument("--bgm-track", default="audio:0",
                        help="视频自带 BGM 轨，默认 audio:0（第一个音轨）")
    parser.add_argument("--output", default=None,
                        help="输出路径，默认输入旁加 _ducked 后缀")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD_DB,
                        help=f"触发阈 dB，默认 {DEFAULT_THRESHOLD_DB}")
    parser.add_argument("--ratio", type=float, default=DEFAULT_RATIO,
                        help=f"压缩比，默认 {DEFAULT_RATIO}")
    parser.add_argument("--attack", type=int, default=DEFAULT_ATTACK_MS,
                        dest="attack_ms", help=f"起 ms，默认 {DEFAULT_ATTACK_MS}")
    parser.add_argument("--release", type=int, default=DEFAULT_RELEASE_MS,
                        dest="release_ms", help=f"放 ms，默认 {DEFAULT_RELEASE_MS}")
    parser.add_argument("--makeup", type=float, default=DEFAULT_MAKEUP_DB,
                        help=f"BGM 压后补 dB，默认 {DEFAULT_MAKEUP_DB}")
    args = parser.parse_args()

    video_path = Path(args.video).resolve()
    if not video_path.is_file():
        die(f"输入视频不存在: {video_path}")

    narration_path = Path(args.narration).resolve()
    if not narration_path.is_file():
        die(f"旁白文件不存在: {narration_path}")

    if args.bgm_source:
        bgm_path = Path(args.bgm_source).resolve()
        if not bgm_path.is_file():
            die(f"BGM 文件不存在: {bgm_path}")
        bgm_src = str(bgm_path)
    else:
        # 没外挂 BGM → 要确认视频有音轨可作 BGM
        n_audio = probe_audio_streams(str(video_path))
        if n_audio == 0:
            die("视频无声轨，无法作 BGM 来源——传 --bgm-source 指定外挂 BGM 文件")
        bgm_src = None

    if args.output:
        out_path = Path(args.output).resolve()
    else:
        stem = video_path.stem
        out_path = video_path.with_name(f"{stem}_ducked.mp4")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[info] input:      {video_path}")
    print(f"[info] narration:  {narration_path}")
    print(f"[info] bgm:        {bgm_src or args.bgm_track}")
    print(f"[info] output:     {out_path}")
    print(f"[info] params:     threshold={args.threshold}dB ratio={args.ratio} "
          f"attack={args.attack_ms}ms release={args.release_ms}ms makeup={args.makeup}dB")

    result = duck(str(video_path), str(narration_path), str(out_path),
                  bgm_src, args.bgm_track,
                  args.threshold, args.ratio,
                  args.attack_ms, args.release_ms, args.makeup)

    print(f"\n[done] ducked: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
