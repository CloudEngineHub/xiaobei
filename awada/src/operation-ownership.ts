import type { ClawdbotConfig, OpenClawPluginApi } from "./runtime-api.js";
import { listAwadaAccountIds, resolveAwadaAccount } from "./accounts.js";
import { awadaSessionOwner, claimAwadaOperation, retainAwadaMessageClaims } from "./ledger.js";

function receiptIds(value: unknown, ids = new Set<string>(), depth = 0): Set<string> {
  if (!value || typeof value !== "object" || depth > 10) return ids;
  if (Array.isArray(value)) {
    for (const item of value) receiptIds(item, ids, depth + 1);
    return ids;
  }
  for (const [key, item] of Object.entries(value)) {
    if (
      ["eventId", "messageId", "platformMessageId", "primaryPlatformMessageId"].includes(key) &&
      typeof item === "string"
    )
      ids.add(item);
    else if (
      ["operationIds", "messageIds", "platformMessageIds"].includes(key) &&
      Array.isArray(item)
    ) {
      for (const id of item) if (typeof id === "string") ids.add(id);
    } else if (key !== "content") receiptIds(item, ids, depth + 1);
  }
  return ids;
}

/** Observe host message receipts without changing standard media or routing behavior. */
export function registerAwadaMessageOwnership(api: OpenClawPluginApi): void {
  api.on(
    "after_tool_call",
    async (event, ctx) => {
      const owner = awadaSessionOwner(ctx);
      if (!owner || event.error || event.toolName !== "message" || event.params.action !== "send")
        return;
      const details = (
        event.result as
          | { details?: { channel?: string; result?: { channel?: string } } }
          | undefined
      )?.details;
      if (
        event.params.channel !== "awada" &&
        details?.channel !== "awada" &&
        details?.result?.channel !== "awada"
      )
        return;
      await retainAwadaMessageClaims(owner, async () => {
        // The host may infer the destination account without copying it into hook params.
        // Only the account whose local outbound ledger contains this exact ID admits a claim.
        const cfg = api.runtime.config.current() as ClawdbotConfig;
        const ids = receiptIds(event.result);
        for (const accountId of listAwadaAccountIds(cfg)) {
          const account = resolveAwadaAccount({ cfg, accountId });
          if (!account.enabled || !account.configured || !account.awadaKey || !account.relayBaseUrl)
            continue;
          for (const id of ids)
            await claimAwadaOperation(
              {
                relayBaseUrl: account.relayBaseUrl,
                awadaKey: account.awadaKey,
                lane: account.lane,
              },
              id,
              owner,
            );
        }
      });
    },
    { matcher: ["message"] },
  );
}
