#!/bin/bash
# exec-tiers.sh - crew-type + ALLOWED_COMMANDS → exec-approvals / tools.exec 映射
#
# 读取 SOUL.md 的 crew-type（internal/external）+ ALLOWED_COMMANDS 微调，
# 生成 tools.exec，并通过 OpenClaw 的审批状态 owner 更新宿主策略。
#
# 权限模型（2026-07-07 简化，删 T0~T3 四档抽象）：
#   internal        → security: full（无白名单）
#   external        → security: deny
#   external + ALLOWED_COMMANDS 有 + 条目 → 升级为 allowlist（只放行那些条目）
# ALLOWED_COMMANDS 是对外 crew 在 deny 上凿洞的唯一通道；对内 crew 不读它。
#
# 被 setup-crew.sh source 使用。
export XIAOBEI_AGENT_ROSTER_MODULE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/agent-roster.cjs"

# ── 便携 readlink -f ──────────────────────────────────
# macOS 自带 BSD readlink 不支持 -f（静默失败），GNU readlink 才支持。
# 优先 readlink -f；失败则用 python3 os.path.realpath 兜底（python3 是 openclaw 硬依赖）；
# 再失败原样返回，由调用方决定是否接受非 realpath。
_resolve_realpath() {
  local p="$1" r
  r="$(readlink -f "$p" 2>/dev/null || true)"
  if [ -n "$r" ]; then echo "$r"; return; fi
  r="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$p" 2>/dev/null || true)"
  echo "${r:-$p}"
}

# 注意：resolve_crew_type 由 agent-skills.sh 提供（唯一权威实现）
# setup-crew.sh 先 source agent-skills.sh 再 source 本文件，无需重复定义。

# ── 从 ALLOWED_COMMANDS 解析 +/- 微调 ────────────────
# 输出格式: "added1 added2|removed1 removed2"
parse_allowed_commands() {
  local file="$1"
  local added=""
  local removed=""

  if [ ! -f "$file" ]; then
    echo "|"
    return
  fi

  while IFS= read -r line; do
    line="$(printf '%s' "$line" | sed 's/#.*//' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    [ -n "$line" ] || continue
    case "$line" in
      +*) added="$added ${line#+}" ;;
      -*) removed="$removed ${line#-}" ;;
    esac
  done < "$file"

  echo "${added}|${removed}"
}

# ── 计算某 crew 的最终命令列表 ──────────────────────
# 返回: 空格分隔的命令名列表, 或 "__FULL__"（internal）, 或空（external 无 + 条目）
# $1: crew_type (internal/external)
# $2: allowed_commands_file（仅 external 读取）
resolve_crew_commands() {
  local crew_type="$1"
  local allowed_commands_file="$2"

  case "$crew_type" in
    internal)
      echo "__FULL__"
      return
      ;;
    external)
      local adjustments
      adjustments="$(parse_allowed_commands "$allowed_commands_file")"
      local added="${adjustments%%|*}"
      # external 只认 + 条目（deny 上凿洞）；- 条目无意义（本就 deny）
      echo "$added"
      return
      ;;
    *)
      # 未知 crew-type：保守 deny
      echo ""
      return
      ;;
  esac
}

# ── 解析命令名 → 二进制绝对路径 ──────────────────────
# $1: 命令名或脚本路径
# $2: (可选) 基准目录，用于解析 ./ 相对路径（默认为 CWD）
resolve_binary_path() {
  local cmd="$1"
  local base_dir="${2:-}"
  # 脚本路径（./scripts/... 或绝对路径）→ 转绝对路径
  # 已安装脚本使用 realpath，与引擎的 resolvedRealPath 匹配口径一致；
  # 尚未安装的脚本保留规范化绝对路径，不因目录缺失而丢弃声明。
  case "$cmd" in
    ./*|../*)
      local abs
      abs="$(node -e 'console.log(require("node:path").resolve(process.argv[1], process.argv[2]))' "${base_dir:-$PWD}" "$cmd")"
      if [ -e "$abs" ]; then
        _resolve_realpath "$abs"
      else
        printf '%s\n' "$abs"
      fi
      return
      ;;
    /*)
      # OpenClaw matchAllowlist 用 resolvedRealPath（readlink -f）匹配 pattern，
      # 因此 allowlist 条目必须用 realpath 而非 symlink 路径，
      # 否则 /usr/bin/python3 → /usr/bin/python3.12 的 symlink 会导致 allowlist miss。
      local real
      real="$(_resolve_realpath "$cmd")"
      echo "${real:-$cmd}"
      return
      ;;
  esac
  # skill wrapper 裸名优先查 ~/.openclaw/bin：setup-crew 进程 PATH 可能不含该目录
  # （首装时 rc 尚未 source），command -v 解析不到会把 allowlist 条目静默丢掉。
  local wrapper_bin="${OPENCLAW_BIN_DIR:-$HOME/.openclaw/bin}/$cmd"
  if [ -e "$wrapper_bin" ]; then
    local real
    real="$(_resolve_realpath "$wrapper_bin")"
    echo "${real:-$wrapper_bin}"
    return
  fi
  # command -v 可能返回 shell builtin 名（无 /），此时尝试 which 或常见路径
  local resolved
  resolved="$(command -v "$cmd" 2>/dev/null || true)"
  case "$resolved" in
    /*)
      local real
      real="$(_resolve_realpath "$resolved")"
      echo "${real:-$resolved}"
      return
      ;;
  esac
  # 尝试 which（跳过 builtins）
  resolved="$(which "$cmd" 2>/dev/null || true)"
  case "$resolved" in
    /*)
      local real
      real="$(_resolve_realpath "$resolved")"
      echo "${real:-$resolved}"
      return
      ;;
  esac
  # 兜底：检查常见系统目录
  local dir
  for dir in /usr/bin /bin /usr/local/bin; do
    if [ -x "$dir/$cmd" ]; then
      local real
      real="$(_resolve_realpath "$dir/$cmd")"
      echo "${real:-$dir/$cmd}"
      return
    fi
  done
}

# ── 为 crew 生成 allowlist JSON 数组 ────────────────
# $1: 空格分隔的命令列表
# $2: (可选) agent workspace 目录，用于解析 ./ 相对路径
# 输出: JSON 数组字符串
build_exec_allowlist_json() {
  local commands="$1"
  local base_dir="${2:-}"

  if [ -z "$commands" ] || [ "$commands" = "__FULL__" ]; then
    echo "[]"
    return
  fi

  local entries=""
  local first=true
  for cmd in $commands; do
    local bin_path
    bin_path="$(resolve_binary_path "$cmd" "$base_dir")"
    [ -n "$bin_path" ] || continue

    if [ "$first" = "true" ]; then
      first=false
    else
      entries="${entries},"
    fi
    # 转义 JSON 中的特殊字符（路径一般没有，但以防万一）
    local escaped
    escaped="$(printf '%s' "$bin_path" | sed 's/\\/\\\\/g; s/"/\\"/g')"
    entries="${entries}{\"pattern\":\"${escaped}\"}"
  done

  echo "[${entries}]"
}

# ── crew-type → tools.exec JSON 对象 ────────────────
# $1: crew_type, $2: has_allowlist (true/false)
crew_type_to_tools_exec_json() {
  local crew_type="$1" has_allowlist="$2"
  case "$crew_type" in
    internal) echo '{"host":"gateway","mode":"full"}' ;;
    external)
      if [ "$has_allowlist" = "true" ]; then
        echo '{"host":"gateway","mode":"allowlist"}'
      else
        echo '{"host":"gateway","mode":"deny"}'
      fi
      ;;
    *) echo '{"host":"gateway","mode":"deny"}' ;;
  esac
}

# ── 高层接口：为一组 agents 计算并写入 exec 配置 ─────
# 参数: config_path crews_dir project_root
# 读取每个已注册 crew 的 crew-type，生成 tools.exec + exec-approvals
apply_exec_tiers() {
  local config_path="$1"
  local crews_dir="$2"
  local project_root="$3"

  # 收集所有已注册 crew 的 exec 配置
  local agent_configs="{}"
  local tools_exec_patches="{}"

  local agent_entries=""
  agent_entries="$(CONFIG_PATH="$config_path" node -e '
const fs = require("fs");
const home = process.env.HOME || "";
const c = JSON.parse(fs.readFileSync(process.env.CONFIG_PATH, "utf8"));
for (const a of require(process.env.XIAOBEI_AGENT_ROSTER_MODULE).listAgents(c)) {
  if (!a || typeof a.id !== "string" || !a.id.trim()) continue;
  const id = a.id.trim();
  const wsRaw = typeof a.workspace === "string" && a.workspace.trim()
    ? a.workspace.trim()
    : ("~/.openclaw/workspace-" + id);
  const ws = wsRaw.replace(/^~(?=\/|$)/, home);
  console.log(id + "\t" + ws);
}
')"

  while IFS=$'\t' read -r agent_id workspace_dir; do
    [ -n "$agent_id" ] || continue
    [ -n "$workspace_dir" ] || workspace_dir="$HOME/.openclaw/workspace-$agent_id"
    local soul_file="$workspace_dir/SOUL.md"
    local crew_type
    crew_type="$(resolve_crew_type "$soul_file")"

    # ALLOWED_COMMANDS：优先实例 workspace，缺失回退模板目录
    local allowed_cmds_file="$workspace_dir/ALLOWED_COMMANDS"
    if [ ! -f "$allowed_cmds_file" ] && [ -f "$crews_dir/$agent_id/ALLOWED_COMMANDS" ]; then
      allowed_cmds_file="$crews_dir/$agent_id/ALLOWED_COMMANDS"
    fi

    # 解析最终命令列表
    local commands
    commands="$(resolve_crew_commands "$crew_type" "$allowed_cmds_file")"

    # 生成 allowlist JSON（./ 路径相对于 agent workspace 解析）
    local allowlist_json
    allowlist_json="$(build_exec_allowlist_json "$commands" "$workspace_dir")"

    local has_allowlist="false"
    if [ -n "$allowlist_json" ] && [ "$allowlist_json" != "[]" ]; then
      has_allowlist="true"
    fi

    # 生成 tools.exec JSON
    local tools_exec_json
    tools_exec_json="$(crew_type_to_tools_exec_json "$crew_type" "$has_allowlist")"

    # 生成 exec-approvals agent 配置
    local agent_security agent_ask
    agent_ask="off"
    case "$crew_type" in
      internal) agent_security="full" ;;
      external)
        if [ "$has_allowlist" = "true" ]; then
          agent_security="allowlist"
        else
          agent_security="deny"
        fi
        ;;
      *) agent_security="deny" ;;
    esac

    local cmd_count
    if [ "$commands" = "__FULL__" ]; then
      cmd_count="full"
    elif [ -z "$allowlist_json" ] || [ "$allowlist_json" = "[]" ]; then
      cmd_count="0"
    else
      # 统计实际生成的 allowlist 条目数（已解析为绝对路径的）
      cmd_count="$(printf '%s' "$allowlist_json" | node -e '
        const j = JSON.parse(require("fs").readFileSync(0,"utf8"));
        console.log(j.length);
      ')"
    fi

    echo "  🔒 $agent_id [$crew_type] → security=$agent_security, commands=$cmd_count"

    # 累加到 JSON 对象
    agent_configs="$(PREV="$agent_configs" AID="$agent_id" SEC="$agent_security" ASK="$agent_ask" AL="$allowlist_json" \
      node -e '
const prev = JSON.parse(process.env.PREV);
prev[process.env.AID] = {
  security: process.env.SEC,
  ask: process.env.ASK,
  askFallback: "deny",
  allowlist: JSON.parse(process.env.AL),
};
console.log(JSON.stringify(prev));
')"

    tools_exec_patches="$(PREV="$tools_exec_patches" AID="$agent_id" TEJ="$tools_exec_json" \
      node -e '
const prev = JSON.parse(process.env.PREV);
prev[process.env.AID] = JSON.parse(process.env.TEJ);
console.log(JSON.stringify(prev));
')"
  done <<< "$agent_entries"

  # apply-addons 在新引擎构建和 Doctor 迁移后再同步宿主策略。
  if [ "${XIAOBEI_DEFER_EXEC_APPROVALS:-0}" = "1" ]; then
    echo "  ⏳ Host exec approvals deferred until the pinned engine is ready"
  else
    printf '%s\n' "$agent_configs" | node "$project_root/scripts/sync-exec-approvals.mjs" --config "$config_path"
  fi

  # 写入 agents.entries.<id>.tools.exec 到 openclaw.json
  TOOLS_EXEC_PATCHES="$tools_exec_patches" CONFIG_PATH="$config_path" node -e '
const fs = require("fs");
const patches = JSON.parse(process.env.TOOLS_EXEC_PATCHES);
const c = JSON.parse(fs.readFileSync(process.env.CONFIG_PATH, "utf8"));
const {getAgent, setAgent} = require(process.env.XIAOBEI_AGENT_ROSTER_MODULE);
for (const [agentId, execConfig] of Object.entries(patches)) {
  const agent = getAgent(c, agentId);
  if (agent) {
    setAgent(c, agentId, {
      ...agent,
      tools: {
        ...(agent.tools || {}),
        exec: { ...(agent.tools?.exec || {}), ...execConfig },
      },
    });
  }
}
fs.writeFileSync(process.env.CONFIG_PATH, JSON.stringify(c, null, 2) + "\n");
'
  echo "  ✅ agents.entries.<id>.tools.exec updated"
}
