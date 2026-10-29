import { lstatSync, readFileSync, renameSync, unlinkSync, writeFileSync } from "node:fs";
import { randomBytes, randomUUID } from "node:crypto";
import { join } from "node:path";
import { endpointFor, privateDirectory, registryDir, stateHome } from "../platform/paths.js";
import { PROTOCOL_VERSION, RuntimeError } from "../protocol/index.js";

export const BROKER_SESSION = "__xiaobei_browser_broker__";
export interface BrokerRegistration {
  protocolVersion: number;
  session: string;
  generation: string;
  authorization: string;
  endpoint: string;
  pid: number;
}
const recordPath = (home: string) => join(registryDir(home), "broker.json");

export function newBrokerRecord(home = stateHome()): BrokerRegistration {
  const generation = randomUUID();
  return { protocolVersion: PROTOCOL_VERSION, session: BROKER_SESSION, generation,
    authorization: randomBytes(32).toString("hex"), pid: process.pid,
    endpoint: endpointFor(BROKER_SESSION, generation, home) };
}
export function readBrokerRecord(home = stateHome()): BrokerRegistration | null {
  try {
    const file = recordPath(home), stat = lstatSync(file);
    if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 65536 ||
        (process.platform !== "win32" && (stat.uid !== process.getuid!() || (stat.mode & 0o077))))
      throw new RuntimeError("INVALID_STATE", "Invalid or non-private browser broker record");
    const value = JSON.parse(readFileSync(file, "utf8")) as BrokerRegistration;
    if (value.protocolVersion !== PROTOCOL_VERSION || value.session !== BROKER_SESSION ||
        typeof value.generation !== "string" || !value.generation ||
        typeof value.authorization !== "string" || !/^[a-f0-9]{64}$/.test(value.authorization) ||
        !Number.isSafeInteger(value.pid) || value.pid < 1 ||
        value.endpoint !== endpointFor(BROKER_SESSION, value.generation, home))
      throw new RuntimeError("INVALID_STATE", "Browser broker record does not match this installation");
    return value;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw error;
  }
}
export function writeBrokerRecord(record: BrokerRegistration, home: string): void {
  privateDirectory(registryDir(home));
  const file = recordPath(home), temporary = `${file}.${randomUUID()}.tmp`;
  try {
    writeFileSync(temporary, JSON.stringify(record), { mode: 0o600, flag: "wx" });
    renameSync(temporary, file);
  } finally { try { unlinkSync(temporary); } catch {} }
}
export function removeBrokerRecord(record: BrokerRegistration, home: string): void {
  if (readBrokerRecord(home)?.generation === record.generation) unlinkSync(recordPath(home));
}
