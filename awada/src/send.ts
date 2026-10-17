import type { ContentObject, MediaObject, OutboundMeta, OutboundTarget } from "./redis-types.js";
import { randomUUID } from "node:crypto";
import { awadaRequest, type OperationReceipt } from "./api.js";
import { withAwadaSubmissionLedger } from "./ledger.js";

/**
 * Outbound send — POST /api/v2/awada/outbound?lane=<lane> to the relay gateway.
 * See docs/AWADA-CLIENT-TRANSPORT.md. The relay writes the event onto the outbound
 * Redis stream and the awada-server dispatcher delivers it back to the platform.
 *
 * The configured lane owns provider/account routing. Conversation and recipient IDs
 * come from the standard target; replies also retain their source_event_id.
 */
export type GatewaySendParams = {
  relayBaseUrl: string;
  awadaKey: string;
  lane: string;
  target: OutboundTarget;
  payload: ContentObject[];
  /** event_id of the inbound event that triggered this reply (for correlation/tracing). */
  sourceEventId?: string;
  requestId?: string;
  beforeSend?: () => void | Promise<void>;
  signal?: AbortSignal;
};

export function encodeAwadaTo(target: OutboundTarget): string {
  return `awada:${Buffer.from(JSON.stringify(target)).toString("base64")}`;
}

export function decodeAwadaTo(to: string): OutboundTarget | null {
  if (!to.startsWith("awada:")) return null;
  try {
    const target = JSON.parse(Buffer.from(to.slice(6), "base64").toString("utf8"));
    if (
      !target ||
      typeof target !== "object" ||
      !["tenant_id", "lane", "user_id_external", "channel_id"].every(
        (key) => typeof target[key] === "string",
      )
    )
      return null;
    return target as OutboundTarget;
  } catch {
    return null;
  }
}

export function buildOutboundTarget(meta: {
  lane: string;
  tenant_id: string;
  channel_id: string;
  user_id_external: string;
  platform?: string;
  conversation_id?: string;
}): OutboundTarget {
  const target: OutboundTarget = {
    tenant_id: meta.tenant_id,
    lane: meta.lane,
    user_id_external: meta.user_id_external,
    channel_id: meta.channel_id,
  };
  if (meta.platform) target.platform = meta.platform;
  if (meta.conversation_id) {
    target.conversation_id = meta.conversation_id;
  }
  return target;
}

/** Build the OutboundMeta required by POST /outbound from a target + source event id. */
export function buildOutboundMeta(target: OutboundTarget, sourceEventId?: string): OutboundMeta {
  const meta: OutboundMeta = {
    channel_id: target.channel_id,
    user_id_external: target.user_id_external,
  };
  if (target.platform) meta.platform = target.platform;
  if (target.tenant_id) meta.tenant_id = target.tenant_id;
  if (target.conversation_id) meta.session_id = target.conversation_id;
  if (sourceEventId) meta.source_event_id = sourceEventId;
  if (target.action_ask) meta.action_ask = target.action_ask;
  return meta;
}

export async function postOutbound(
  params: GatewaySendParams,
): Promise<{ streamId: string; eventId: string }> {
  const { relayBaseUrl, awadaKey, lane, target, payload, sourceEventId } = params;
  const meta = buildOutboundMeta(target, sourceEventId);
  if (payload.length < 1 || payload.length > 100)
    throw new Error("Awada payload must contain 1–100 objects");
  const credentials = { relayBaseUrl, awadaKey, lane };
  const requestId = params.requestId ?? randomUUID();
  const body = { payload, meta, request_id: requestId };
  const receipt = await withAwadaSubmissionLedger(credentials, requestId, body, async () => {
    await params.beforeSend?.();
    params.signal?.throwIfAborted();
    return awadaRequest<OperationReceipt>(credentials, "/outbound", {
      body,
      signal: params.signal,
    });
  });
  if (!receipt.eventId || !receipt.streamId)
    throw new Error("Awada returned an invalid enqueue receipt");
  return receipt;
}

export async function sendTextToAwada(params: {
  relayBaseUrl: string;
  awadaKey: string;
  lane: string;
  target: OutboundTarget;
  text: string;
  sourceEventId?: string;
  requestId?: string;
}): Promise<string> {
  const { relayBaseUrl, awadaKey, lane, target, text, sourceEventId } = params;
  const result = await postOutbound({
    relayBaseUrl,
    awadaKey,
    lane,
    target,
    payload: [{ type: "text", text }],
    sourceEventId,
    requestId: params.requestId,
  });
  return result.eventId;
}

/**
 * Send a media item (file, image, or audio) to the relay outbound endpoint.
 */
export async function sendMediaToAwada(params: {
  relayBaseUrl: string;
  awadaKey: string;
  lane: string;
  target: OutboundTarget;
  media: ContentObject;
  sourceEventId?: string;
  requestId?: string;
}): Promise<string> {
  const { relayBaseUrl, awadaKey, lane, target, media, sourceEventId } = params;
  const result = await postOutbound({
    relayBaseUrl,
    awadaKey,
    lane,
    target,
    payload: [media],
    sourceEventId,
    requestId: params.requestId,
  });
  return result.eventId;
}

const IMAGE_EXTENSIONS = new Set([".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"]);

/**
 * Build a ContentObject from a URL.
 * file_name is extracted from the URL path; file_url is set to the URL.
 * Type is determined by extension: image extensions → ImageObject, everything else → FileObject.
 */
export function buildMediaContentFromUrl(url: string): MediaObject {
  const pathname = new URL(url).pathname;
  const raw = pathname.split("/").pop() ?? "";
  const file_name = raw || "file";
  const ext = file_name.slice(file_name.lastIndexOf(".")).toLowerCase();
  if (IMAGE_EXTENSIONS.has(ext)) {
    return { type: "image", file_name, file_url: url };
  }
  if ([".mp4", ".mov", ".webm", ".m4v"].includes(ext))
    return { type: "video", file_name, file_url: url };
  return { type: "file", file_name, file_url: url };
}
