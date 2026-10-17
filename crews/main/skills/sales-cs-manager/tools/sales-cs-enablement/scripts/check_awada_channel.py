#!/usr/bin/env python3
"""Read-only Awada V2 configuration check; optional authenticated health/capabilities probe.

Exit 0: a selected enabled account is configured; 1: invalid/incomplete; 2: config absent.
No credential values or provider response bodies are printed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

DEFAULT_RELAY = "https://relay.openclaw-for-business.com/api/v2/awada"


def path_default():
    state = Path(os.environ.get("OPENCLAW_STATE_DIR", str(Path.home() / ".openclaw")))
    return Path(os.environ.get("OPENCLAW_CONFIG_PATH") or os.environ.get("OPENCLAW_JSON") or state / "openclaw.json").expanduser()


def api_url(base, endpoint, lane=""):
    url = urlsplit(base)
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("invalid relayBaseUrl")
    prefix = re.sub(r"/api/v[12]/awada$", "", url.path.rstrip("/"))
    return urlunsplit((url.scheme, url.netloc, prefix + "/api/v2/awada" + endpoint, urlencode({"lane": lane}) if lane else "", ""))


def resolved_key(value):
    if not isinstance(value, str):
        return ""
    value = value.strip()
    match = re.fullmatch(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", value)
    if match:
        value = os.environ.get(match[1], "").strip()
    return "" if not value or value.startswith("<") else value


def probe(base, key, lane):
    def request(endpoint, authenticated):
        req = Request(api_url(base, endpoint, lane if authenticated else ""), headers={"X-OFB-Key": key} if authenticated else {})
        with urlopen(req, timeout=5) as response:
            data = json.loads(response.read(2 * 1024 * 1024))
        if data.get("success") is not True or not isinstance(data.get("data"), dict):
            raise ValueError("invalid V2 response envelope")
        return data["data"]
    health = request("/health", False)
    if health.get("version") != 2 or health.get("redis") is not True:
        raise ValueError("V2 health/Redis check failed")
    capabilities = request("/capabilities", True)
    lane_info = capabilities.get("lane", {})
    return {"ok": True, "laneId": lane_info.get("laneId")}


def check(cfg, account_id=None, agent_id="sales-cs", remote=False):
    root = cfg.get("channels", {}).get("awada", {})
    if not isinstance(root, dict):
        raise ValueError("channels.awada must be an object")
    plugins = cfg.get("plugins", {})
    plugin_enabled = plugins.get("enabled") is not False and plugins.get("entries", {}).get("awada", {}).get("enabled") is True
    plugin_enabled = plugin_enabled and "awada" not in plugins.get("deny", []) and (not plugins.get("allow") or "awada" in plugins["allow"])
    accounts = root.get("accounts", {})
    ids = list(accounts)
    if root.get("awadaKey") or not ids:
        ids = list(dict.fromkeys(["default", *ids]))
    if account_id and account_id not in ids:
        return {"configured": False, "pluginEnabled": plugin_enabled, "accounts": [], "reason": "requested account not found"}
    selected = [account_id] if account_id else ids
    rows = []
    for name in selected:
        effective = {key: value for key, value in root.items() if key not in ("accounts", "defaultAccount")}
        effective.update(accounts.get(name, {}))
        key = resolved_key(effective.get("awadaKey"))
        base = effective.get("relayBaseUrl") or DEFAULT_RELAY
        lane = effective.get("lane") or ""
        dm = effective.get("dmPolicy", "pairing")
        groups = effective.get("groupPolicy", cfg.get("channels", {}).get("defaults", {}).get("groupPolicy", "open"))
        errors = []
        if "list" in cfg.get("agents", {}):
            errors.append("legacy_agents_roster_run_doctor")
        if not plugin_enabled:
            errors.append("plugin_disabled_or_not_enabled")
        if root.get("enabled") is False or effective.get("enabled") is False:
            errors.append("account_disabled")
        if not key:
            errors.append("key_missing_placeholder_or_unresolved")
        if dm not in ("open", "pairing", "allowlist", "disabled"):
            errors.append("invalid_dm_policy")
        if groups not in ("open", "allowlist", "disabled"):
            errors.append("invalid_group_policy")
        if dm == "open" and "*" not in effective.get("allowFrom", []):
            errors.append("open_dm_requires_wildcard_allow_from")
        if dm == "allowlist" and not effective.get("allowFrom"):
            errors.append("dm_allowlist_empty")
        if dm == "disabled" and groups == "disabled":
            errors.append("all_message_access_disabled")
        try:
            api_url(base, "/health")
            if effective.get("mediaPublicBaseUrl"):
                api_url(effective["mediaPublicBaseUrl"], "/health")
        except (ValueError, TypeError):
            errors.append("invalid_relay_or_media_url")
        bindings = [binding.get("agentId") for binding in cfg.get("bindings", [])
                    if binding.get("match", {}).get("channel") == "awada"
                    and binding["match"].get("accountId", "default") in (name, "*")]
        bound = any(binding.get("agentId") == agent_id and binding.get("match", {}) in
                    ({"channel": "awada", "accountId": name}, {"channel": "awada", "accountId": "*"},
                     *([{"channel": "awada"}] if name == "default" else [])) for binding in cfg.get("bindings", []))
        row = {"accountId": name, "configured": not errors, "keyConfigured": bool(key),
               "lane": lane, "dmPolicy": dm, "groupPolicy": groups, "boundAgents": bindings,
               "boundToRequestedAgent": bound, "errors": errors,
               "mediaHostingConfigured": bool(effective.get("mediaPublicBaseUrl"))}
        if remote and not errors:
            try:
                row["probe"] = probe(base, key, lane)
            except HTTPError as error:
                row["probe"] = {"ok": False, "error": f"HTTP_{error.code}"}
                row["configured"] = False
            except (URLError, OSError, ValueError, TypeError, AttributeError):
                row["probe"] = {"ok": False, "error": "V2_PROBE_FAILED"}
                row["configured"] = False
        rows.append(row)
    ready = [row["accountId"] for row in rows if row["configured"]]
    return {"configured": bool(ready), "pluginEnabled": plugin_enabled, "accounts": rows, "configuredAccountIds": ready,
            "agentId": agent_id, "agentRegistered": agent_id in cfg.get("agents", {}).get("entries", {})
                or any(agent.get("id") == agent_id for agent in cfg.get("agents", {}).get("list", [])),
            "commandsFile": plugins.get("entries", {}).get("awada", {}).get("config", {}).get("commandsFile"),
            "runtimeVerified": False, "probeRequested": remote}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=path_default())
    parser.add_argument("--account-id")
    parser.add_argument("--agent-id", default="sales-cs")
    parser.add_argument("--probe", action="store_true", help="read-only V2 health and authenticated capabilities; no sends")
    args = parser.parse_args()
    path = args.config.expanduser()
    result = {"configured": False, "path": str(path)}
    if not path.is_file():
        result["reason"] = "openclaw.json not found"
        print(json.dumps(result, ensure_ascii=False))
        return 2
    try:
        result.update(check(json.loads(path.read_text(encoding="utf-8")), args.account_id, args.agent_id, args.probe))
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        result["reason"] = "invalid or unreadable config"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["configured"] else 1


if __name__ == "__main__":
    sys.exit(main())
