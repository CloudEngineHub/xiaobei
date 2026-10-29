#!/usr/bin/env python3
"""Offline, fail-closed XHS IM reply eligibility and durable message deduplication.

check never writes. record reserves an incoming message even for unknown outcomes;
there is intentionally no date expiry. This helper never sends or marks messages.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile

NAMESPACE = "xhs_im_reply_guard"
OUTCOMES = {"submitted", "confirmed", "unknown", "platform_notice"}
NOTICE_FIELDS = ("messageSource", "customDefaultTemplateName", "defaultTitle", "defaultSubTitle")


class Unsafe(ValueError):
    pass


def ident(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).strip():
        raise Unsafe("missing_identifier")
    return str(value)


def number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not re.fullmatch(r"[0-9]+", str(value)):
        raise Unsafe("invalid_message_order")
    return int(value)


def decode(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


def notices(value, depth=0):
    if depth > 12:
        return []
    value = decode(value)
    found = []
    if isinstance(value, dict):
        if (value.get("messageSource") == "c2cbusiness_system"
                or value.get("customDefaultTemplateName") == "im_c2c_warning_card"):
            # Fixed structured metadata only, never customer body or identity.
            found.append({k: value[k] for k in NOTICE_FIELDS if isinstance(value.get(k), str)})
        for child in value.values():
            if isinstance(child, (dict, list, str)):
                found.extend(notices(child, depth + 1))
    elif isinstance(value, list):
        for child in value:
            found.extend(notices(child, depth + 1))
    return found


def messages_from(value):
    for _ in range(8):
        if not isinstance(value, dict):
            raise Unsafe("invalid_history")
        if value.get("ok") is False or value.get("success") is False:
            raise Unsafe("history_request_failed")
        if "code" in value and value["code"] not in (0, "0", 200, "200"):
            raise Unsafe("history_request_failed")
        if isinstance(value.get("result"), dict) and value["result"].get("success") is False:
            raise Unsafe("history_request_failed")
        for key in ("out_message_list", "messages"):
            if key in value:
                if not isinstance(value[key], list):
                    raise Unsafe("invalid_history")
                return value[key]
        value = value.get("data")
    raise Unsafe("invalid_history")


def load_ledger(path):
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        raise Unsafe("invalid_ledger")
    if not isinstance(value, dict):
        raise Unsafe("invalid_ledger")
    if "conversations" in value:
        if not isinstance(value["conversations"], list) or any(
                not isinstance(row, dict) or not isinstance(row.get("user_id"), (str, int))
                for row in value["conversations"]):
            raise Unsafe("invalid_ledger")
    if NAMESPACE in value:
        section = value[NAMESPACE]
        if not isinstance(section, dict) or section.get("version") != 1 or not isinstance(section.get("records"), list):
            raise Unsafe("invalid_ledger")
        for row in section["records"]:
            if not isinstance(row, dict) or row.get("outcome") not in OUTCOMES - {"platform_notice"}:
                raise Unsafe("invalid_ledger")
            ident(row.get("conversation"))
            number(row.get("incoming_id"))
        states = section.get("notices", {})
        if not isinstance(states, dict):
            raise Unsafe("invalid_ledger")
        for key, state in states.items():
            ident(key)
            if not isinstance(state, dict) or state.get("suppress_external_guidance") is not True:
                raise Unsafe("invalid_ledger")
            number(state.get("last_notice_id"))
    return value


def check(conversation, history, ledger_path):
    result = dict(ok=False, should_reply=False, reason="invalid_history",
                  last_customer_message_id=None, last_notice_id=None, platform_notice=[], suppress_external_guidance=False)
    try:
        conversation = ident(conversation)
        ledger = load_ledger(ledger_path)
        notice_state = ledger.get(NAMESPACE, {}).get("notices", {}).get(conversation, {})
        if notice_state.get("suppress_external_guidance"):
            result["suppress_external_guidance"] = True
            result["last_notice_id"] = notice_state["last_notice_id"]
        messages = messages_from(history)
        # Inspect cards before validation so warning policy survives malformed history.
        for message in messages:
            if isinstance(message, dict):
                for notice in notices(message.get("content")):
                    if notice not in result["platform_notice"]:
                        result["platform_notice"].append(notice)
                    result["suppress_external_guidance"] = True
                    mid = str(number(message.get("store_id")))
                    if result["last_notice_id"] is None or int(mid) > int(result["last_notice_id"]):
                        result["last_notice_id"] = mid
        result["suppress_external_guidance"] = result["suppress_external_guidance"] or bool(result["platform_notice"])
        incoming, outgoing, seen = [], [], {}
        for message in messages:
            if not isinstance(message, dict):
                raise Unsafe("invalid_history")
            if message.get("group_chat") is True or message.get("revoked") is True:
                continue
            if message.get("group_chat") is not False or message.get("revoked") is not False:
                raise Unsafe("missing_message_flags")
            content = decode(message.get("content"))
            if not isinstance(content, dict) or type(content.get("content_type")) is not int:
                raise Unsafe("invalid_message_content")
            if notices(content):
                continue
            sender, receiver = ident(message.get("sender_id")), ident(message.get("receiver_id"))
            if sender == receiver or conversation not in (sender, receiver):
                raise Unsafe("ambiguous_message_direction")
            mid = str(number(message.get("store_id")))
            order = (number(message.get("created_at")), int(mid))
            if mid in seen:
                if seen[mid] != message:
                    raise Unsafe("conflicting_message_id")
                continue
            seen[mid] = message
            if sender != conversation:
                outgoing.append(order)
            elif content["content_type"] == 1:
                body = content.get("content")
                # Structured/system payloads cannot masquerade as human text.
                if not isinstance(body, str):
                    raise Unsafe("invalid_text_content")
                if isinstance(decode(body), (dict, list)):
                    continue
                if any(char.isalnum() for char in body):
                    incoming.append((order, mid))
        latest = max(incoming, default=None)
        if latest:
            result["last_customer_message_id"] = latest[1]
        result["ok"] = True
        if any(str(row["user_id"]) == conversation for row in ledger.get("conversations", [])):
            result["reason"] = "legacy_ledger_requires_review"
        elif not latest:
            result["reason"] = "no_customer_text"
        elif outgoing and latest[0] <= max(outgoing):
            result["reason"] = "already_replied"
        elif any(str(row["conversation"]) == conversation and str(number(row["incoming_id"])) == latest[1]
                 for row in ledger.get(NAMESPACE, {}).get("records", [])):
            result["reason"] = "message_already_recorded"
        else:
            result.update(should_reply=True, reason="new_customer_text")
    except (Unsafe, OSError, ValueError, TypeError) as exc:
        result.update(ok=False, should_reply=False, reason=str(exc) if isinstance(exc, Unsafe) else "invalid_input")
    return result


def record(conversation, incoming_id, ledger_path, outcome, outgoing_id=None):
    conversation, incoming_id = ident(conversation), str(number(incoming_id))
    if outcome not in OUTCOMES:
        raise Unsafe("invalid_outcome")
    if outgoing_id is not None:
        outgoing_id = ident(outgoing_id)
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Stable sidecar lock: locking the replaced ledger inode is not sufficient.
    fd = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(fd, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        ledger = load_ledger(path)
        section = ledger.setdefault(NAMESPACE, {"version": 1, "records": []})
        records = section["records"]
        if outcome == "platform_notice":
            states = section.setdefault("notices", {})
            previous = states.get(conversation)
            duplicate = previous is not None
            last_id = str(max(int(incoming_id), int(previous["last_notice_id"]))) if previous else incoming_id
            states[conversation] = dict(last_notice_id=last_id, suppress_external_guidance=True)
            row = dict(outcome=outcome)
        else:
            duplicate, row = update_record(records, conversation, incoming_id, outcome, outgoing_id)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                             prefix="." + path.name + ".", delete=False) as handle:
                temporary = handle.name
                json.dump(ledger, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            temporary = None
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if temporary is not None:
                os.unlink(temporary)
    return dict(ok=True, recorded=True, already_recorded=duplicate,
                conversation=conversation, incoming_id=incoming_id, outcome=row["outcome"])


def update_record(records, conversation, incoming_id, outcome, outgoing_id):
    row = next((r for r in records if str(r["conversation"]) == conversation
                and str(number(r["incoming_id"])) == incoming_id), None)
    duplicate = row is not None
    if row is None:
        row = dict(conversation=conversation, incoming_id=incoming_id, outcome=outcome)
        records.append(row)
    elif row["outcome"] != "confirmed":
        row["outcome"] = outcome
    if outgoing_id is not None:
        row["outgoing_id"] = outgoing_id
    return duplicate, row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check_parser = sub.add_parser("check", help="read-only eligibility check")
    record_parser = sub.add_parser("record", help="durably reserve/record an incoming message")
    for command in (check_parser, record_parser):
        command.add_argument("--conversation", required=True)
        command.add_argument("--ledger", required=True)
    check_parser.add_argument("--history-file", required=True)
    record_parser.add_argument("--incoming-id", required=True)
    record_parser.add_argument("--outcome", required=True, choices=sorted(OUTCOMES))
    record_parser.add_argument("--outgoing-id")
    args = parser.parse_args()
    try:
        if args.command == "check":
            try:
                with open(args.history_file, encoding="utf-8") as handle:
                    history = json.load(handle)
            except (OSError, ValueError):
                history = None
            result = check(args.conversation, history, args.ledger)
        else:
            result = record(args.conversation, args.incoming_id, args.ledger, args.outcome, args.outgoing_id)
    except (Unsafe, OSError, ValueError, TypeError):
        result = dict(ok=False, recorded=False, reason="invalid_ledger_or_record")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
