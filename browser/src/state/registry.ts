import { closeSync, existsSync, lstatSync, openSync, readFileSync, readdirSync, renameSync, unlinkSync, writeFileSync } from "node:fs";
import { randomBytes, randomUUID } from "node:crypto";
import { dirname, join } from "node:path";
import { RuntimeError, PROTOCOL_VERSION } from "../protocol/index.js";
import { endpointFor, privateDirectory, recordPath, registryDir, stateHome } from "../platform/paths.js";

export interface LaunchOptions {
  headless: boolean;
  persistent: string | null;
  proxy: string | null;
  geoip: boolean;
  locale: string | null;
  viewport: [number, number] | null;
  idleTimeout: number;
}
export interface Registration {
  protocolVersion: number;
  session: string;
  generation: string;
  authorization: string;
  endpoint: string;
  pid: number;
  createdAt: string;
  options: LaunchOptions;
  ownerGeneration?: string;
}
export function isAlive(pid: number): boolean {
  if (!Number.isSafeInteger(pid) || pid < 1) return false;
  try { process.kill(pid, 0); return true; }
  catch (e) { return (e as NodeJS.ErrnoException).code !== "ESRCH"; }
}
export function readRecord(session: string, home = stateHome()): Registration | null {
  const file = recordPath(session, home);
  try {
    const stat = lstatSync(file);
    if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 65536 ||
        (process.platform !== "win32" && (stat.uid !== process.getuid!() || (stat.mode & 0o077))))
      throw new RuntimeError("INVALID_STATE", "Invalid or non-private runtime record");
    const value = JSON.parse(readFileSync(file, "utf8")) as Registration;
    if (value.protocolVersion !== PROTOCOL_VERSION || value.session !== session ||
        typeof value.generation !== "string" || typeof value.authorization !== "string" ||
        value.authorization.length !== 64 || !Number.isSafeInteger(value.pid) || !value.options ||
        (value.ownerGeneration !== undefined && typeof value.ownerGeneration !== "string") ||
        value.endpoint !== endpointFor(session, value.generation, home))
      throw new RuntimeError("INVALID_STATE", "Runtime record does not match this installation");
    return value;
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw e;
  }
}
export function writeRecord(record: Registration, home = stateHome()): void {
  const file = recordPath(record.session, home);
  privateDirectory(dirname(file));
  const temp = `${file}.${randomUUID()}.tmp`;
  try {
    writeFileSync(temp, JSON.stringify(record), { mode: 0o600, flag: "wx" });
    renameSync(temp, file);
  } finally { try { unlinkSync(temp); } catch {} }
}
export function newRecord(session: string, options: LaunchOptions, home = stateHome()): Registration {
  const generation = randomUUID();
  return { protocolVersion: PROTOCOL_VERSION, session, generation, authorization: randomBytes(32).toString("hex"),
    endpoint: endpointFor(session, generation, home), pid: process.pid, createdAt: new Date().toISOString(), options };
}
export function removeRecord(record: Registration, home = stateHome()): void {
  if (readRecord(record.session, home)?.generation === record.generation) unlinkSync(recordPath(record.session, home));
}
export function records(home = stateHome()): Registration[] {
  const dir = registryDir(home);
  if (!existsSync(dir)) return [];
  return readdirSync(dir).filter(n => /^[a-f0-9]{24}\.json$/.test(n)).map(n => {
    // Validate each through the same ownership and endpoint checks as a direct read.
    const file = join(dir, n);
    const stat = lstatSync(file);
    if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 65536) throw new RuntimeError("INVALID_STATE", "Invalid registry entry");
    const session = JSON.parse(readFileSync(file, "utf8")).session;
    return readRecord(session, home)!;
  });
}

/** Cross-process admission lock. Never steals a live or ambiguous owner, never kills by PID. */
export async function withLock<T>(file: string, action: () => Promise<T>, timeoutMs = 65000): Promise<T> {
  privateDirectory(dirname(file));
  const owner = { pid: process.pid, nonce: randomUUID() };
  const until = Date.now() + timeoutMs;
  while (true) {
    try {
      const fd = openSync(file, "wx", 0o600);
      try { writeFileSync(fd, JSON.stringify(owner)); } finally { closeSync(fd); }
      break;
    } catch (e) {
      if ((e as NodeJS.ErrnoException).code !== "EEXIST") throw e;
      // Serialize recovery too: only one contender can remove a dead owner's lock.
      const recovery = `${file}.recover`;
      let guard: number | undefined;
      try {
        guard = openSync(recovery, "wx", 0o600);
        const previous = JSON.parse(readFileSync(file, "utf8"));
        if (Number.isSafeInteger(previous.pid) && !isAlive(previous.pid)) unlinkSync(file);
      } catch {} finally {
        if (guard !== undefined) { closeSync(guard); unlinkSync(recovery); }
      }
      if (Date.now() >= until) throw new RuntimeError("SESSION_BUSY", "Startup lock is occupied; inspect the owning process before recovery");
      await new Promise(r => setTimeout(r, 50));
    }
  }
  try { return await action(); }
  finally {
    try { if (JSON.parse(readFileSync(file, "utf8")).nonce === owner.nonce) unlinkSync(file); } catch {}
  }
}
