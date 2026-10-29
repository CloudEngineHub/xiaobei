"""Python entry to the shared browser client through Node; no shell or npm lookup."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Mapping, Sequence


class BrowserError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def request(
    action: str,
    params: Mapping[str, Any] | None = None,
    *,
    session: str = "default",
    node: str | None = None,
    runtime_root: str | Path | None = None,
    home: str | Path | None = None,
    launch_args: Sequence[str] = (),
    request_id: str | None = None,
    lease_token: str | None = None,
    timeout: float = 75,
) -> dict[str, Any]:
    """Return v1 data or raise BrowserError. Never retry an uncertain operation.

    Distributions should supply their portable node executable explicitly.
    home selects test state; omitting it preserves the runtime's usual state home.
    launch_args accepts explicit launch flags, e.g. ("--headed", "--persistent").
    """
    executable = node or os.environ.get("XIAOBEI_BROWSER_NODE") or shutil.which("node")
    if not executable:
        raise BrowserError("NODE_MISSING", "Node executable was not found")
    root = Path(runtime_root) if runtime_root else Path(__file__).resolve().parents[1]
    entry = root / "dist" / "cli.js"
    if not entry.is_file():
        raise BrowserError("RUNTIME_MISSING", "Browser CLI is not built or distributed")
    body: dict[str, Any] = {"action": action, "params": dict(params or {})}
    if request_id is not None:
        body["requestId"] = request_id
    argv = [str(executable), str(entry), "--session", session, *launch_args,
            "--request-stdin", "--json"]
    if lease_token is not None:
        argv.extend(["--lease-token", lease_token])
    env = os.environ.copy()
    if home is not None:
        env["XIAOBEI_BROWSER_HOME"] = str(home)
        env["CAMOUFOX_CLI_CONFIG"] = str(Path(home) / "config.json")
    try:
        completed = subprocess.run(argv, input=json.dumps(body, ensure_ascii=False),
                                   capture_output=True, text=True, encoding="utf-8",
                                   env=env, timeout=timeout, shell=False)
    except subprocess.TimeoutExpired as exc:
        raise BrowserError("OUTCOME_UNKNOWN", "CLI timed out; query status/result before taking further action") from exc
    except OSError as exc:
        raise BrowserError("CLI_UNAVAILABLE", "Could not start the browser CLI") from exc
    try:
        response = json.loads(completed.stdout)
        if not isinstance(response, dict) or response.get("protocolVersion") != 1 or type(response.get("ok")) is not bool:
            raise ValueError("Invalid protocol")
    except (ValueError, TypeError) as exc:
        raise BrowserError("OUTCOME_UNKNOWN", "CLI returned no valid v1 result; do not automatically retry") from exc
    if not response["ok"]:
        error = response.get("error") or {}
        raise BrowserError(str(error.get("code", "ACTION_FAILED")), str(error.get("message", "Browser action failed")))
    if completed.returncode:
        raise BrowserError("OUTCOME_UNKNOWN", "CLI exited abnormally after returning a result")
    return response.get("data") or {}
