import { createServer, type Server, type Socket } from "node:net";
import { chmodSync, unlinkSync } from "node:fs";
import { dirname } from "node:path";
import { createHash, randomBytes, timingSafeEqual } from "node:crypto";
import { encode, failure, FrameReader, MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES, parseRequest, reply, RuntimeError, type Params, type Request, type Response } from "../protocol/index.js";
import { privateDirectory } from "../platform/paths.js";
import type { Registration } from "../state/registry.js";

export interface Driver {
  launch(): Promise<void>;
  execute(action: string, params: Params): Promise<Params>;
  close(): Promise<void>;
  capabilities: string[];
}
interface Lease { token: string; expiresAt: number | null }
export class RuntimeServer {
  private server: Server | undefined;
  private sockets = new Set<Socket>();
  private phase: "starting" | "ready" | "failed" | "stopping" = "starting";
  private busy = false;
  private lease: Lease | undefined;
  private lastActivity = Date.now();
  private timer: ReturnType<typeof setInterval> | undefined;
  private stopped: (() => void) | undefined;
  readonly closed = new Promise<void>(resolve => { this.stopped = resolve; });
  private closing: Promise<void> | undefined;
  private results = new Map<string, { digest: string; response?: Response; bytes?: number }>();
  private resultBytes = 0;
  constructor(readonly record: Registration, private driver: Driver, private onError: (error: unknown) => void = () => {}) {}
  async start(): Promise<void> {
    if (process.platform !== "win32") privateDirectory(dirname(this.record.endpoint));
    this.server = createServer({ allowHalfOpen: true }, socket => this.connect(socket));
    await new Promise<void>((resolve, reject) => {
      this.server!.once("error", reject);
      this.server!.listen(this.record.endpoint, () => {
        this.server!.removeListener("error", reject); resolve();
      });
    });
    this.server.on("error", error => { this.onError(error); void this.close(); });
    if (process.platform !== "win32") chmodSync(this.record.endpoint, 0o600);
    this.timer = setInterval(() => {
      this.expireLease();
      if (this.phase === "ready" && !this.busy && !this.lease && this.record.options.idleTimeout > 0 &&
          Date.now() - this.lastActivity > this.record.options.idleTimeout * 1000) void this.close();
    }, 1000);
    try { await this.driver.launch(); this.phase = "ready"; }
    catch (e) { this.phase = "failed"; this.onError(e); await this.close(); throw e; }
  }
  private expireLease(): void {
    if (!this.busy && this.lease?.expiresAt !== null && (this.lease?.expiresAt ?? Infinity) <= Date.now()) this.lease = undefined;
  }
  private status(): Params {
    this.expireLease();
    return { session: this.record.session, running: this.phase !== "failed", state: this.phase !== "ready" ? this.phase :
      this.busy ? "busy" : this.lease?.expiresAt === null ? "waiting_human" : "ready",
      headless: this.record.options.headless, headed: !this.record.options.headless, leased: !!this.lease,
      generation: this.record.generation, capabilities: this.driver.capabilities };
  }
  private connect(socket: Socket): void {
    this.sockets.add(socket);
    socket.on("close", () => this.sockets.delete(socket));
    socket.on("error", () => socket.destroy());
    socket.setTimeout(10000, () => socket.destroy());
    const reader = new FrameReader(MAX_REQUEST_BYTES);
    let received = false;
    socket.on("data", chunk => {
      if (received) { socket.destroy(); return; }
      try {
        const line = reader.push(chunk);
        if (line === undefined) return;
        received = true;
        socket.setTimeout(0);
        const request = parseRequest(JSON.parse(line));
        void this.dispatch(request).then(response => {
          if (socket.destroyed) return;
          try { socket.end(encode(response, MAX_RESPONSE_BYTES)); }
          catch (e) { socket.end(encode(failure(request.requestId, this.record.generation, e), MAX_RESPONSE_BYTES)); }
          if (["stop", "owner.stop"].includes(request.action) && response.ok) setImmediate(() => { void this.close(); });
        }).catch(error => { this.onError(error); socket.destroy(); });
      } catch (e) { received = true; socket.end(encode(failure("?", this.record.generation, e), MAX_RESPONSE_BYTES)); }
    });
    socket.on("end", () => { if (!received) socket.destroy(); });
  }
  async dispatch(request: Request): Promise<Response> {
    const id = request.requestId;
    try {
      if (request.generation !== this.record.generation || request.session !== this.record.session)
        throw new RuntimeError("STALE_GENERATION", "Session generation does not match");
      const actual = Buffer.from(request.authorization);
      const expected = Buffer.from(this.record.authorization);
      if (actual.length !== expected.length || !timingSafeEqual(actual, expected))
        throw new RuntimeError("UNAUTHORIZED", "Invalid local authorization");
      if (request.deadlineMs <= Date.now()) throw new RuntimeError("TIMEOUT", "Request expired before execution");
      if (request.action === "hello" || request.action === "status") return reply(id, this.record.generation, this.status());
      if (request.action === "owner.stop") {
        if (!this.record.ownerGeneration || request.params.ownerGeneration !== this.record.ownerGeneration)
          throw new RuntimeError("UNAUTHORIZED", "Session is not owned by this broker generation");
        this.phase = "stopping";
        return reply(id, this.record.generation, { stopping: true });
      }
      const digest = createHash("sha256").update(JSON.stringify([request.action, request.params, request.leaseToken])).digest("hex");
      const previous = this.results.get(id);
      if (previous) {
        if (previous.digest !== digest) throw new RuntimeError("INVALID_ARGUMENT", "Request ID reused with different content");
        return previous.response ?? failure(id, this.record.generation, new RuntimeError("OUTCOME_UNKNOWN", "Request is still running"));
      }
      this.expireLease();
      if (this.lease && request.leaseToken !== this.lease.token)
        throw new RuntimeError("SESSION_BUSY", "Session is reserved by another task");
      if (request.leaseToken && !this.lease) throw new RuntimeError("LEASE_EXPIRED", "Lease is no longer valid");
      if (request.action === "result") {
        const result = this.results.get(String(request.params.requestId));
        return reply(id, this.record.generation, { state: !result ? "unknown" : result.response ? "completed" : "running", response: result?.response });
      }
      if (this.phase !== "ready") throw new RuntimeError("DAEMON_UNAVAILABLE", `Session is ${this.phase}`);
      if (this.busy) throw new RuntimeError("SESSION_BUSY", "Another command is executing");
      this.lastActivity = Date.now();
      while (this.results.size >= 200 || this.resultBytes > 16 * 1024 * 1024) this.evictResult();
      const entry: { digest: string; response?: Response; bytes?: number } = { digest };
      this.results.set(id, entry);
      this.busy = true;
      // Keep busy until the actual action settles, including after the caller's deadline.
      const work = (async () => {
        try {
          let data: Params;
          if (request.action === "lease.acquire") {
            if (this.lease) throw new RuntimeError("SESSION_BUSY", "Lease already exists; renew or release it");
            this.lease = { token: randomBytes(32).toString("hex"), expiresAt: this.leaseDeadline(request.params) };
            data = { leaseToken: this.lease.token, expiresAt: this.lease.expiresAt };
          } else if (request.action === "lease.renew" || request.action === "lease.wait") {
            if (!this.lease) throw new RuntimeError("LEASE_EXPIRED", "Acquire a lease first");
            this.lease.expiresAt = request.action === "lease.wait" ? null : this.leaseDeadline(request.params);
            data = { expiresAt: this.lease.expiresAt };
          } else if (request.action === "lease.release") {
            if (!this.lease) throw new RuntimeError("LEASE_EXPIRED", "No lease to release");
            this.lease = undefined; data = { released: true };
          } else if (request.action === "stop") {
            this.phase = "stopping"; data = { stopping: true };
          } else {
            if (!this.driver.capabilities.includes(request.action)) throw new RuntimeError("ACTION_UNSUPPORTED", `Unsupported action: ${request.action}`);
            data = await this.driver.execute(request.action, request.params);
          }
          entry.response = reply(id, this.record.generation, data);
          // Bound cached results as well as transport responses.
          entry.bytes = encode(entry.response, MAX_RESPONSE_BYTES).length;
        } catch (e) { entry.response = failure(id, this.record.generation, e); }
        finally {
          this.resultBytes += entry.bytes ?? 0;
          while (this.resultBytes > 16 * 1024 * 1024 && this.results.size > 1) this.evictResult();
          this.busy = false; this.lastActivity = Date.now();
        }
        return entry.response;
      })();
      let timer: ReturnType<typeof setTimeout>;
      const deadline = new Promise<Response>(resolve => { timer = setTimeout(() => resolve(failure(id, this.record.generation,
        new RuntimeError("OUTCOME_UNKNOWN", "Action exceeded deadline; query its result, do not replay"))), Math.max(1, request.deadlineMs - Date.now())); });
      try { return await Promise.race([work, deadline]); } finally { clearTimeout(timer!); }
    } catch (e) { return failure(id, this.record.generation, e); }
  }
  private evictResult(): void {
    const key = this.results.keys().next().value;
    if (key === undefined) return;
    this.resultBytes -= this.results.get(key)?.bytes ?? 0;
    this.results.delete(key);
  }
  private leaseDeadline(params: Params): number {
    const ttl = params.ttlMs ?? 120000;
    if (!Number.isSafeInteger(ttl) || (ttl as number) < 1000 || (ttl as number) > 3600000)
      throw new RuntimeError("INVALID_ARGUMENT", "Lease TTL must be 1000–3600000 ms");
    return Date.now() + (ttl as number);
  }
  close(): Promise<void> {
    return this.closing ??= this.shutdown();
  }
  private async shutdown(): Promise<void> {
    this.phase = "stopping";
    if (this.timer) clearInterval(this.timer);
    const closed = new Promise<void>(resolve => this.server?.listening ? this.server.close(() => resolve()) : resolve());
    for (const socket of this.sockets) socket.destroy();
    try { await this.driver.close(); }
    finally {
      await closed;
      if (process.platform !== "win32") { try { unlinkSync(this.record.endpoint); } catch {} }
      this.stopped?.();
    }
  }
}
