import { stripReasoningTagsFromText } from "openclaw/plugin-sdk/text-chunking";
import type { ReplyPayload } from "./runtime-api.js";
import { getAwadaRuntime } from "./runtime.js";

/** Customer channels keep host failure notices in operator logs. */
export function filterAwadaReply(params: {
  payload: ReplyPayload;
  accountId?: string | null;
  inboundEventId?: string;
  requestId?: string;
}): ReplyPayload | null {
  const text = stripReasoningTagsFromText(params.payload.text ?? "").trimStart();
  const match = /^⚠\uFE0F?\s+OpenClaw couldn['’]t (produce or deliver a reply|finish this reply)\./u.exec(
    text,
  );
  if (!match) return params.payload;
  getAwadaRuntime().logging.getChildLogger({ subsystem: "awada" }).warn(
    "Suppressed OpenClaw failure reply on customer channel",
    {
      code: "openclaw_failure_reply_suppressed",
      notice: match[1] === "finish this reply" ? "reply_failed" : "no_visible_reply",
      accountId: params.accountId ?? undefined,
      inboundEventId: params.inboundEventId,
      requestId: params.requestId,
      reference: /\bReference: ([a-z0-9][a-z0-9_-]{0,127})\./iu.exec(text)?.[1],
    },
  );
  return null;
}
