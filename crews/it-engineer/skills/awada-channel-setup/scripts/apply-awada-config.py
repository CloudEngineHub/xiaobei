#!/usr/bin/env python3
"""Merge one Awada V2 account, crew and binding without replacing unrelated configuration."""
from __future__ import annotations

import argparse
import copy
import getpass
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

SAMPLE = Path(__file__).resolve().parent.parent / "openclaw-awada-sample.json"


def config_path() -> Path:
    state = Path(os.environ.get("OPENCLAW_STATE_DIR", str(Path.home() / ".openclaw")))
    return Path(os.environ.get("OPENCLAW_CONFIG_PATH") or os.environ.get("OPENCLAW_JSON") or state / "openclaw.json").expanduser()


def project_root(explicit: str | None, cfg: dict) -> Path:
    candidates = [explicit, os.environ.get("WISEFLOW_PROJECT_ROOT"), os.environ.get("XIAOBEI_HOME"), str(Path(__file__).resolve().parents[5]), "/opt/openclaw"]
    candidates += [str(Path(p).expanduser().parent) for p in cfg.get("plugins", {}).get("load", {}).get("paths", []) if isinstance(p, str) and Path(p).name == "awada"]
    for value in candidates:
        if value and (Path(value).expanduser() / "awada" / "package.json").is_file():
            return Path(value).expanduser().resolve()
        if value and value == explicit:
            raise ValueError("project root has no awada/package.json")
    raise ValueError("Cannot locate the project; pass --project-root (see OFB_ENV.md)")


def merge(base: dict, overlay: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        result[key] = merge(result[key], value) if isinstance(result.get(key), dict) and isinstance(value, dict) else copy.deepcopy(value)
    return result


def render(value, root: Path, state: Path):
    if isinstance(value, str):
        return value.replace("{WISEFLOW_PROJECT_ROOT}", str(root)).replace("{path_to_.openclaw}", str(state)).replace("{HOME}", str(Path.home()))
    if isinstance(value, dict):
        return {key: render(item, root, state) for key, item in value.items()}
    if isinstance(value, list):
        return [render(item, root, state) for item in value]
    return value


def valid_url(value: str):
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("URL must be an HTTP(S) origin or API path, without credentials/query/fragment")


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=config_path())
    parser.add_argument("--project-root")
    parser.add_argument("--account-id")
    parser.add_argument("--agent-id", default="sales-cs")
    parser.add_argument("--agent-sample", type=Path)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--key-env", default="AWADA_KEY", help="environment variable containing the lane key; never pass the key as an argument")
    parser.add_argument("--replace-key", action="store_true", help="explicitly replace the selected account key from --key-env or hidden interactive input")
    parser.add_argument("--lane", help="omit to retain existing selection; empty string asks Relay to resolve the unique user lane")
    parser.add_argument("--relay-base-url")
    parser.add_argument("--dm-policy", choices=("open", "pairing", "allowlist", "disabled"))
    parser.add_argument("--allow-from", action="append")
    parser.add_argument("--group-policy", choices=("open", "allowlist", "disabled"))
    parser.add_argument("--media-public-base-url")
    parser.add_argument("--commands-file")
    parser.add_argument("--without-customerdb", action="store_true", help="leave the existing CustomerDB scope unchanged")
    parser.add_argument("--dry-run", action="store_true", help="print a redacted plan without writing or restarting anything")
    return parser.parse_args()


def build(cfg: dict, args):
    root = project_root(args.project_root, cfg)
    state = Path(os.environ.get("OPENCLAW_STATE_DIR", str(args.config.expanduser().resolve().parent))).expanduser().resolve()
    template = render(json.loads(SAMPLE.read_text(encoding="utf-8")), root, state)
    result = copy.deepcopy(cfg)
    channels = result.setdefault("channels", {})
    awada = channels.setdefault("awada", {})
    accounts = awada.get("accounts", {})
    if not args.account_id and not awada.get("defaultAccount") and not awada.get("awadaKey") and len(accounts) > 1:
        raise ValueError("Multiple accounts without a default; pass --account-id")
    account_id = args.account_id or awada.get("defaultAccount") or ("default" if awada.get("awadaKey") else next(iter(accounts), "default"))
    account_id = account_id.strip()
    if not account_id or any(char in account_id for char in "/\\\x00\n"):
        raise ValueError("Invalid account ID")
    common = {key: value for key, value in awada.items() if key not in ("accounts", "defaultAccount")}
    effective = merge(common, accounts.get(account_id, {}))
    defaults = template["channels"]["awada"]
    target = awada if account_id == "default" and account_id not in accounts else awada.setdefault("accounts", {}).setdefault(account_id, {})
    for key, value in defaults.items():
        if key != "allowFrom" and key not in effective:
            target[key] = value
    if "allowFrom" not in effective:
        policy = args.dm_policy or effective.get("dmPolicy") or defaults["dmPolicy"]
        target["allowFrom"] = ["*"] if policy == "open" else []
    key = os.environ.get(args.key_env, "") if args.replace_key else effective.get("awadaKey") or os.environ.get(args.key_env, "")
    if not isinstance(key, str) or not key.strip() or key.strip().startswith("<"):
        if sys.stdin.isatty():
            key = getpass.getpass("Awada V2 lane key: ").strip()
        else:
            raise ValueError(f"Missing lane key; configure {args.key_env} or enter it interactively")
    if not key.strip() or key.strip().startswith("<"):
        raise ValueError("A placeholder is not a lane key")
    target.update(enabled=True, awadaKey=key.strip())
    awada["enabled"] = True
    for name, value in (("lane", args.lane), ("relayBaseUrl", args.relay_base_url), ("dmPolicy", args.dm_policy), ("allowFrom", args.allow_from), ("groupPolicy", args.group_policy), ("mediaPublicBaseUrl", args.media_public_base_url)):
        if value is not None:
            target[name] = value
    effective = merge({key: value for key, value in awada.items() if key not in ("accounts", "defaultAccount")}, accounts.get(account_id, {}))
    if target is not awada:
        effective = merge(effective, target)
    for name in ("relayBaseUrl", "mediaPublicBaseUrl"):
        if effective.get(name):
            valid_url(effective[name])
    if effective.get("dmPolicy") == "open" and "*" not in effective.get("allowFrom", []):
        raise ValueError('open DM requires allowFrom ["*"]; pass --allow-from "*" explicitly')
    if effective.get("dmPolicy") == "allowlist" and not effective.get("allowFrom"):
        raise ValueError("allowlist DM requires at least one --allow-from")
    plugins = result.setdefault("plugins", {})
    if plugins.get("enabled") is False or "awada" in plugins.get("deny", []):
        raise ValueError("Global plugin policy disables awada; resolve that policy before applying")
    paths = plugins.setdefault("load", {}).setdefault("paths", [])
    plugin_path = str(root / "awada")
    if plugin_path not in paths:
        paths.append(plugin_path)
    if plugins.get("allow") and "awada" not in plugins["allow"]:
        plugins["allow"].append("awada")
    entry = plugins.setdefault("entries", {}).setdefault("awada", {})
    entry["enabled"] = True
    plugin_config = entry.setdefault("config", {})
    if args.commands_file is not None:
        commands_path = Path(args.commands_file).expanduser()
        if not commands_path.is_absolute():
            commands_path = state / commands_path
        commands = json.loads(commands_path.read_text(encoding="utf-8"))
        if not isinstance(commands, dict) or commands.get("version") != 1 or not isinstance(commands.get("commands"), list):
            raise ValueError("Commands file requires version:1 and commands:[]")
        plugin_config["commandsFile"] = str(commands_path) if args.commands_file.startswith("~") else args.commands_file
    workspace = args.workspace.expanduser().resolve() if args.workspace else state / f"workspace-{args.agent_id}"
    if args.agent_id == "sales-cs" and not args.without_customerdb:
        customerdb = plugin_config.get("customerdb", {})
        if customerdb.get("agentId", args.agent_id) != args.agent_id or customerdb.get("accountId", account_id) != account_id:
            raise ValueError("CustomerDB already belongs to another agent/account; use --without-customerdb to preserve it")
        hook_policy = entry.setdefault("hooks", {})
        for permission in ("allowConversationAccess", "allowPromptInjection"):
            if hook_policy.get(permission) is False:
                raise ValueError(f"CustomerDB requires hooks.{permission}; review the explicit deny or use --without-customerdb")
        hook_policy.setdefault("allowConversationAccess", True)
        plugin_config["customerdb"] = {**customerdb, "enabled": True, "agentId": args.agent_id, "accountId": account_id, "workspaceDir": str(workspace)}
    agent_config = result.setdefault("agents", {})
    if "list" in agent_config:
        raise ValueError("Legacy agents.list must be migrated with apply-addons or OpenClaw Doctor before channel setup")
    agents = agent_config.setdefault("entries", {})
    existing = agents.get(args.agent_id)
    if existing is None:
        sample_path = args.agent_sample or root / "crews" / args.agent_id / "openclaw_setting_sample.json"
        sample = render(json.loads(sample_path.read_text(encoding="utf-8")), root, state)
        if sample.get("id") != args.agent_id or "channel" in sample:
            raise ValueError("Agent sample ID mismatch or unsupported top-level channel field")
        sample["workspace"] = str(workspace)
        sample.pop("id")
        agents[args.agent_id] = sample
    elif args.workspace is not None:
        existing["workspace"] = str(workspace)
    elif existing.get("workspace"):
        if args.agent_id == "sales-cs" and not args.without_customerdb:
            plugin_config["customerdb"]["workspaceDir"] = existing["workspace"]
    bindings = result.setdefault("bindings", [])
    for binding in bindings:
        match = binding.get("match", {})
        if match == {"channel": "awada", "accountId": account_id} or (account_id == "default" and match == {"channel": "awada"}):
            if binding.get("agentId") != args.agent_id:
                raise ValueError("This Awada account is bound to another crew; resolve the binding before reassignment")
            match["accountId"] = account_id
            break
    else:
        bindings.append({"agentId": args.agent_id, "match": {"channel": "awada", "accountId": account_id}})
    summary = {"accountId": account_id, "agentId": args.agent_id, "keyConfigured": True,
               "relayBaseUrl": effective.get("relayBaseUrl"), "lane": effective.get("lane", ""),
               "dmPolicy": effective.get("dmPolicy"), "allowFrom": effective.get("allowFrom", []),
               "groupPolicy": effective.get("groupPolicy"), "mediaPublicBaseUrl": effective.get("mediaPublicBaseUrl"),
               "commandsFile": plugin_config.get("commandsFile"), "pluginPath": plugin_path,
               "customerdb": {name: value for name, value in plugin_config.get("customerdb", {}).items()
                              if name in ("enabled", "accountId", "agentId", "workspaceDir")}, "restartsGateway": False}
    return result, summary


def write_config(path: Path, original: bytes, cfg: dict) -> Path:
    backup = path.with_name(f"{path.name}.bak-{time.time_ns()}")
    with backup.open("xb") as stream:
        os.chmod(backup, 0o600)
        stream.write(original)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(cfg, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if path.read_bytes() != original:
            raise ValueError("Config changed during preparation; rerun against the current file")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return backup


def main():
    args = arguments()
    try:
        args.config = args.config.expanduser().resolve()
        original = args.config.read_bytes()
        cfg = json.loads(original)
        updated, summary = build(cfg, args)
        summary["dryRun"] = args.dry_run
        if not args.dry_run and updated != cfg:
            summary["backup"] = str(write_config(args.config, original, updated))
        summary["changed"] = updated != cfg
        summary["path"] = str(args.config)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        print(f"awada-channel-setup: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
