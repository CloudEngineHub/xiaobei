import { createHash, randomUUID } from "node:crypto";
import { setTimeout as delay } from "node:timers/promises";
import {
  awadaRequest,
  waitForAwadaOperation,
  type GatewayCredentials,
  type OperationReceipt,
  type OperationResult,
} from "./api.js";
import { withAwadaSubmissionLedger } from "./ledger.js";
import type { InboundEvent } from "./redis-types.js";

function responseData(result: OperationResult): Record<string, unknown> {
  if (result.state !== "succeeded")
    throw new Error(
      `Awada transcription operation ${result.state}; check its result before retrying`,
    );
  for (const entry of result.results ?? []) {
    const response = (entry as { response?: { data?: unknown } }).response;
    if (response?.data && typeof response.data === "object" && !Array.isArray(response.data))
      return response.data as Record<string, unknown>;
  }
  throw new Error("Awada transcription returned no result data");
}

/** The native task requires msgServerId, which can differ from source_message_id. */
export function awadaVoiceMessageId(event: InboundEvent): string | undefined {
  if (!event.payload.some((item) => item.type === "audio")) return undefined;
  const id = event.meta.provider_raw?.msgServerId;
  if (typeof id === "string" && id.trim() && id !== "0") return id;
  if (typeof id === "number" && Number.isSafeInteger(id) && id > 0) return String(id);
  return undefined;
}

/** One business action: apply, await execution, poll progress, return final text. */
export async function transcribeAwadaVoice(
  credentials: GatewayCredentials,
  messageId: string,
  options: { requestId?: string; timeoutMs?: number; signal?: AbortSignal } = {},
): Promise<{ messageId: string; text: string }> {
  if (typeof messageId !== "string" || !messageId.trim())
    throw new Error("A voice messageId string is required");
  const timeoutMs = options.timeoutMs ?? 30_000;
  if (!Number.isInteger(timeoutMs) || timeoutMs < 1000 || timeoutMs > 60_000)
    throw new Error("Transcription timeoutMs must be between 1000 and 60000");
  const signal = AbortSignal.any([
    AbortSignal.timeout(timeoutMs),
    ...(options.signal ? [options.signal] : []),
  ]);
  signal.throwIfAborted();
  const rootId = createHash("sha256")
    .update(JSON.stringify([options.requestId ?? randomUUID(), messageId]))
    .digest("hex");
  async function step(
    operation: string,
    params: Record<string, unknown>,
    requestId: string,
    retain = false,
  ) {
    signal.throwIfAborted();
    const body = { operation, params, request_id: requestId };
    const submit = () =>
      awadaRequest<OperationReceipt>(credentials, "/operations", { body, signal });
    const receipt = retain
      ? await withAwadaSubmissionLedger(credentials, requestId, body, submit)
      : await submit();
    return responseData(
      await waitForAwadaOperation(credentials, receipt.eventId, { timeoutMs, signal }),
    );
  }
  const applied = await step(
    "qiweapi.msg.voiceToTextApply",
    { msgServerId: messageId },
    `voice-${rootId}-apply`,
    true,
  );
  if (typeof applied.voiceId !== "string" || !applied.voiceId)
    throw new Error("Awada transcription returned no voiceId");
  while (true) {
    // A progress query is a new read, not a replay of an earlier cached query result.
    const data = await step(
      "qiweapi.msg.voiceToTextQuery",
      { msgServerId: messageId, voiceId: applied.voiceId },
      `voice-query-${randomUUID()}`,
    );
    if (data.isEnd === true) {
      if (typeof data.text !== "string" || !data.text.trim())
        throw new Error("Awada transcription completed without text");
      return { messageId, text: data.text };
    }
    await delay(500, undefined, { signal });
  }
}
