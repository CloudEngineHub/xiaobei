#!/usr/bin/env python3
"""Gate 3 批量调度——读 gen-jobs.json 逐条调公共 aigc-video-gen wrapper 走 i2v 模式（首尾帧插值）。

每个 job 字段：
  prompt         aigc-video-gen --prompt（中文声画同出描述）
  first_frame    首帧路径（纯色空场，720x1280）
  last_frame     尾帧路径（确认静帧裁到 720x1280，720P）
  output         输出 MP4 路径（相对 workspace，须在 output_videos/ 或 <platform>/outputs/ 下——aigc-video-gen 的 ensure_safe_output 要求）
  ratio          默认 9:16
  resolution     默认 720P
  duration       默认 5

aigc-video-gen wrapper 内部已带候选链 fallback + decisions.log 落盘，本脚本只做批量调度——
串行调（视频生成是异步轮询任务，并行调会撞平台并发限）。

Usage:
  python3 <skill-dir>/scripts/run_gate3.py --batch <project>/gen-jobs.json
  python3 <skill-dir>/scripts/run_gate3.py --batch <project>/gen-jobs.json --dry-run

Exit codes:
  0  全部 job 跑通
  1  参数错 / gen-jobs.json 不存在 / 格式错 / aigc-video-gen wrapper 不在 PATH
  2  部分 job 失败（stderr 报失败清单，已跑通的保留）
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

# 公共 wrapper——aigc-video-gen（PATH 化调用，不裸引用其下 scripts/gen.py）
WRAPPER = "aigc-video-gen"


def die(msg: str, code: int = 1) -> None:
    print(f"[error] {msg}", file=sys.stderr)
    sys.exit(code)


def run_one(job: dict, job_id: int, dry_run: bool) -> tuple[bool, str]:
    """调 aigc-video-gen wrapper i2v 跑一个 job. 返 (ok, detail)."""
    for required in ("prompt", "first_frame", "last_frame", "output"):
        if not job.get(required):
            return False, f"job {job_id} missing field: {required}"

    cmd = [
        WRAPPER,
        "--prompt", job["prompt"],
        "--image", job["first_frame"],        # i2v 首帧
        "--last-frame", job["last_frame"],    # i2v 尾帧
        "--ratio", job.get("ratio", "9:16"),
        "--resolution", job.get("resolution", "720P"),
        "--duration", str(job.get("duration", 5)),
        "--output", job["output"],
    ]

    if dry_run:
        print(f"[dry-run] job {job_id}: {' '.join(cmd[:4])} ... --output {job['output']}")
        return True, "dry-run skipped"

    print(f"[info] job {job_id}: aigc-video-gen i2v → {job['output']}")
    try:
        r = subprocess.run(cmd, timeout=1200)
        if r.returncode == 0:
            return True, f"ok exit 0 → {job['output']}"
        return False, f"aigc-video-gen exit {r.returncode} for job {job_id}（查 wrapper stderr + decisions.log）"
    except subprocess.TimeoutExpired:
        return False, f"aigc-video-gen timeout 1200s for job {job_id}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gate 3 批量调度——读 gen-jobs.json 逐条调公共 aigc-video-gen wrapper 走 i2v（首尾帧插值）."
    )
    parser.add_argument("--batch", required=True, help="gen-jobs.json 路径")
    parser.add_argument("--dry-run", action="store_true", help="只打印不真调")
    args = parser.parse_args()

    if not shutil.which(WRAPPER):
        die(f"wrapper 不在 PATH: {WRAPPER}（确认公共 aigc-video-gen 已通过 apply-addons.sh 软链到 ~/.openclaw/bin）")

    batch_path = Path(args.batch).resolve()
    if not batch_path.is_file():
        die(f"gen-jobs.json 不存在: {batch_path}")

    try:
        jobs = json.loads(batch_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        die(f"gen-jobs.json 格式错: {e}")

    if not isinstance(jobs, list):
        die("gen-jobs.json 顶层数组不是 list")

    print(f"[info] batch: {batch_path} ({len(jobs)} jobs)")

    failures: list[tuple[int, str]] = []
    for i, job in enumerate(jobs):
        ok, detail = run_one(job, i, args.dry_run)
        print(detail)
        if not ok:
            failures.append((i, detail))

    if failures:
        print(f"\n[fail] {len(failures)} job(s) failed:", file=sys.stderr)
        for jid, det in failures:
            print(f"  job {jid}: {det}", file=sys.stderr)
        sys.exit(2)

    print(f"\n[ok] all {len(jobs)} jobs completed")


if __name__ == "__main__":
    main()
