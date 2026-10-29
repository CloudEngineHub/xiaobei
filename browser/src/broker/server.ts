import { createServer, type Server, type Socket } from "node:net";
import { chmodSync, unlinkSync } from "node:fs";
import { dirname, join } from "node:path";
import { createHash, timingSafeEqual } from "node:crypto";
import { BrowserClient } from "../client/index.js";
import { privateDirectory, registryDir, stateHome, validateSession } from "../platform/paths.js";
import { encode, failure, FrameReader, isObject, MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES,
  parseRequest, reply, RuntimeError, type Request, type Response } from "../protocol/index.js";
import { isAlive, readRecord, withLock, type LaunchOptions } from "../state/registry.js";
import { BROKER_SESSION, newBrokerRecord, readBrokerRecord, removeBrokerRecord, writeBrokerRecord,
  type BrokerRegistration } from "./state.js";

function launchOptions(value: unknown): LaunchOptions {
  if (!isObject(value) || typeof value.headless !== "boolean" || typeof value.geoip !== "boolean" ||
      !["persistent", "proxy", "locale"].every(key => value[key] === null || typeof value[key] === "string") ||
      !Number.isSafeInteger(value.idleTimeout) || Number(value.idleTimeout) < 0 ||
      !(value.viewport === null || (Array.isArray(value.viewport) && value.viewport.length === 2 &&
        value.viewport.every(n => Number.isSafeInteger(n) && n > 0 && n <= 16384))))
    throw new RuntimeError("INVALID_ARGUMENT", "Invalid browser launch options");
  return { headless: value.headless, geoip: value.geoip,
    persistent: value.persistent as string | null, proxy: value.proxy as string | null,
    locale: value.locale as string | null, viewport: value.viewport as [number, number] | null,
    idleTimeout: value.idleTimeout as number };
}

/** A Gateway plugin service owns launches, independently of individual agent exec scopes. */
export class BrowserBroker {
  private server?: Server;
  private record?: BrokerRegistration;
  private sockets = new Set<Socket>();
  private owned = new Map<string, string>();
  private requests = new Map<string, { digest: string; work: Promise<Response>; done: boolean }>();
  private stopping = false;
  private closing?: Promise<void>;
  constructor(readonly home = stateHome(), private onError: (error: unknown) => void = () => {}) {}

  async start(): Promise<void> {
    await withLock(join(registryDir(this.home), "broker-owner.lock"), async () => {
      if (this.server || this.stopping) throw new RuntimeError("BROKER_BUSY", "Broker service is already started or stopping");
      const previous = readBrokerRecord(this.home);
      if (previous && isAlive(previous.pid)) throw new RuntimeError("BROKER_BUSY", "Another browser broker owner is alive");
      const record = newBrokerRecord(this.home);
      this.record = record;
      if (process.platform !== "win32") privateDirectory(dirname(record.endpoint));
      this.server = createServer({ allowHalfOpen: true }, socket => this.connect(socket));
      try {
        await new Promise<void>((resolve, reject) => {
          this.server!.once("error", reject);
          this.server!.listen(record.endpoint, () => { this.server!.removeListener("error", reject); resolve(); });
        });
        if (process.platform !== "win32") chmodSync(record.endpoint, 0o600);
        writeBrokerRecord(record, this.home);
        this.server.on("error", error => { this.onError(error); void this.close().catch(this.onError); });
      } catch (error) {
        this.server.close();
        if (process.platform !== "win32") { try { unlinkSync(record.endpoint); } catch {} }
        throw error;
      }
    });
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
        received = true; socket.setTimeout(0);
        const request = parseRequest(JSON.parse(line));
        void this.dispatch(request).then(response => {
          if (!socket.destroyed) socket.end(encode(response, MAX_RESPONSE_BYTES));
        }).catch(() => socket.destroy());
      } catch (error) {
        socket.end(encode(failure("?", this.record!.generation, error), MAX_RESPONSE_BYTES));
      }
    });
    socket.on("end", () => { if (!received) socket.destroy(); });
  }
  async dispatch(request: Request): Promise<Response> {
    const record = this.record!;
    try {
      if (request.generation !== record.generation || request.session !== BROKER_SESSION)
        throw new RuntimeError("STALE_GENERATION", "Browser broker generation does not match");
      const actual = Buffer.from(request.authorization), expected = Buffer.from(record.authorization);
      if (actual.length !== expected.length || !timingSafeEqual(actual, expected))
        throw new RuntimeError("UNAUTHORIZED", "Invalid local broker authorization");
      if (request.deadlineMs <= Date.now()) throw new RuntimeError("TIMEOUT", "Broker request expired before execution");
      if (this.stopping) throw new RuntimeError("BROKER_UNAVAILABLE", "Browser broker is stopping");
      if (request.action === "hello") return reply(request.requestId, record.generation, { kind: "xiaobei-browser-broker" });
      if (request.action !== "start") throw new RuntimeError("ACTION_UNSUPPORTED", "Broker only accepts browser starts");
      const session = request.params.session;
      if (typeof session !== "string" || session === BROKER_SESSION) throw new RuntimeError("INVALID_ARGUMENT", "Invalid session");
      validateSession(session);
      const options = launchOptions(request.params.options);
      const digest = createHash("sha256").update(JSON.stringify([session, options])).digest("hex");
      const previous = this.requests.get(request.requestId);
      if (previous) {
        if (previous.digest !== digest) throw new RuntimeError("INVALID_ARGUMENT", "Broker request ID reused with different content");
        return previous.work;
      }
      while (this.requests.size >= 200) {
        const old = [...this.requests].find(([, entry]) => entry.done);
        if (!old) throw new RuntimeError("CAPACITY_EXCEEDED", "Too many pending broker starts");
        this.requests.delete(old[0]);
      }
      const entry = { digest, done: false, work: Promise.resolve({} as Response) };
      this.requests.set(request.requestId, entry);
      entry.work = (async () => {
        try {
          const client = new BrowserClient({ home: this.home, session });
          return reply(request.requestId, record.generation,
            await client.startLocally(options, record.generation, request.deadlineMs));
        } catch (error) { return failure(request.requestId, record.generation, error); }
        finally {
          try {
            const current = readRecord(session, this.home);
            if (current?.ownerGeneration === record.generation) this.owned.set(session, current.generation);
          } finally { entry.done = true; }
        }
      })();
      return entry.work;
    } catch (error) { return failure(request.requestId, record.generation, error); }
  }
  close(): Promise<void> { return this.closing ??= this.shutdown(); }
  private async shutdown(): Promise<void> {
    this.stopping = true;
    const closed = new Promise<void>(resolve => this.server?.listening ? this.server.close(() => resolve()) : resolve());
    await Promise.allSettled([...this.requests.values()].map(entry => entry.work));
    const stopped = await Promise.allSettled([...this.owned].map(async ([session, generation]) => {
      const record = readRecord(session, this.home);
      const owner = this.record?.generation;
      if (!owner || !record || record.generation !== generation || record.ownerGeneration !== owner) return;
      if (!(await new BrowserClient({ home: this.home, session }).status()).running) return;
      const response = await new BrowserClient({ home: this.home, session }).stopOwned(owner);
      if (!response.ok) throw new RuntimeError(response.error!.code, response.error!.message);
    }));
    for (const socket of this.sockets) socket.destroy();
    await closed;
    if (this.record) {
      removeBrokerRecord(this.record, this.home);
      if (process.platform !== "win32") { try { unlinkSync(this.record.endpoint); } catch {} }
    }
    const failed = stopped.find(result => result.status === "rejected");
    if (failed?.status === "rejected") throw failed.reason;
  }
}
