import type { ChannelOutboundAdapter } from "openclaw/plugin-sdk/core";
import {
  loadOutboundMediaFromUrl,
  type OutboundMediaLoadOptions,
} from "openclaw/plugin-sdk/outbound-media";
import { resolveSendableOutboundReplyParts } from "openclaw/plugin-sdk/reply-payload";
import { stripReasoningTagsFromText } from "openclaw/plugin-sdk/text-chunking";
import type { ClawdbotConfig, ReplyPayload } from "./runtime-api.js";
import type { ContentObject, OutboundTarget } from "./redis-types.js";
import { resolveAwadaAccount } from "./accounts.js";
import { getAwadaRuntime } from "./runtime.js";
import { buildMediaContentFromUrl, decodeAwadaTo, postOutbound } from "./send.js";
import { MAX_UPLOAD_BYTES } from "./api.js";
import { prepareAwadaHostedMedia } from "./hosted-media.js";
import { encodeAwadaVoice } from "./voice.js";
import { filterAwadaReply } from "./reply-filter.js";
import {
  defineChannelMessageAdapter,
  createMessageReceiptFromOutboundResults,
} from "openclaw/plugin-sdk/channel-outbound";

export function resolveAwadaSendTarget(
  to: string,
  accountId: string,
  lane: string,
): OutboundTarget {
  const encoded = decodeAwadaTo(to);
  if (encoded) return encoded;
  const match = to.replace(/^awada:/, "").match(/^(user|chat):(.+)$/s);
  if (!match) throw new Error("Awada target must be user:<id> or chat:<id>");
  return {
    tenant_id: "",
    lane,
    user_id_external: match[1] === "user" ? match[2]! : "",
    channel_id: match[1] === "chat" ? match[2]! : "0",
  };
}

/** Leave headroom for routing metadata while respecting both V2 payload limits. */
export function splitAwadaContent(
  parts: ContentObject[],
  maxBytes = 32 * 1024 * 1024 - 64 * 1024,
): ContentObject[][] {
  const batches: ContentObject[][] = [];
  let current: ContentObject[] = [];
  let bytes = 2;
  for (const part of parts) {
    const size = Buffer.byteLength(JSON.stringify(part)) + 1;
    if (size + 2 > maxBytes) throw new Error("Awada content object exceeds the request limit");
    if (current.length && (current.length >= 100 || bytes + size > maxBytes)) {
      batches.push(current);
      current = [];
      bytes = 2;
    }
    current.push(part);
    bytes += size;
  }
  if (current.length) batches.push(current);
  return batches;
}

async function mediaContent(params: {
  cfg: ClawdbotConfig;
  accountId?: string;
  target: OutboundTarget;
  mediaUrl: string;
  mediaAccess?: OutboundMediaLoadOptions["mediaAccess"];
  mediaLocalRoots?: readonly string[];
  mediaReadFile?: (filePath: string) => Promise<Buffer>;
  audioAsVoice?: boolean;
  forceDocument?: boolean;
}): Promise<ContentObject> {
  if (/^https?:\/\//i.test(params.mediaUrl) && !params.audioAsVoice) {
    const content = buildMediaContentFromUrl(params.mediaUrl);
    return params.forceDocument ? { ...content, type: "file" } : content;
  }
  const account = resolveAwadaAccount({ cfg: params.cfg, accountId: params.accountId });
  if (!account.relayBaseUrl || !account.awadaKey) throw new Error("Awada is not configured");
  const maxBytes = Math.min(MAX_UPLOAD_BYTES, (account.config.mediaMaxMb ?? 20) * 1024 * 1024);
  if (account.config.mediaPublicBaseUrl && !params.audioAsVoice) {
    if (/^https?:\/\//i.test(params.mediaUrl)) return buildMediaContentFromUrl(params.mediaUrl);
    const url = await prepareAwadaHostedMedia({
      accountId: account.accountId,
      lane: account.lane,
      publicBaseUrl: account.config.mediaPublicBaseUrl,
      mediaUrl: params.mediaUrl,
      maxBytes,
      mediaAccess: params.mediaAccess,
      mediaLocalRoots: params.mediaLocalRoots,
      mediaReadFile: params.mediaReadFile,
    });
    const content = buildMediaContentFromUrl(url);
    const filename = params.mediaUrl.split(/[\\/]/).pop() ?? "attachment";
    return {
      ...content,
      type: params.forceDocument
        ? "file"
        : /\.(?:jpg|jpeg|png|gif)$/i.test(filename)
          ? "image"
          : /\.(?:mp4|mov|webm)$/i.test(filename)
            ? "video"
            : "file",
      file_name: filename,
    };
  }
  const loaded = await loadOutboundMediaFromUrl(params.mediaUrl, {
    maxBytes,
    mediaAccess: params.mediaAccess,
    mediaLocalRoots: params.mediaLocalRoots,
    mediaReadFile: params.mediaReadFile,
  });
  if (params.audioAsVoice && !params.forceDocument)
    return {
      type: "audio",
      file_name: "voice.silk",
      ...(await encodeAwadaVoice(loaded.buffer, maxBytes)),
    };
  const type = params.forceDocument
    ? "file"
    : loaded.contentType?.startsWith("image/")
      ? "image"
      : loaded.contentType?.startsWith("video/")
        ? "video"
        : "file";
  return {
    type,
    file_name: loaded.fileName ?? params.mediaUrl.split(/[\\/]/).pop() ?? "attachment",
    base64: loaded.buffer.toString("base64"),
  };
}

export async function deliverAwadaReply(params: {
  cfg: ClawdbotConfig;
  accountId?: string;
  target: OutboundTarget;
  payload: ReplyPayload;
  inboundEventId?: string;
  requestId?: string;
  mediaAccess?: OutboundMediaLoadOptions["mediaAccess"];
  mediaLocalRoots?: readonly string[];
  mediaReadFile?: (filePath: string) => Promise<Buffer>;
  forceDocument?: boolean;
  beforeSend?: () => void | Promise<void>;
  signal?: AbortSignal;
}): Promise<string[]> {
  if (filterAwadaReply(params) === null) return [];
  const account = resolveAwadaAccount({ cfg: params.cfg, accountId: params.accountId });
  if (!account.enabled || !account.configured || !account.relayBaseUrl || !account.awadaKey)
    throw new Error("Awada account is not configured");
  const reply = resolveSendableOutboundReplyParts(params.payload);
  const text = stripReasoningTagsFromText(reply.text);
  const limit =
    account.config.perMsgMaxLen ??
    getAwadaRuntime().channel.text.resolveTextChunkLimit(params.cfg, "awada", account.accountId, {
      fallbackLimit: 2000,
    });
  const parts: ContentObject[] = text.trim()
    ? getAwadaRuntime()
        .channel.text.chunkMarkdownText(text, limit)
        .map((text) => ({ type: "text", text }))
    : [];
  for (const url of reply.mediaUrls)
    parts.push(
      await mediaContent({ ...params, mediaUrl: url, audioAsVoice: params.payload.audioAsVoice }),
    );
  const ids: string[] = [];
  for (const [index, batch] of splitAwadaContent(parts).entries()) {
    const receipt = await postOutbound({
      relayBaseUrl: account.relayBaseUrl,
      awadaKey: account.awadaKey,
      lane: account.lane,
      target: params.target,
      payload: batch,
      sourceEventId: params.inboundEventId,
      requestId: params.requestId ? `${params.requestId}-${index}` : undefined,
      beforeSend: params.beforeSend,
      signal: params.signal,
    });
    ids.push(receipt.eventId);
  }
  return ids;
}

export const awadaOutbound: ChannelOutboundAdapter = {
  deliveryMode: "direct",
  chunker: (text, limit) => getAwadaRuntime().channel.text.chunkMarkdownText(text, limit),
  chunkerMode: "markdown",
  textChunkLimit: 2000,
  normalizePayload: filterAwadaReply,
  sendText: async ({
    cfg,
    to,
    text,
    accountId,
    deliveryQueueId,
    deliveryPartIndex,
    signal,
    onPlatformSendDispatch,
    assertDirectAdapterHandoff,
  }) => {
    const account = resolveAwadaAccount({ cfg, accountId });
    const ids = await deliverAwadaReply({
      cfg,
      accountId: account.accountId,
      target: resolveAwadaSendTarget(to, account.accountId, account.lane),
      payload: { text },
      signal,
      requestId: deliveryQueueId
        ? `delivery-${deliveryQueueId}-${deliveryPartIndex ?? 0}`
        : undefined,
      beforeSend: async () => {
        await onPlatformSendDispatch?.();
        assertDirectAdapterHandoff?.();
      },
    });
    return {
      channel: "awada",
      messageId: ids.at(-1) ?? "no_reply_suppressed",
      ...(ids.length ? {} : { outcome: "not_sent" as const }),
      meta: { state: ids.length ? "queued" : "suppressed", operationIds: ids },
    };
  },
  sendMedia: async ({
    cfg,
    to,
    text,
    mediaUrl,
    accountId,
    mediaAccess,
    mediaLocalRoots,
    mediaReadFile,
    audioAsVoice,
    forceDocument,
    deliveryQueueId,
    deliveryPartIndex,
    signal,
    onPlatformSendDispatch,
    assertDirectAdapterHandoff,
  }) => {
    const account = resolveAwadaAccount({ cfg, accountId });
    const ids = await deliverAwadaReply({
      cfg,
      accountId: account.accountId,
      mediaAccess,
      mediaLocalRoots,
      mediaReadFile,
      forceDocument,
      target: resolveAwadaSendTarget(to, account.accountId, account.lane),
      payload: { text, mediaUrl, audioAsVoice },
      signal,
      requestId: deliveryQueueId
        ? `delivery-${deliveryQueueId}-${deliveryPartIndex ?? 0}`
        : undefined,
      beforeSend: async () => {
        await onPlatformSendDispatch?.();
        assertDirectAdapterHandoff?.();
      },
    });
    return {
      channel: "awada",
      messageId: ids.at(-1) ?? "no_reply_suppressed",
      ...(ids.length ? {} : { outcome: "not_sent" as const }),
      meta: { state: ids.length ? "queued" : "suppressed", operationIds: ids },
    };
  },
};

export const awadaMessageAdapter = defineChannelMessageAdapter({
  id: "awada",
  send: {
    text: async (ctx) => {
      const { onDeliveryResult: _progress, ...outboundCtx } = ctx;
      const result = await awadaOutbound.sendText!(outboundCtx);
      return {
        ...(result.outcome ? { outcome: result.outcome } : {}),
        messageId: result.messageId,
        receipt: createMessageReceiptFromOutboundResults({ results: [result], kind: "text" }),
      };
    },
    media: async (ctx) => {
      const { onDeliveryResult: _progress, ...outboundCtx } = ctx;
      const result = await awadaOutbound.sendMedia!(outboundCtx);
      return {
        ...(result.outcome ? { outcome: result.outcome } : {}),
        messageId: result.messageId,
        receipt: createMessageReceiptFromOutboundResults({ results: [result], kind: "media" }),
      };
    },
  },
});
