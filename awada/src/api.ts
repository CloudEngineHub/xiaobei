import { randomUUID } from "node:crypto";
import { awadaCatalogView, awadaKnownAction, awadaTransportAction } from "./action-catalog.js";
import { assertAwadaPublicAction, awadaTranscriptionAction } from "./action-policy.js";
import {
  awadaOperationView,
  awadaPublicValue,
  awadaTechnicalText,
  type AwadaCatalogOperation,
} from "./presentation.js";

export const AWADA_API_PATH = "/api/v2/awada";
export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;
export type GatewayCredentials = { relayBaseUrl: string; awadaKey: string; lane: string };
export type OperationState =
  | "queued"
  | "running"
  | "submitted"
  | "succeeded"
  | "failed"
  | "unknown";
export type OperationReceipt = {
  streamId: string;
  eventId: string;
  operationId?: string;
  state?: OperationState;
};
export type OperationResult = {
  state: OperationState;
  eventId?: string;
  operationId?: string;
  results?: unknown[];
  error?: unknown;
  [key: string]: unknown;
};
export type ProviderOperation = {
  operation: string;
  params?: Record<string, unknown> | unknown[];
  query?: Record<string, unknown>;
  file?: { filename: string; base64: string; contentType?: string };
  request_id?: string;
};

/** Accept existing origin-only settings and full API URLs; never silently use v1. */
export function awadaApiUrl(base: string, endpoint: string, lane?: string): URL {
  const url = new URL(base);
  if (!/^https?:$/.test(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new Error("Invalid awada relayBaseUrl");
  }
  let prefix = url.pathname.replace(/\/+$/, "");
  if (/\/api\/v[12]\/awada$/.test(prefix)) prefix = prefix.replace(/\/api\/v[12]\/awada$/, "");
  url.pathname = prefix + AWADA_API_PATH + endpoint;
  if (lane) url.searchParams.set("lane", lane);
  return url;
}

/** Preserve the original JSON token for identifiers beyond the safe integer range. */
export function parseAwadaJson(text: string): unknown {
  return JSON.parse(text, ((_key: string, value: unknown, context?: { source?: string }) => {
    if (typeof value === "number" && Number.isInteger(value) && !Number.isSafeInteger(value)) {
      if (context?.source && /^-?\d+$/.test(context.source)) return context.source;
      throw new Error("Unsafe numeric identifier in awada response");
    }
    return value;
  }) as Parameters<typeof JSON.parse>[1]);
}

export function stringifyAwadaJson(value: unknown): string {
  return JSON.stringify(value, (_key, item) => {
    if (
      typeof item === "number" &&
      (!Number.isFinite(item) || (Number.isInteger(item) && !Number.isSafeInteger(item)))
    ) {
      throw new Error("Pass large awada identifiers as strings");
    }
    return item;
  });
}

export class AwadaApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status = 0,
  ) {
    super(`awada ${awadaTechnicalText(code)}: ${awadaTechnicalText(message)}`);
    this.code = awadaTechnicalText(code);
  }
}

export async function awadaRequest<T>(
  credentials: GatewayCredentials,
  endpoint: string,
  options: {
    body?: unknown;
    signal?: AbortSignal;
    timeoutMs?: number;
    query?: Record<string, unknown>;
    public?: boolean;
  } = {},
): Promise<T> {
  const url = awadaApiUrl(
    credentials.relayBaseUrl,
    endpoint,
    options.public ? undefined : credentials.lane,
  );
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined) url.searchParams.set(key, String(value));
  }
  const body = options.body === undefined ? undefined : stringifyAwadaJson(options.body);
  if (body && Buffer.byteLength(body) > 32 * 1024 * 1024)
    throw new Error("Awada request exceeds 32 MiB");
  const timeout = AbortSignal.timeout(options.timeoutMs ?? 30_000);
  const res = await fetch(url, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      ...(!options.public ? { "X-OFB-Key": credentials.awadaKey } : {}),
      "Content-Type": "application/json",
    },
    body,
    signal: options.signal ? AbortSignal.any([timeout, options.signal]) : timeout,
  });
  const response = parseAwadaJson(await res.text()) as {
    success?: boolean;
    data?: T;
    error?: { code?: string; message?: string };
  };
  if (
    !res.ok ||
    response.success !== true ||
    response.data === undefined ||
    response.data === null
  ) {
    throw new AwadaApiError(
      response.error?.code ?? `HTTP_${res.status}`,
      response.error?.message ?? res.statusText,
      res.status,
    );
  }
  return response.data;
}

export async function getAwadaCapabilities(
  credentials: GatewayCredentials,
  operation?: string,
  signal?: AbortSignal,
) {
  if (!operation) {
    const remote = await awadaRequest<Record<string, unknown>>(credentials, "/capabilities", {
      signal,
    });
    return awadaCatalogView(credentials, remote);
  }
  assertAwadaPublicAction(operation);
  if (operation === awadaTranscriptionAction.id)
    return awadaOperationView(awadaTranscriptionAction, true);
  const transportAction = awadaTransportAction(credentials, operation);
  assertAwadaPublicAction(transportAction);
  try {
    const remote = await awadaRequest<AwadaCatalogOperation>(
      credentials,
      `/capabilities/${encodeURIComponent(transportAction)}`,
      { signal },
    );
    return awadaOperationView({ ...awadaKnownAction(operation), ...remote }, true);
  } catch (error) {
    const known = awadaKnownAction(operation);
    // Older servers scope discovery to one account. Keep the full contract available;
    // execution support and permissions are always decided by the server.
    if (known && error instanceof AwadaApiError && error.status === 404)
      return awadaOperationView(known, true);
    throw error;
  }
}

export function submitAwadaOperation(
  credentials: GatewayCredentials,
  input: ProviderOperation,
  signal?: AbortSignal,
) {
  if (typeof input.operation !== "string" || !input.operation.trim())
    throw new Error("Invalid Awada action ID");
  assertAwadaPublicAction(input.operation);
  const operation = awadaTransportAction(credentials, input.operation);
  assertAwadaPublicAction(operation);
  if (input.operation === awadaTranscriptionAction.id)
    throw new Error("Use transcribeAwadaVoice or awada_api operation voice.transcribe");
  if (input.file && Buffer.from(input.file.base64, "base64").length > MAX_UPLOAD_BYTES) {
    throw new Error("Awada upload exceeds 20 MiB");
  }
  return awadaRequest<OperationReceipt>(credentials, "/operations", {
    body: {
      ...input,
      operation,
      request_id: input.request_id ?? randomUUID(),
    },
    signal,
  });
}

export async function getAwadaOperation(
  credentials: GatewayCredentials,
  id: string,
  signal?: AbortSignal,
) {
  const result = await awadaRequest<OperationResult>(
    credentials,
    `/operations/${encodeURIComponent(id)}`,
    {
      signal,
    },
  );
  return awadaPublicValue(result) as OperationResult;
}

/** Wait for execution, never resubmit an accepted or uncertain provider write. */
export async function waitForAwadaOperation(
  credentials: GatewayCredentials,
  id: string,
  options: { timeoutMs?: number; signal?: AbortSignal } = {},
) {
  const deadline = Date.now() + (options.timeoutMs ?? 30_000);
  while (true) {
    const result = await getAwadaOperation(credentials, id, options.signal);
    if (["succeeded", "failed", "unknown"].includes(result.state) || Date.now() >= deadline)
      return result;
    await new Promise<void>((resolve, reject) => {
      const onAbort = () => {
        clearTimeout(timer);
        reject(options.signal?.reason);
      };
      const timer = setTimeout(() => {
        options.signal?.removeEventListener("abort", onAbort);
        resolve();
      }, 500);
      if (options.signal?.aborted) onAbort();
      else options.signal?.addEventListener("abort", onAbort, { once: true });
    });
  }
}

export function readAwadaInbound(
  credentials: GatewayCredentials,
  options: { count?: number; block_ms?: number; last_id?: string; signal?: AbortSignal } = {},
) {
  const { signal, ...query } = options;
  return awadaRequest<{ events: Array<{ id: string; event: unknown }>; lastId: string }>(
    credentials,
    "/inbound",
    { query, signal },
  );
}
