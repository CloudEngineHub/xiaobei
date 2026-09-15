#!/usr/bin/env bash
# collage-broll.sh — collage-broll 工具 wrapper（薄转发，子命令范式）
# 让 agent 用 `collage-broll <子命令> [参数...]` 走 PATH，零路径拼接。
# 子命令：
#   check-setup              环境自检（ffmpeg/ffprobe/AWK_API_KEY/视频平台 key/python 版本）
#   gate3 --batch <jobs.json> [--dry-run]   Gate 3 批量调度 i2v 生成
# 纸拼贴 B-roll 的完整制作流程见 expert-video 包内 Collage B-roll Workflow。
set -euo pipefail
SELF="${BASH_SOURCE[0]}"
# Resolve symlink (wrapper is ln -sfn'd into ~/.openclaw/bin) so SCRIPT_DIR points at the real tool dir.
while [ -L "$SELF" ]; do SELF="$(readlink -f "$SELF")"; done
SCRIPT_DIR="$(cd "$(dirname "$SELF")" && pwd)"

SUBCMD="${1:?用法: collage-broll <check-setup|gate3> [参数...]}"
shift
case "$SUBCMD" in
  check-setup)
    exec bash "$SCRIPT_DIR/scripts/check_setup.sh" "$@"
    ;;
  gate3)
    exec python3 "$SCRIPT_DIR/scripts/run_gate3.py" "$@"
    ;;
  -h|--help|help)
    cat <<'HELP'
collage-broll — 纸拼贴 B-roll 原子工具（wrapper）

用法:
  collage-broll check-setup                       环境自检（依赖与 key）
  collage-broll gate3 --batch <gen-jobs.json>     Gate 3 批量 i2v 生成（串行调 aigc-video-gen）
  collage-broll gate3 --batch <...> --dry-run     只打印调度计划不真调
  collage-broll help                              本帮助

退出码:
  check-setup  0 全通 / 1 有缺项
  gate3        0 全部 job 跑通 / 1 参数错或 wrapper 缺失 / 2 部分 job 失败（已跑通的保留）

制作流程（隐喻 → 静帧 → 视频三道闸门）见 expert-video 包内 Collage B-roll Workflow；
本 wrapper 只代理脚本，不含流程语义。
HELP
    ;;
  *)
    echo "未知子命令: $SUBCMD" >&2
    echo "用 collage-broll help 查可用子命令" >&2
    exit 1
    ;;
esac
