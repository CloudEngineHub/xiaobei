/**
 * Gateway client — WS inbound channel + ack.
 *
 * Per docs/AWADA-CLIENT-TRANSPORT.md §4: bot opens WS /api/v2/awada/inbound?lane=<lane>
 * with X-OFB-Key header. Relay pushes `{id, event}` frames. Bot processes the event then
 * sends `{type:"ack",id}`. Unacked events stay in the PEL and are reclaimed by the gateway
 * (XAUTOCLAIM, min-idle 65s) after reconnect — at-least-once semantics.
 *
 * Replies (outbound) are NOT sent over this socket; they go via HTTP POST /outbound (see send.ts),
 * which keeps the reply path usable from contexts that don't own the WS connection (proactive
 * sends, message actions) and decouples reply latency from the inbound socket.
 */
import WebSocket from "ws";
import type { InboundEvent } from "./redis-types.js";
import { awadaApiUrl, parseAwadaJson } from "./api.js";
import { awadaTechnicalText } from "./presentation.js";

const RECONNECT_BACKOFF_MS = [1_000, 2_000, 5_000, 10_000, 30_000];
const HEARTBEAT_TIMEOUT_MS = 90_000; // server pings every 30s; allow 3 missed.

/** Convert http(s) base URL to ws(s) and append the inbound path + lane. */
export function buildInboundWsUrl(relayBaseUrl: string, lane: string): string {
  const url = awadaApiUrl(relayBaseUrl, "/inbound", lane);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.href;
}

export type GatewayClientOpts = {
  relayBaseUrl: string;
  awadaKey: string;
  lane: string;
  /** Bot processing for one inbound event. Resolves when the bot is done (reply already POSTed). */
  onEvent: (id: string, event: InboundEvent) => Promise<void>;
  abortSignal?: AbortSignal;
  log?: (...args: unknown[]) => void;
  error?: (...args: unknown[]) => void;
};

/**
 * Run the gateway WS client until aborted. Reconnects with backoff on close/error.
 * Resolves when abortSignal fires (or a fatal misconfiguration throws).
 */
export async function runGatewayClient(opts: GatewayClientOpts): Promise<void> {
  const {
    relayBaseUrl,
    awadaKey,
    lane,
    onEvent,
    abortSignal,
    log = console.log,
    error: reportError = console.error,
  } = opts;
  const error = (...args: unknown[]) =>
    reportError(
      ...args.map((value) => (typeof value === "string" ? awadaTechnicalText(value) : value)),
    );
  if (!relayBaseUrl) throw new Error("[awada] relayBaseUrl not configured");
  if (!awadaKey) throw new Error("[awada] awadaKey not configured");

  const url = buildInboundWsUrl(relayBaseUrl, lane);
  let backoffIdx = 0;
  let stopped = false;

  const stop = () => {
    stopped = true;
  };
  abortSignal?.addEventListener("abort", stop);

  while (!stopped) {
    if (abortSignal?.aborted) break;
    const sessionStart = Date.now();
    try {
      await runOnce(url, awadaKey, lane, onEvent, abortSignal, log, error);
      // runOnce resolves only on close/error; fall through to reconnect.
    } catch (err) {
      error(`[awada] gateway WS error: ${String(err)}`);
    }
    if (stopped || abortSignal?.aborted) break;
    // Reset backoff if the previous session lived long enough to be considered healthy.
    if (Date.now() - sessionStart >= 60_000) backoffIdx = 0;
    const delay = RECONNECT_BACKOFF_MS[Math.min(backoffIdx, RECONNECT_BACKOFF_MS.length - 1)]!;
    backoffIdx++;
    log(`[awada] gateway WS reconnecting in ${delay}ms (lane=${lane})`);
    await sleep(delay, abortSignal);
  }

  abortSignal?.removeEventListener("abort", stop);
}

function sleep(ms: number, abortSignal?: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (abortSignal?.aborted) return resolve();
    const finish = () => {
      clearTimeout(t);
      abortSignal?.removeEventListener("abort", finish);
      resolve();
    };
    const t = setTimeout(finish, ms);
    abortSignal?.addEventListener("abort", finish, { once: true });
  });
}

/**
 * One WS connection lifecycle. Resolves on close/error. The caller measures the session
 * duration to reset reconnect backoff after a healthy long-lived connection.
 */
function runOnce(
  url: string,
  awadaKey: string,
  lane: string,
  onEvent: (id: string, event: InboundEvent) => Promise<void>,
  abortSignal: AbortSignal | undefined,
  log: (...args: unknown[]) => void,
  error: (...args: unknown[]) => void,
): Promise<void> {
  return new Promise<void>((resolve) => {
    let closed = false;
    const ws = new WebSocket(url, {
      headers: { "X-OFB-Key": awadaKey },
      handshakeTimeout: 30_000,
      maxPayload: 32 * 1024 * 1024,
    });
    let admissionTail = Promise.resolve();
    const onAbort = () => {
      try {
        ws.close(1000, "abort");
      } catch {}
    };

    let lastPong = Date.now();
    const watchdog = setInterval(() => {
      if (closed) return;
      if (Date.now() - lastPong > HEARTBEAT_TIMEOUT_MS) {
        error(`[awada] gateway WS heartbeat timeout (lane=${lane}); terminating`);
        try {
          ws.terminate();
        } catch {
          // ignore
        }
      }
    }, 30_000);

    // Server sends protocol-level ping every 30s; ws auto-replies with pong.
    // Track ping events for liveness (we receive pings, not pongs).
    ws.on("ping", () => {
      lastPong = Date.now();
    });

    const cleanup = () => {
      if (closed) return;
      closed = true;
      clearInterval(watchdog);
      abortSignal?.removeEventListener("abort", onAbort);
      try {
        ws.removeAllListeners();
      } catch {
        // ignore
      }
    };

    ws.on("open", () => {
      log(`[awada] gateway WS connected (lane=${lane})`);
    });

    ws.on("message", (raw: Buffer) => {
      let frame: unknown;
      try {
        frame = parseAwadaJson(String(raw));
      } catch {
        error(`[awada] gateway WS bad frame (non-json)`);
        return;
      }
      if (!frame || typeof frame !== "object") return;
      const f = frame as {
        id?: string;
        event?: InboundEvent;
        error?: { code?: string; message?: string };
      };
      if (f.error) {
        error(`[awada] gateway WS error frame: ${f.error.code ?? ""} ${f.error.message ?? ""}`);
        return;
      }
      if (!f.id || !f.event) return;
      const id = f.id;
      const event = f.event;
      // onEvent durably admits before ACK. A failed admission must remain in the server PEL.
      const admission = admissionTail
        .then(() => onEvent(id, event))
        .then(() => {
          if (!closed && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "ack", id }));
          }
        });
      admissionTail = admission.catch((err) => {
        error(`[awada] durable admission failed for ${id}: ${String(err)}`);
        ws.close(1011, "durable admission failed");
      });
    });

    ws.on("error", (err: Error) => {
      // Suppress noisy ECONNRESET on close; reconnect loop handles it.
      if (!closed) error(`[awada] gateway WS error: ${err.message}`);
    });

    ws.on("close", () => {
      cleanup();
      resolve();
    });

    abortSignal?.addEventListener("abort", onAbort, { once: true });
  });
}
