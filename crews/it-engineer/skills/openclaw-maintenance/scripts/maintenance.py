#!/usr/bin/env python3
"""Bounded JSON log review and native Automation scratch snapshots/CAS writes."""
import argparse
from collections import Counter, deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess


def cli_json(arguments):
    entry = os.environ.get("XIAOBEI_OPENCLAW_ENTRY")
    executable = os.environ.get("XIAOBEI_OPENCLAW_CLI") or shutil.which("openclaw")
    if entry:
        command = ["node", str(Path(entry).expanduser())]
    elif executable:
        command = [str(Path(executable).expanduser())]
    else:
        raise ValueError("set XIAOBEI_OPENCLAW_CLI or XIAOBEI_OPENCLAW_ENTRY from OFB_ENV.md")
    result = subprocess.run(command + arguments, capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise ValueError(f"native CLI failed (exit {result.returncode}): {result.stderr.strip()[:1200]}")
    # Do not guess JSON boundaries around unexpected stdout banners.
    return json.loads(result.stdout)


def instant(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include an explicit UTC offset or Z")
    return parsed.astimezone(timezone.utc)


def logs(args):
    start, end = instant(args.since), instant(args.until)
    if start >= end:
        raise ValueError("since must precede until")
    if args.file:
        logfile = Path(args.file).expanduser().absolute()
    else:
        config = cli_json(["config", "get", "logging", "--json"])
        configured = config.get("file")
        state_dir = Path(os.environ.get("OPENCLAW_STATE_DIR") or Path.home() / ".openclaw")
        logfile = Path(configured).expanduser() if configured else state_dir / "logs/gateway.log"
        if not logfile.is_absolute():
            raise ValueError("logging.file is relative; pass the resolved active path with --file")
    levels = Counter()
    issues = Counter()
    examples = deque(maxlen=args.examples)
    files = []
    warnings = []
    first = last = None
    malformed = matches = 0
    for number in range(5, -1, -1):
        path = Path(f"{logfile}.{number}") if number else logfile
        if not path.exists():
            if number == 0:
                warnings.append(f"active log missing: {path}")
            continue
        stats = {"path": str(path), "lines": 0, "matched": 0}
        files.append(stats)
        try:
            with path.open(encoding="utf-8") as stream:
                for line_number, line in enumerate(stream, 1):
                    stats["lines"] += 1
                    try:
                        item = json.loads(line)
                        timestamp = instant(item["time"])
                    except (ValueError, KeyError, TypeError):
                        malformed += 1
                        continue
                    first = timestamp if first is None else min(first, timestamp)
                    last = timestamp if last is None else max(last, timestamp)
                    if not start <= timestamp < end:
                        continue
                    matches += 1
                    stats["matched"] += 1
                    meta = item.get("_meta") or {}
                    if not isinstance(meta, dict):
                        meta = {}
                    level = str(meta.get("logLevelName") or item.get("level") or "UNKNOWN").upper()
                    levels[level] += 1
                    message = item.get("message")
                    if message is None:
                        message = " ".join(str(item[key]) for key in sorted(item) if key.isdigit())
                    if level in {"WARN", "WARNING", "ERROR", "FATAL", "4", "5", "6", "40", "50", "60"}:
                        # Keep raw wording; grouping must not conflate distinct causes.
                        issues[str(message)[:1000]] += 1
                        examples.append({"file": str(path), "line": line_number,
                                         "time": item["time"], "level": level, "message": str(message)[:2000]})
        except (OSError, UnicodeError) as error:
            warnings.append(f"incomplete read: {path}: {error}")
    if malformed:
        warnings.append(f"{malformed} lines could not be parsed/timed; counts may be incomplete")
    if first is None or first > start:
        warnings.append("available logs do not establish coverage from window start")
    if not matches:
        warnings.append("no records in requested window; this does not prove a healthy service")
    return {"file": str(logfile), "since": start.isoformat(), "untilExclusive": end.isoformat(),
            "files": files, "firstObserved": first.isoformat() if first else None,
            "lastObserved": last.isoformat() if last else None, "recordsInWindow": matches,
            "levels": levels, "topMessages": issues.most_common(30), "examples": list(examples),
            "warnings": warnings, "scope": "configured file and numbered rotations .1-.5 only"}


def scratch_save(args):
    response = cli_json(["automations", "scratch", args.job, "--json"])
    revision = response["currentRevision"]
    if type(revision) is not int or revision < 0:
        raise ValueError("invalid scratch revision")
    output = Path(args.output).expanduser().absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump({"jobId": args.job, "capturedAt": datetime.now(timezone.utc).isoformat(),
                   "response": response}, stream, ensure_ascii=False, indent=2)
    return {"path": str(output), "jobId": args.job, "revision": revision}


def scratch_replace(args):
    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    job_id = snapshot["jobId"]
    revision = snapshot["response"]["currentRevision"]
    if not isinstance(job_id, str) or not job_id or type(revision) is not int or revision < 0:
        raise ValueError("invalid scratch snapshot")
    content = Path(args.file).expanduser().resolve(strict=True)
    # Native CLI owns size validation, authority and compare-and-swap. Never
    # silently retry a conflict or restore this content to a different job.
    result = cli_json(["automations", "scratch", job_id, "--file", str(content),
                       "--expected-revision", str(revision), "--json"])
    if result.get("ok") is not True:
        raise ValueError("scratch write not confirmed; reread before any retry")
    try:
        current = cli_json(["automations", "scratch", job_id, "--json"])
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        raise ValueError("scratch write was accepted, but readback failed; read current scratch before any further edit; do not replay the write") from error
    return {"jobId": job_id, "write": result, "readback": current,
            "note": "write accepted; inspect readback for subsequent concurrent edits"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    log = commands.add_parser("logs")
    log.add_argument("--file", help="resolved active log path, including when Gateway is unavailable")
    log.add_argument("--since", required=True, help="ISO timestamp with timezone")
    log.add_argument("--until", required=True, help="exclusive ISO timestamp with timezone")
    log.add_argument("--examples", type=int, default=15, choices=range(0, 101), metavar="0..100")
    log.set_defaults(run=logs)
    save = commands.add_parser("scratch-save")
    save.add_argument("--job", required=True)
    save.add_argument("--output", required=True)
    save.set_defaults(run=scratch_save)
    replace = commands.add_parser("scratch-replace")
    replace.add_argument("--snapshot", required=True)
    replace.add_argument("--file", required=True, help="complete merged replacement text")
    replace.set_defaults(run=scratch_replace)
    args = parser.parse_args()
    try:
        print(json.dumps(args.run(args), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"openclaw-maintenance: {error}\n")


if __name__ == "__main__":
    main()
