#!/usr/bin/env bash
set -euo pipefail
SELF="${BASH_SOURCE[0]}"
while [ -L "$SELF" ]; do SELF="$(readlink -f "$SELF")"; done
SCRIPT_DIR="$(cd "$(dirname "$SELF")" && pwd)"
if [[ "${1:-}" != "resume" ]]; then
  echo '数字人生成已迁到 avatar generate；旧任务仍可 liveportrait resume --job <旧任务记录>' >&2
  exit 2
fi
exec python3 "$SCRIPT_DIR/scripts/liveportrait.py" "$@"
