#!/usr/bin/env python3
"""Stage 13b — motion-audit：CP 侧 motion_led 抽查，补公共 video-review。

Usage:
  python3 scripts/motion-audit.py <project_dir>

入：project_dir/video.mp4 + slots/delivery-promise.json
出：project_dir/review/motion-audit.json（motion_led 抽查结果 + 兑付判定）

motion_led 抽查：成片里真实运动镜头占比是否兑付 delivery-promise 的 motion_ratio 承诺。
技术层硬伤走公共 video-review（Stage 13a，本脚本不重做技术自检，只补 CP 侧的承诺兑付抽查）。

抽查方法（不引 CLIP/torch）：
1. ffprobe 抽每秒 1 帧到 review/frames/
2. agent 看抽帧序列，人核哪些镜有真运动（不动不算）
3. 算 motion_led = 有运动的镜数/总镜数
4. 对比 delivery-promise.motion_ratio.promised_min
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def die(msg: str) -> None:
    print(f"[error] {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 13b motion-audit")
    parser.add_argument("project_dir", help="项目目录（CP 自建工作区 output_videos/<topic-en-slug>/）")
    args = parser.parse_args()

    project = Path(args.project_dir).resolve()
    video = project / "video.mp4"
    promise_path = project / "slots" / "delivery-promise.json"
    if not video.is_file():
        die(f"前置缺失: video.mp4 不存在，先跑 assemble")
    if not promise_path.is_file():
        die(f"前置缺失: delivery-promise.json 不存在")

    review_dir = project / "review"
    frames_dir = review_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    audit_path = review_dir / "motion-audit.json"

    # checkpoint
    if audit_path.is_file():
        existing = json.loads(audit_path.read_text(encoding="utf-8"))
        print(f"[checkpoint] motion-audit.json 已存在：")
        print(json.dumps(existing, ensure_ascii=False, indent=2))
        return

    # 抽帧：每秒 1 帧
    ffprobe = shutil.which("ffprobe")
    ffmpeg = shutil.which("ffmpeg")
    if not ffprobe or not ffmpeg:
        die("ffprobe/ffmpeg 未在 PATH")

    try:
        result = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", str(video)],
            capture_output=True, text=True, timeout=15,
        )
        duration = float(json.loads(result.stdout).get("format", {}).get("duration", 0))
    except Exception:
        duration = 0.0

    frame_count = max(1, int(duration))
    if not list(frames_dir.glob("frame-*.jpg")):
        subprocess.run(
            [ffmpeg, "-i", str(video), "-vf", f"fps=1", "-q:v", "2",
             str(frames_dir / "frame-%02d.jpg")],
            capture_output=True, timeout=60,
        )

    promise = json.loads(promise_path.read_text(encoding="utf-8"))
    motion_promise = promise.get("promises", {}).get("motion_ratio", {})
    promised_min = motion_promise.get("promised_min")

    stub = {
        "stage": "13b",
        "video": str(video),
        "duration": round(duration, 3),
        "frames_sampled": frame_count,
        "frames_dir": str(frames_dir),
        "promise_motion_min": promised_min,
        "instruction": (
            "agent 看 frames/ 抽帧序列人核：哪些镜有真运动（不动不算，静图加转场也不算）。"
            "填 motion_led = 有运动的镜数/总镜数。"
            "verdict: pass（motion_led ≥ promised_min）/ fail（< promised_min，必返工换素材重渲）。"
            "技术层硬伤（黑帧/音电平/分辨率）走公共 video-review（Stage 13a），本脚本不重做。"
        ),
        "motion_led": None,
        "verdict": None,
        "must_rework": None,
    }
    audit_path.write_text(json.dumps(stub, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] 抽 {frame_count} 帧到 {frames_dir}")
    print(f"[done] motion-audit.json 模板已落：{audit_path}")
    print(f"[next] agent 看抽帧填 motion_led → verdict → pass 跑 make-cover（Stage 14a）")


if __name__ == "__main__":
    main()
