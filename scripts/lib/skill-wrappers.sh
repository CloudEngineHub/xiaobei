#!/bin/bash
# skill-wrappers.sh - 把 skill 顶层 wrapper 暴露到 ~/.openclaw/bin/（PATH 友好）
#
# 配合 D21 wrapper 覆盖：每个含顶层 <skill-name>.sh wrapper 的 skill，
# ln -sfn 一条 symlink 到 ~/.openclaw/bin/<skill-name>，幂等重建。
# agent 调 `<skill> <cmd>` 即可，零路径拼接（治弱模型拼错绝对路径）。
#
# 调用方：
#   apply-addons.sh       → 对公共 skills/ 暴露
#   crew-workspaces.sh    → 对各 crew crews/<id>/skills/ 暴露
#   setup-crew.sh         → 跑完 sync_crew_skills 后调
#
# 设计要点：
#   - bin 目录幂等建：mkdir -p
#   - symlink 幂等重建：ln -sfn 处理现存 symlink / 真文件 / 不存在 三种态
#     （-n 不解引用现存 symlink，避免把链 target 改成目录链套链）
#   - 仅扫顶层同名 wrapper <skill>/<skill>.sh；不带 wrapper 的 skill 不动
#     （纯指导 skill / 多并列脚本 skill 未加 wrapper，保持现状）
#   - PATH 注入：把 ~/.openclaw/bin 加进 ~/.zshrc / ~/.bashrc，幂等追加

OPENCLAW_BIN_DIR="${OPENCLAW_BIN_DIR:-$HOME/.openclaw/bin}"

# 把一个 skill 根目录下所有顶层 wrapper 暴露到 ~/.openclaw/bin/
#   $1  skills_root  skill 集合根目录（如 skills/ 或 crews/main/skills/）
expose_skill_wrappers() {
  local skills_root="$1"
  [ -d "$skills_root" ] || return 0
  mkdir -p "$OPENCLAW_BIN_DIR"

  local skill_dir=""
  local skill_name=""
  local wrapper=""
  local exposed=0
  for skill_dir in "$skills_root"/*/; do
    [ -d "$skill_dir" ] || continue
    skill_name="$(basename "$skill_dir")"
    # 跳过 _shared 等以下划线开头的辅助目录（不是 skill）
    case "$skill_name" in
      _*) continue ;;
    esac
    wrapper="$skill_dir${skill_name}.sh"
    [ -f "$wrapper" ] || continue
    # wrapper 需可执行：agent 走 PATH exec 调 `<skill> <cmd>`，缺 +x 会「权限不够」。
    chmod +x "$wrapper"
    # ln -sfn 在 Windows 非管理员/未开开发者模式时会 "Operation not permitted"。
    # set -e 下这会让整个 setup-crew.sh 退出，后续 workspace 全建不出来。
    # wrapper 暴露是辅助功能（PATH 友好），失败不阻塞核心安装。用 || true 吞掉错误。
    ln -sfn "$wrapper" "$OPENCLAW_BIN_DIR/$skill_name" 2>/dev/null || true
    exposed=$((exposed + 1))
  done

  # 专家包收纳层：暴露 <skill>/tools/<name>/<name>.sh（如 expert-wx-mp/tools/wx-mp-publisher/）
  # 工具目录整体迁入专家包后，PATH wrapper 名保持不变，调用方式零变化。
  local tool_dir=""
  local tool_name=""
  for tool_dir in "$skills_root"/*/tools/*/; do
    [ -d "$tool_dir" ] || continue
    tool_name="$(basename "$tool_dir")"
    wrapper="$tool_dir${tool_name}.sh"
    [ -f "$wrapper" ] || continue
    chmod +x "$wrapper"
    ln -sfn "$wrapper" "$OPENCLAW_BIN_DIR/$tool_name" 2>/dev/null || true
    exposed=$((exposed + 1))
  done

  # 清理悬挂 wrapper：技能改名 / 收纳进专家包 tools/ 后，旧 bin 软链会指向不存在的路径。
  # 只删「软链且目标不存在」的条目；真文件与有效软链不动。
  local bin_link=""
  local pruned=0
  for bin_link in "$OPENCLAW_BIN_DIR"/*; do
    [ -L "$bin_link" ] || continue
    if [ ! -e "$bin_link" ]; then
      if rm -f "$bin_link" 2>/dev/null; then
        pruned=$((pruned + 1))
      fi
    fi
  done
  [ "$pruned" -gt 0 ] && echo "  🧹 pruned $pruned dangling wrapper symlink(s) in ~/.openclaw/bin"

  [ "$exposed" -gt 0 ] && echo "  ✅ exposed $exposed wrapper(s) → ~/.openclaw/bin (from $(basename "$skills_root"))"
}

# 把 ~/.openclaw/bin 加进 shell rc 的 PATH（幂等）
# 仅在源码部署跑：Docker 走 COPY，容器内 PATH 由 entrypoint 自管，不调本函数。
ensure_openclaw_bin_in_path() {
  mkdir -p "$OPENCLAW_BIN_DIR"
  local marker='# wiseflow skill wrappers (D21)'
  local line="export PATH=\"\$HOME/.openclaw/bin:\$PATH\"  $marker"

  local rc_file=""
  for rc_file in "$HOME/.zshrc" "$HOME/.bashrc"; do
    # rc 不存在时只建 bashrc（zshrc 由 zsh 自管建），但本机已用 zsh 则建之
    [ -f "$rc_file" ] || continue
    if grep -qF '.openclaw/bin' "$rc_file" 2>/dev/null; then
      continue
    fi
    printf '\n%s\n' "$line" >> "$rc_file"
    echo "  ✅ Added ~/.openclaw/bin to PATH in $(basename "$rc_file")"
  done
}
