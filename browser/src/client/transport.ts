import { createConnection } from "node:net";
import { encode, FrameReader, MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES, PROTOCOL_VERSION, RuntimeError, type Request, type Response } from "../protocol/index.js";

/** Never retries a dispatched request: its side effects may already have happened. */
export function exchange(endpoint: string, request: Request): Promise<Response> {
  const frame = encode(request, MAX_REQUEST_BYTES);
  return new Promise((resolve, reject) => {
    let sent = false;
    let settled = false;
    const reader = new FrameReader(MAX_RESPONSE_BYTES);
    const socket = createConnection(endpoint);
    const finish = (error?: Error, response?: Response) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      socket.destroy();
      if (error) reject(error); else resolve(response!);
    };
    const timer = setTimeout(() => finish(new RuntimeError(sent ? "OUTCOME_UNKNOWN" : "DAEMON_UNAVAILABLE",
      sent ? "Response deadline exceeded; do not replay the action" : "Connection deadline exceeded")),
      Math.max(1, request.deadlineMs - Date.now()));
    socket.once("connect", () => { sent = true; socket.end(frame); });
    socket.on("data", chunk => {
      try {
        const line = reader.push(chunk);
        if (line === undefined) return;
        const response = JSON.parse(line) as Response;
        if (response.protocolVersion !== PROTOCOL_VERSION || response.requestId !== request.requestId ||
            response.meta?.generation !== request.generation || typeof response.ok !== "boolean")
          throw new RuntimeError("PROTOCOL_MISMATCH", "Response identity or version mismatch");
        finish(undefined, response);
      } catch (e) { finish(e as Error); }
    });
    socket.once("error", () => finish(new RuntimeError(sent ? "OUTCOME_UNKNOWN" : "DAEMON_UNAVAILABLE",
      sent ? "Connection failed after dispatch; inspect the result before retrying" : "Daemon is unavailable")));
    socket.once("end", () => finish(new RuntimeError(sent ? "OUTCOME_UNKNOWN" : "DAEMON_UNAVAILABLE", "Connection ended without a complete response")));
  });
}
