import {
  formatInboundMediaUnavailableText,
  type InboundMediaFacts,
} from "openclaw/plugin-sdk/channel-inbound";
import { getAwadaRuntime } from "./runtime.js";
import { submitAwadaOperation, waitForAwadaOperation, type GatewayCredentials } from "./api.js";
import type { InboundEvent, MediaObject } from "./redis-types.js";
import { readFile } from "node:fs/promises";
import { decodeAwadaVoice } from "./voice.js";

const defaultExtensions = { image: "jpg", audio: "amr", video: "mp4", file: "bin" };

async function resolveQiweMedia(
  credentials: GatewayCredentials,
  media: MediaObject,
  eventId: string,
  index: number,
): Promise<string> {
  const raw = media.provider_data ?? {};
  const fileId = raw.fileId ?? media.file_id;
  const aes = raw.fileAeskey ?? raw.fileAesKey;
  const filename =
    media.file_name ??
    (typeof raw.filename === "string"
      ? raw.filename
      : `attachment.${defaultExtensions[media.type]}`);
  if (!fileId || !aes || !raw.fileMd5)
    throw new Error("Provider did not supply the required CDN download fields");
  const receipt = await submitAwadaOperation(credentials, {
    operation: "qiweapi.cloud.cdnWxDownload",
    params: { fileId, fileAeskey: aes, fileMd5: raw.fileMd5, filename },
    request_id: `media-${eventId}-${index}`,
  });
  const result = await waitForAwadaOperation(credentials, receipt.eventId, { timeoutMs: 30_000 });
  if (result.state !== "succeeded")
    throw new Error(`CDN download ${result.state}; operation ${receipt.eventId}`);
  for (const entry of result.results ?? []) {
    const data = (entry as { response?: { data?: { fileUrl?: string; cloudUrl?: string } } })
      .response?.data;
    if (data?.fileUrl || data?.cloudUrl) return (data.fileUrl ?? data.cloudUrl)!;
  }
  throw new Error("Provider returned no download URL");
}

export async function resolveAwadaInboundMedia(params: {
  event: InboundEvent;
  credentials: GatewayCredentials;
  maxBytes: number;
  log: (message: string) => void;
}): Promise<{ media: InboundMediaFacts[]; failures: string[] }> {
  const media: InboundMediaFacts[] = [];
  const failures: string[] = [];
  const core = getAwadaRuntime();
  for (const [index, item] of params.event.payload.entries()) {
    if (!["image", "file", "audio", "video"].includes(item.type)) continue;
    const attachment = item as MediaObject;
    try {
      const kind = attachment.type === "file" ? "document" : attachment.type;
      let saved: { path: string; contentType?: string };
      if (attachment.base64) {
        const bytes = Buffer.from(attachment.base64, "base64");
        saved = await core.channel.media.saveMediaBuffer(
          bytes,
          undefined,
          "inbound",
          params.maxBytes,
          attachment.file_name,
        );
      } else {
        const url =
          attachment.file_url ??
          (params.event.meta.platform === "qiweapi"
            ? await resolveQiweMedia(params.credentials, attachment, params.event.event_id, index)
            : undefined);
        if (!url) throw new Error("No downloadable media was provided");
        saved = await core.channel.media.saveRemoteMedia({
          url,
          maxBytes: params.maxBytes,
          subdir: "inbound",
          originalFilename: attachment.file_name,
        });
      }
      if (attachment.type === "audio") {
        const wav = await decodeAwadaVoice(await readFile(saved.path), params.maxBytes);
        if (wav)
          saved = await core.channel.media.saveMediaBuffer(
            wav,
            "audio/wav",
            "inbound",
            params.maxBytes,
            "voice.wav",
          );
      }
      media.push({
        path: saved.path,
        contentType: saved.contentType,
        kind,
        fileName: attachment.file_name,
        messageId: params.event.event_id,
      });
    } catch (error) {
      params.log(
        `awada: ${attachment.type} download failed for ${params.event.event_id}: ${String(error)}`,
      );
      failures.push(
        formatInboundMediaUnavailableText({ notice: "[awada attachment unavailable]" }),
      );
    }
  }
  return { media, failures };
}
