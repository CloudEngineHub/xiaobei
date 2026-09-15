#!/usr/bin/env bash
# collage-broll environment self-check.
# Exit 0 = all good; exit 1 = at least one item missing (details on stdout).
#
# 探依赖：ffmpeg / ffprobe / AWK_API_KEY（Gate 2 静帧）/ 视频平台 key（Gate 3 视频）
# 不探 venv——仓根 requirements.txt 统一装，不留独立 venv（xiaobei 语境）

set -u

FAIL=0

ok()   { printf 'PASS  %s\n' "$1"; }
bad()  { printf 'FAIL  %s\n' "$1"; FAIL=1; }

# 1. AWK_API_KEY（Gate 2 静帧生成要——siliconflow-img-gen / Seedream）
if [ -n "${AWK_API_KEY:-}" ]; then
  ok "AWK_API_KEY 已设置（Gate 2 静帧可用）"
else
  bad "AWK_API_KEY 未设置（Gate 2 静帧生成要——到 https://console.volcengine.com/ark 创建后 export 到 shell 配置）"
fi

# 2. 视频平台 key（Gate 3 视频生成要——aigc-video-gen / 百炼或火山）
if [ -n "${MODELSTUDIO_API_KEY:-}" ] || [ -n "${DASHSCOPE_API_KEY:-}" ]; then
  ok "MODELSTUDIO_API_KEY / DASHSCOPE_API_KEY 已设置（Gate 3 走百炼 happyhorse-1.1-i2v）"
elif [ -n "${AWK_GEN_KEY:-}" ]; then
  ok "AWK_GEN_KEY 已设置（Gate 3 走火山 Seedance，百炼未配）"
else
  bad "视频平台 key 都未设置（Gate 3 要 MODELSTUDIO_API_KEY 百炼 或 AWK_GEN_KEY 火山）"
fi

# 3. ffmpeg / ffprobe
if command -v ffmpeg >/dev/null 2>&1; then
  ok "ffmpeg 已装"
else
  bad "ffmpeg 缺失（macOS: brew install ffmpeg; Debian/Ubuntu: sudo apt install ffmpeg）"
fi
if command -v ffprobe >/dev/null 2>&1; then
  ok "ffprobe 已装"
else
  bad "ffprobe 缺失（跟 ffmpeg 同包，装 ffmpeg 即带）"
fi

# 4. Python >= 3.10
if command -v python3 >/dev/null 2>&1; then
  PY_VER=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "0.0")
  PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
  PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
  if [ "$PY_MAJOR" -gt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -ge 10 ]; }; then
    ok "Python $PY_VER（>= 3.10）"
  else
    bad "Python $PY_VER 过旧（需要 >= 3.10；macOS: brew install python3；或从 python.org 安装）"
  fi
else
  bad "python3 缺失（macOS: brew install python3；或从 python.org 安装）"
fi

exit $FAIL
