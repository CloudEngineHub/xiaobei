#!/usr/bin/env bash
# Apply source patches only; never touch user config, dependencies or services.
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OPENCLAW_DIR="${OPENCLAW_DIR:-$PROJECT_ROOT/openclaw}"
source "$PROJECT_ROOT/openclaw.version"
if [[ "$(git -C "$OPENCLAW_DIR" rev-parse HEAD)" != "$OPENCLAW_COMMIT" ]]; then
  echo "OpenClaw HEAD does not match openclaw.version ($OPENCLAW_VERSION)" >&2
  exit 1
fi
for patch in "$PROJECT_ROOT"/patches/*.patch "$PROJECT_ROOT"/patches/browser-camoufox-pivot/patches/*.patch; do
  [[ -f "$patch" ]] || continue
  echo "  → $(basename "$patch")"
  # Exact patches are deliberate: --3way can exit zero with unmerged stages.
  git -C "$OPENCLAW_DIR" apply --check "$patch"
  git -C "$OPENCLAW_DIR" apply --index "$patch"
done
for file in "$PROJECT_ROOT"/patches/browser-camoufox-pivot/files/*.ts; do
  [[ -f "$file" ]] || continue
  cp "$file" "$OPENCLAW_DIR/extensions/browser/src/"
done
if [[ -n "$(git -C "$OPENCLAW_DIR" ls-files -u)" ]]; then
  echo "OpenClaw patch application left unresolved conflicts" >&2
  exit 1
fi
