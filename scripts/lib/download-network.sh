#!/usr/bin/env bash
# Called after the portable Node runtime is extracted, or with the source toolchain.
xiaobei_configure_download_network() {
  [ -n "${XIAOBEI_GITHUB_PROXY:-}" ] || return 0
  local project_root="$1" node_bin="${2:-node}" network_exports
  local helper="$project_root/browser/scripts/download-network.mjs"
  if [ ! -f "$helper" ]; then
    echo 'This release does not support XIAOBEI_GITHUB_PROXY; install a newer tarball.' >&2
    return 1
  fi
  network_exports="$("$node_bin" "$helper" --shell)" || return $?
  eval "$network_exports"
}
