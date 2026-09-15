#!/usr/bin/env bash
# design-full.sh — design-full 工具 wrapper（薄转发，子命令范式；expert-design 包内工具）
# 让 agent 用 `design-full <子命令> [参数...]` 走 PATH，零路径拼接。
# 子命令：
#   init <任务名>            建任务文件夹 + brief 模板（落 design_assets/YYYY-MM-DD-<任务名>/）
#   pick "<风格描述>"        从内置设计系统库匹配最合适的 1–3 套
# 内部转发到 scripts/ 下对应脚本；wrapper 自身只是 exec 转发，不改语义。
set -euo pipefail
SELF="${BASH_SOURCE[0]}"
# Resolve symlink (wrapper is ln -sfn'd into ~/.openclaw/bin) so SCRIPT_DIR points at the real skill dir.
while [ -L "$SELF" ]; do SELF="$(readlink -f "$SELF")"; done
SCRIPT_DIR="$(cd "$(dirname "$SELF")" && pwd)"

SUBCMD="${1:?用法: design-full <init|pick> [参数...]}"
shift
case "$SUBCMD" in
  init)
    exec "$SCRIPT_DIR/scripts/init.sh" "$@"
    ;;
  pick)
    exec "$SCRIPT_DIR/scripts/pick.sh" "$@"
    ;;
  -h|--help|help)
    cat <<'HELP'
design-full — 平面设计原子工具（wrapper，expert-design 包内工具）

用法:
  design-full init <任务名>           建任务文件夹 + brief 模板
  design-full pick "<风格描述>"        从内置设计系统库匹配最合适的 1–3 套
  design-full help                    本帮助

子命令是 expert-design 通用骨架里的原子步骤：
  Step 1 建工作区       → design-full init（workdir 必须是 Content Producer workspace 根）
  Step 3 设计系统选取   → design-full pick
其余步骤（brief 确认、素材获取、HTML/CSS 编写、视觉 review、交付归档）由 agent
按 expert-design 包内 SKILL.md 与 workflows/ 直接执行，不经本 wrapper。
HELP
    ;;
  *)
    echo "未知子命令: $SUBCMD" >&2
    echo "用 design-full help 查可用子命令" >&2
    exit 1
    ;;
esac
