import type { InboundEvent } from "./redis-types.js";

/** Qiwe callbacks carry the receiving bot's userId and structured mentions in provider_raw. */
export function prepareAwadaMentions(event: InboundEvent): InboundEvent {
  if (event.meta.platform !== "qiweapi" || !event.meta.provider_raw) return event;
  const raw = event.meta.provider_raw;
  const botId = raw.userId === undefined ? "" : String(raw.userId);
  const data = raw.msgData;
  const parts = Array.isArray(data) ? data.map((part) => part?.subMsgData) : [data];
  const mentions = parts
    .flatMap((part) => (Array.isArray(part?.atList) ? part.atList : []))
    .filter((entry): entry is { userId: unknown; nickname: string } =>
      Boolean(entry && typeof entry === "object" && typeof entry.nickname === "string"),
    );
  const replacements = new Map<string, string>();
  const escapeHtml = (value: string) =>
    value
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  for (const mention of mentions) {
    if (!mention.nickname || mention.userId === undefined) continue;
    const id = String(mention.userId);
    replacements.set(
      `@${mention.nickname}`,
      botId && id === botId
        ? ""
        : `<at user_id="${escapeHtml(id)}">${escapeHtml(mention.nickname)}</at>`,
    );
  }
  const keys = [...replacements.keys()]
    .sort((a, b) => b.length - a.length)
    .map((key) => key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  // A single pass, as in Feishu, avoids interpreting display names as more mention keys.
  const pattern = keys.length ? new RegExp(`(${keys.join("|")})(?=\\s|$)`, "gu") : undefined;
  return {
    ...event,
    meta: {
      ...event.meta,
      at_me:
        event.meta.at_me === true ||
        Boolean(botId && mentions.some((mention) => String(mention.userId) === botId)),
      sender_name:
        event.meta.sender_name ?? (typeof raw.senderName === "string" ? raw.senderName : undefined),
    },
    payload: pattern
      ? event.payload.map((item) =>
          item.type === "text"
            ? { ...item, text: item.text.replace(pattern, (key) => replacements.get(key)!).trim() }
            : item,
        )
      : event.payload,
  };
}
