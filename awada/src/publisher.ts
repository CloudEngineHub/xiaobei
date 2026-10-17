import type { ClawdbotConfig } from "./runtime-api.js";
import { resolveAwadaAccount } from "./accounts.js";
import { buildOutboundTarget, postOutbound } from "./send.js";

/**
 * Publish a proactive (non-reply) text message to an awada platform.
 *
 * Use this when the agent initiates a message rather than responding to an inbound event.
 * The caller must supply the target user details explicitly. Routed via relay
 * POST /outbound (docs/AWADA-CLIENT-TRANSPORT.md §3).
 */
export async function publishTextToAwada(params: {
  cfg: ClawdbotConfig;
  accountId?: string;
  /** Target user external ID (e.g. wxid or worktool userId) */
  userId: string;
  /** Channel ID from the platform (e.g. weixin room or conversation id) */
  channelId: string;
  /** Tenant ID (use empty string if not applicable) */
  tenantId?: string;
  text: string;
}): Promise<string> {
  const { cfg, accountId, userId, channelId, tenantId = "", text } = params;

  const account = resolveAwadaAccount({ cfg, accountId });
  if (!account.relayBaseUrl || !account.awadaKey) {
    throw new Error("[awada] not configured (need awadaKey)");
  }

  // platform is omitted — the relay derives it from the lane binding (provisioned server-side).
  const target = buildOutboundTarget({
    lane: account.lane,
    user_id_external: userId,
    channel_id: channelId,
    tenant_id: tenantId,
  });

  const result = await postOutbound({
    relayBaseUrl: account.relayBaseUrl,
    awadaKey: account.awadaKey,
    lane: account.lane,
    target,
    payload: [{ type: "text", text }],
  });
  return result.eventId;
}
