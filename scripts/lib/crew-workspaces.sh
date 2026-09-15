#!/bin/bash
# crew-workspaces.sh - shared helpers for deploying crew template directories

# skill-wrappers.sh 提供 expose_skill_wrappers（D21 wrapper 暴露到 ~/.openclaw/bin）
# 用 lazy source 避免循环依赖：仅在 sync_crew_skills 调用时确保已加载
_skill_wrappers_sourced() {
  type expose_skill_wrappers &>/dev/null
}

copy_crew_template_contents() {
  local source_dir="$1"
  local dest_dir="$2"

  if [ ! -d "$source_dir" ]; then
    echo "❌ Crew template directory not found: $source_dir" >&2
    return 1
  fi

  mkdir -p "$dest_dir"
  cp -R "$source_dir/." "$dest_dir/"
}

# 同步 crew 专属 skill 到已部署 workspace（spec §2.3）。
#   src_crew：仓库 crews/<id>/
#   dest_ws：~/.openclaw/workspace-<id>/
# 语义：
#   - 对仓库里每个合法 skill（含 SKILL.md）+ _ 前缀共享库（如 _shared），rm -rf + ln -s 软链到 dest_ws/skills/<name>/
#   - 不删除 dest_ws/skills/ 里仓库没有的 skill（保留部署实例自定义 skill）
#   - 不碰 dest_ws 下的 AGENTS.md / TOOLS.md / Memory 等（保留用户编辑）
#   - node 依赖不在此装：由 apply-addons.sh per-skill npm install 写进仓内 skill 目录，
#     Node 从脚本 realpath 向上解析命中 skill 自己的 node_modules
# 软链而非拷贝：skill 在仓里改完即生效，运行实例无需重跑 setup。
# openclaw skill loader 跟随软链（local-loader.ts readdirSync isDirectory + realpathSync）。
# 幂等：dest 若是旧拷贝留下的真目录，rm -rf 清掉再 ln -s；已是正确软链则重建无害。
sync_crew_skills() {
  local src_crew="$1"
  local dest_ws="$2"
  local src_skills="$src_crew/skills"
  local dest_skills="$dest_ws/skills"

  [ -d "$src_skills" ] || return 0
  mkdir -p "$dest_skills"

  local skill_dir=""
  local skill_name=""
  local is_shared=""
  local synced=0
  for skill_dir in "$src_skills"/*/; do
    [ -d "$skill_dir" ] || continue
    skill_name="$(basename "$skill_dir")"
    # 软链两类目录：
    #   1. skill（含 SKILL.md）
    #   2. 共享库（_ 前缀、无 SKILL.md，如 _shared）—— 被兄弟 skill 相对导入
    #      （../../_shared/...）。软链安全：导入方自身也是软链→仓，Node/Python
    #      先 follow 到仓 realpath 再算相对路径，解析到仓里的 _shared，workspace
    #      的 _shared 不参与解析。软链保证共享库跟仓同步，不会变陈旧拷贝。
    is_shared=false
    case "$skill_name" in _*) is_shared=true;; esac
    if [ -f "${skill_dir}SKILL.md" ] || [ "$is_shared" = true ]; then
      rm -rf "$dest_skills/$skill_name"
      # 优先用软链（skill 在仓里改完即生效），失败则回退拷贝。
      # Windows 小白用户通常非管理员、未开开发者模式，ln -s 会 "Operation not permitted"。
      # 若 set -e 下 ln 失败直接退出脚本，导致 main/it-engineer 等 workspace 缺失。
      # 用 || cp -rf 回退：功能可用，代价是仓库 skill 改动不自动同步到 workspace。
      if ln -s "${skill_dir%/}" "$dest_skills/$skill_name" 2>/dev/null; then
        :
      else
        cp -rf "${skill_dir%/}" "$dest_skills/$skill_name"
        echo "  ⚠️  symlink failed for '$skill_name', used copy instead (admin/dev-mode needed for symlinks)" >&2
      fi
      synced=$((synced + 1))
    fi
  done

  [ "$synced" -gt 0 ] && echo "  ✅ synced $synced crew skill(s) → $(basename "$dest_ws")"

  # 清理悬挂软链：技能在仓里改名 / 收纳进专家包后（如 video-producer → expert-video/tools/video-producer），
  # dest_skills 下的旧软链会指向不存在的仓路径。只删「软链且目标不存在」的条目，
  # 真目录（部署实例自建技能）与有效软链一律不动。
  local pruned=0
  local link=""
  for link in "$dest_skills"/*; do
    [ -L "$link" ] || continue
    if [ ! -e "$link" ]; then
      if rm -f "$link" 2>/dev/null; then
        pruned=$((pruned + 1))
      fi
    fi
  done
  [ "$pruned" -gt 0 ] && echo "  🧹 pruned $pruned dangling skill symlink(s) in $(basename "$dest_ws")/skills"

  # D21 wrapper 暴露：把 dest_ws/skills 下顶层 wrapper 暴露到 ~/.openclaw/bin/。
  # 必须扫 dest_ws 而非 src：wrapper 软链目标需指向 workspace 字面路径——子脚本用
  # dirname $0/../../.. 推导 workspace 根（ROOT/db/…），若指向 src（仓库模板），
  # 解析后 ROOT 落在模板目录，找不到运行数据（DB 为空 / 查询返回 []）。
  # dest_ws 内 skill 是链回 src 的软链，wrapper 经软链命中真实文件，行为一致。
  if ! _skill_wrappers_sourced; then
    local _script_dir
    _script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    [ -f "$_script_dir/skill-wrappers.sh" ] && source "$_script_dir/skill-wrappers.sh"
  fi
  type expose_skill_wrappers &>/dev/null && expose_skill_wrappers "$dest_skills"
}

# 同步仓库声明的 skill 列表文件（BUILTIN_SKILLS / DENIED_SKILLS）到已部署 workspace。
#   $1 src_crew      仓库 crews/<id>/
#   $2 dest_ws       ~/.openclaw/workspace-<id>/
#   $3 project_root  仓库根
#   $4 openclaw_home ~/.openclaw
# 为什么需要：这两个文件驱动 openclaw.json 里该 agent 的 skills allowlist。技能改名或
# 收纳进专家包后（如 video-producer → expert-video/tools/video-producer），已部署 workspace
# 里的旧文件名会让 allowlist 指向不存在的技能，crew 直接失去这批能力。
# 安全边界：只在「已部署文件里存在解析不到的陈旧条目」时才重写；重写取
# 仓库声明 ∪ 已部署文件中仍能解析的条目，实例自装技能不会被抹掉。
sync_skill_declaration_files() {
  local src_crew="$1"
  local dest_ws="$2"
  local project_root="$3"
  local openclaw_home="${4:-$HOME/.openclaw}"
  local fname=""

  _skill_name_resolves() {
    local name="$1"
    [ -d "$dest_ws/skills/$name" ] && return 0
    [ -d "$src_crew/skills/$name" ] && return 0
    [ -d "$project_root/skills/$name" ] && return 0
    [ -d "$openclaw_home/skills/$name" ] && return 0
    [ -d "$project_root/openclaw/skills/$name" ] && return 0
    return 1
  }

  for fname in BUILTIN_SKILLS DENIED_SKILLS; do
    local src="$src_crew/$fname"
    local dest="$dest_ws/$fname"
    [ -f "$src" ] || continue
    if [ ! -f "$dest" ]; then
      cp "$src" "$dest" 2>/dev/null || true
      echo "  ✅ $fname installed → $(basename "$dest_ws")"
      continue
    fi

    local stale=0
    local line=""
    while IFS= read -r line || [ -n "$line" ]; do
      line="${line#"${line%%[![:space:]]*}"}"      # ltrim
      line="${line%"${line##*[![:space:]]}"}"      # rtrim
      [ -n "$line" ] || continue
      case "$line" in \#*) continue ;; esac
      _skill_name_resolves "$line" || stale=1
    done < "$dest"

    [ "$stale" = "1" ] || continue

    # 重写：仓库声明在前，已部署文件中仍能解析的自定义条目追加在后（去重）
    local merged=""
    merged="$(cat "$src")"
    while IFS= read -r line || [ -n "$line" ]; do
      line="${line#"${line%%[![:space:]]*}"}"
      line="${line%"${line##*[![:space:]]}"}"
      [ -n "$line" ] || continue
      case "$line" in \#*) continue ;; esac
      _skill_name_resolves "$line" || continue
      if ! printf '%s\n' "$merged" | grep -qxF "$line"; then
        merged="$merged"$'\n'"$line"
      fi
    done < "$dest"
    printf '%s\n' "$merged" > "$dest"
    echo "  🧹 $fname refreshed (stale skill entries) → $(basename "$dest_ws")"
  done
}

ensure_soul_crew_type() {
  local soul_file="$1"
  local crew_type="$2"

  [ -f "$soul_file" ] || return 0

  case "$crew_type" in
    internal|external) ;;
    *)
      echo "❌ Invalid crew-type: $crew_type" >&2
      return 1
      ;;
  esac

  if grep -qi '^crew-type:' "$soul_file" 2>/dev/null; then
    sed -i.bak "s/^[Cc]rew-[Tt]ype:.*$/crew-type: $crew_type/" "$soul_file"
    rm -f "$soul_file.bak"
  else
    printf '\ncrew-type: %s\n' "$crew_type" >> "$soul_file"
  fi
}
