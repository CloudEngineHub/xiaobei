import { spawn } from "node:child_process";
import { existsSync, openSync, closeSync } from "node:fs";
import { join } from "node:path";
import { createConnection } from "node:net";
import { exchange } from "./transport.js";
import { PROTOCOL_VERSION, RuntimeError, requestId, type Params, type Response } from "../protocol/index.js";
import { canonicalProfile, packageRoot, privateDirectory, registryDir, stateHome, validateSession } from "../platform/paths.js";
import { createHash } from "node:crypto";
import { isDeepStrictEqual } from "node:util";
import { isAlive, newRecord, readRecord, records, removeRecord, withLock, writeRecord, type LaunchOptions, type Registration } from "../state/registry.js";
import { loadDefaults } from "../state/config.js";
import { validateProfile } from "../state/identity-schema.js";

/** Shared launch defaults for CLI and Gateway adapters. */
export function resolveLaunchOptions(session: string, overrides: Partial<LaunchOptions> = {}, home = stateHome()): LaunchOptions {
  validateSession(session);
  const defaults = loadDefaults(session);
  return { headless: !(defaults.headed ?? false), persistent: defaults.persistent !== undefined ? defaults.persistent : join(home, "profiles", session),
    proxy: defaults.proxy ?? null, geoip: defaults.geoip ?? true, locale: defaults.locale ?? null,
    viewport: defaults.viewport ?? null, idleTimeout: defaults.timeout ?? 0, ...overrides };
}

export interface ClientOptions { home?: string; session?: string; deadlineMs?: number; leaseToken?: string }
export class BrowserClient {
  readonly home: string;
  readonly session: string;
  constructor(options: ClientOptions = {}) {
    this.home = options.home ?? stateHome(); this.session = options.session ?? "default";
    validateSession(this.session);
  }
  async send(record: Registration, action: string, params: Params = {}, options: ClientOptions & { requestId?: string } = {}): Promise<Response> {
    return exchange(record.endpoint, { protocolVersion: PROTOCOL_VERSION, requestId: options.requestId ?? requestId(),
      generation: record.generation, session: record.session, authorization: record.authorization, action, params,
      deadlineMs: Date.now() + (options.deadlineMs ?? 60000), leaseToken: options.leaseToken });
  }
  async status(): Promise<Params> {
    const record = readRecord(this.session, this.home);
    if (!record) return { session: this.session, running: false, state: "stopped" };
    try {
      const response = await this.send(record, "hello", {}, { deadlineMs: 2000 });
      if (!response.ok) throw new RuntimeError(response.error!.code, response.error!.message);
      return response.data!;
    } catch (e) {
      if (!(e instanceof RuntimeError) || !["DAEMON_UNAVAILABLE", "OUTCOME_UNKNOWN"].includes(e.code)) throw e;
      return { session: this.session, running: false, state: isAlive(record.pid) ? "unreachable" : "stale" };
    }
  }
  async start(options: LaunchOptions): Promise<Params> {
    options = { ...options, persistent: options.persistent === null ? null : canonicalProfile(options.persistent) };
    privateDirectory(registryDir(this.home));
    return withLock(join(registryDir(this.home), "admission.lock"), async () => {
      const previous = readRecord(this.session, this.home);
      const status = await this.status();
      if (status.running) {
        if (!isDeepStrictEqual(previous!.options, options))
          throw new RuntimeError("MODE_CONFLICT", "Existing session has different launch options; close it explicitly before changing mode");
        if (status.state === "starting") return this.waitReady(previous!);
        return status;
      }
      if (previous && isAlive(previous.pid))
        throw new RuntimeError("SESSION_BUSY", "Recorded owner is alive but unreachable; no automatic takeover");
      if (await this.legacyRunning()) throw new RuntimeError("PROFILE_IN_USE", "Legacy daemon is running for this session; drain it before migration");
      const alive = records(this.home).filter(r => isAlive(r.pid));
      if (alive.length >= 6) throw new RuntimeError("CAPACITY_EXCEEDED", "Six sessions are already admitted; no session was evicted");
      if (options.persistent && alive.some(r => r.options.persistent === options.persistent))
        throw new RuntimeError("PROFILE_IN_USE", "Another session owns this profile");
      if (options.persistent) validateProfile(options.persistent);
      const record = newRecord(this.session, options, this.home);
      writeRecord(record, this.home);
      const log = openSync(join(registryDir(this.home), `${record.generation}.log`), "wx", 0o600);
      try {
        const child = spawn(process.execPath, [join(packageRoot, "dist", "daemon.js"), this.session, record.generation], {
          detached: true, windowsHide: true, stdio: ["ignore", log, log],
          env: { ...process.env, XIAOBEI_BROWSER_HOME: this.home },
        });
        await new Promise<void>((resolve, reject) => { child.once("spawn", resolve); child.once("error", reject); });
        record.pid = child.pid!;
        writeRecord(record, this.home);
        child.unref();
      } catch (error) {
        // Only retract a record that never handed ownership to a child.
        if (readRecord(this.session, this.home)?.pid === process.pid) removeRecord(record, this.home);
        throw error;
      } finally { closeSync(log); }
      return this.waitReady(record);
    });
  }
  private async waitReady(record: Registration): Promise<Params> {
    const deadline = Date.now() + 60000;
    while (Date.now() < deadline) {
      if (!isAlive(record.pid)) throw new RuntimeError("START_FAILED", "Daemon exited during startup; inspect its local startup log");
      try {
        const response = await this.send(record, "hello", {}, { deadlineMs: 1000 });
        if (!response.ok) throw new RuntimeError(response.error!.code, response.error!.message);
        if (response.data?.state === "failed") throw new RuntimeError("START_FAILED", "Browser startup failed; inspect its local startup log");
        if (response.data?.state !== "starting") return response.data!;
      } catch (e) {
        if (!(e instanceof RuntimeError) || !["DAEMON_UNAVAILABLE", "OUTCOME_UNKNOWN"].includes(e.code)) throw e;
      }
      await new Promise(r => setTimeout(r, 100));
    }
    throw new RuntimeError("START_TIMEOUT", "Browser is still starting; inspect status instead of starting another daemon");
  }
  async request(action: string, params: Params = {}, options: ClientOptions & { requestId?: string } = {}): Promise<Response> {
    const record = readRecord(this.session, this.home);
    if (!record) throw new RuntimeError("DAEMON_UNAVAILABLE", "Session is not running; start or open it first");
    // Authenticated hello validates the endpoint before any action is sent.
    const hello = await this.send(record, "hello", {}, { deadlineMs: 2000 });
    if (!hello.ok) return hello;
    return this.send(record, action, params, options);
  }
  async sessions(): Promise<Params[]> {
    return Promise.all(records(this.home).map(r => new BrowserClient({ home: this.home, session: r.session }).status()));
  }
  async stop(options: ClientOptions = {}): Promise<Response> {
    const record = readRecord(this.session, this.home);
    if (!record) return { protocolVersion: PROTOCOL_VERSION, requestId: requestId(), ok: true, data: { closed: true }, meta: { generation: "local" } };
    const response = await this.request("stop", {}, options);
    if (!response.ok) return response;
    const deadline = Date.now() + 20000;
    while (Date.now() < deadline) {
      const current = readRecord(this.session, this.home);
      if (!current || current.generation !== record.generation) return { ...response, data: { closed: true } };
      await new Promise(r => setTimeout(r, 100));
    }
    throw new RuntimeError("OUTCOME_UNKNOWN", "Shutdown has not released its registration; do not assume the profile is free");
  }
  private async legacyRunning(): Promise<boolean> {
    if (process.platform === "win32") return false;
    const name = this.session.length > 84 ? `s-${createHash("sha256").update(this.session).digest("hex").slice(0, 16)}` : this.session;
    const endpoint = `/tmp/camoufox-cli-${name}.sock`;
    if (!existsSync(endpoint)) return false;
    return new Promise(resolve => {
      const socket = createConnection(endpoint);
      const done = (alive: boolean) => { socket.destroy(); resolve(alive); };
      socket.once("connect", () => done(true));
      socket.once("error", () => done(false));
      socket.setTimeout(500, () => done(true)); // Ambiguous existing endpoint is occupied.
    });
  }
}
