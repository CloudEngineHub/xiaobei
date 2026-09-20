#!/usr/bin/env bash
# collage-broll.sh — collage-broll 工具 wrapper（薄转发，子命令范式）
# 让 agent 用 `collage-broll <子命令> [参数...]` 走 PATH，零路径拼接。
# 子命令：
#   check-setup                       环境自检（ffmpeg/ffprobe/AWK_API_KEY/视频平台 key/python 版本）
#   render --batch <jobs.json> [--dry-run]   Stage 10 批量调度 i2v 生成
# 纸拼贴 B-roll 的完整制作流程见 expert-video 包内 Collage B-roll Workflow。
set -euo pipefail
SELF="${BASH_SOURCE[0]}"
# Resolve symlink (wrapper is ln -sfn'd into ~/.openclaw/bin) so SCRIPT_DIR points at the real tool dir.
while [ -L "$SELF" ]; do SELF="$(readlink -f "$SELF")"; done
SCRIPT_DIR="$(cd "$(dirname "$SELF")" && pwd)"

SUBCMD="${1:?用法: collage-broll <check-setup|render> [参数...]}"
shift
case "$SUBCMD" in
  check-setup)
    exec bash "$SCRIPT_DIR/scripts/check_setup.sh" "$@"
    ;;
  render)
    exec python3 "$SCRIPT_DIR/scripts/run_render.py" "$@"
    ;;
  -h|--help|help)
    cat <<'HELP'
collage-broll — 纸拼贴 B-roll 原子工具（wrapper）

用法:
  collage-broll check-setup                         环境自检（依赖与 key）
  collage-broll render --batch <gen-jobs.json>      Stage 10 批量 i2v 生成（串行调 aigc-video-gen）
  collage-broll render --batch <...> --dry-run      只打印调度计划不真调
  collage-broll help                                本帮助

退出码:
  check-setup  0 全通 / 1 有缺项
  render       0 全部 job 跑通 / 1 参数错或 wrapper 缺失 / 2 部分 job 失败（已跑通的保留）

制作流程（GATE A 隐喻清单 → GATE B 静帧 → Stage 10 i2v 组装）见 expert-video 包内
Collage B-roll Workflow；本 wrapper 只代理脚本，不含流程语义。
HELP
    ;;
  *)
    echo "未知子命令: $SUBCMD" >&2
    echo "用 collage-broll help 查可用子命令" >&2
    exit 1
    ;;
esac
