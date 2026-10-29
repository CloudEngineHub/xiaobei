import { randomUUID } from "node:crypto";

export const PROTOCOL_VERSION = 1;
export const MAX_REQUEST_BYTES = 1024 * 1024;
export const MAX_RESPONSE_BYTES = 8 * 1024 * 1024;
export type Params = Record<string, unknown>;
export class RuntimeError extends Error {
  constructor(public code: string, message: string) { super(message); }
}
export interface Request {
  protocolVersion: number;
  requestId: string;
  generation: string;
  session: string;
  authorization: string;
  action: string;
  params: Params;
  deadlineMs: number;
  leaseToken?: string;
}
export interface Response {
  protocolVersion: number;
  requestId: string;
  ok: boolean;
  data?: Params;
  error?: { code: string; message: string; retryable: boolean };
  meta: { generation: string };
}
export const isObject = (value: unknown): value is Params =>
  value !== null && typeof value === "object" && !Array.isArray(value);
export function parseRequest(value: unknown): Request {
  if (!isObject(value)) throw new RuntimeError("INVALID_ARGUMENT", "Request must be an object");
  if (value.protocolVersion !== PROTOCOL_VERSION) throw new RuntimeError("PROTOCOL_MISMATCH", "Unsupported protocol version");
  for (const field of ["requestId", "generation", "session", "authorization", "action"])
    if (typeof value[field] !== "string" || !value[field] || (value[field] as string).length > 512)
      throw new RuntimeError("INVALID_ARGUMENT", `Invalid ${field}`);
  if (!isObject(value.params) || !Number.isSafeInteger(value.deadlineMs) ||
      (value.leaseToken !== undefined && typeof value.leaseToken !== "string"))
    throw new RuntimeError("INVALID_ARGUMENT", "Invalid params, deadline or lease token");
  return value as unknown as Request;
}
export function reply(requestId: string, generation: string, data: Params): Response {
  return { protocolVersion: PROTOCOL_VERSION, requestId, ok: true, data, meta: { generation } };
}
export function failure(requestId: string, generation: string, error: unknown): Response {
  const code = error instanceof RuntimeError ? error.code : "ACTION_FAILED";
  return { protocolVersion: PROTOCOL_VERSION, requestId, ok: false,
    error: { code, message: error instanceof Error ? error.message : String(error),
      retryable: ["SESSION_BUSY", "DAEMON_UNAVAILABLE", "CAPACITY_EXCEEDED"].includes(code) },
    meta: { generation } };
}
export const requestId = (): string => randomUUID();

/** One bounded UTF-8 JSON line, including when a multibyte character is split. */
export class FrameReader {
  private chunks: Buffer[] = [];
  private size = 0;
  private complete = false;
  constructor(private limit: number) {}
  push(chunk: Buffer): string | undefined {
    if (this.complete) throw new RuntimeError("INVALID_ARGUMENT", "Only one request per connection is supported");
    this.size += chunk.length;
    if (this.size > this.limit) throw new RuntimeError("PAYLOAD_TOO_LARGE", "JSON frame exceeds byte limit");
    this.chunks.push(chunk);
    const newline = chunk.indexOf(10);
    if (newline < 0) return;
    if (newline !== chunk.length - 1) throw new RuntimeError("INVALID_ARGUMENT", "Unexpected data after JSON frame");
    this.complete = true;
    return new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(this.chunks).subarray(0, -1));
  }
}
export function encode(value: unknown, limit: number): Buffer {
  const bytes = Buffer.from(JSON.stringify(value) + "\n");
  if (bytes.length > limit) throw new RuntimeError("PAYLOAD_TOO_LARGE", "JSON frame exceeds byte limit");
  return bytes;
}
