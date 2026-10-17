import { createHash } from "node:crypto";
import { existsSync, lstatSync, mkdirSync, realpathSync } from "node:fs";
import { homedir, tmpdir, userInfo } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { RuntimeError } from "../protocol/index.js";

export const hash = (value: string): string => createHash("sha256").update(value).digest("hex").slice(0, 24);
export const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
export function stateHome(): string {
  return resolve(process.env.XIAOBEI_BROWSER_HOME || join(homedir(), ".camoufox-cli"));
}
export function validateSession(session: string): void {
  // Session names also become profile basenames. Reject separators and Windows devices on all OSes.
  if (!session || session.length > 128 || /[<>:"/\\|?*\x00-\x1f]/.test(session) ||
      /[. ]$/.test(session) || /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(session))
    throw new RuntimeError("INVALID_ARGUMENT", "Session must be a portable profile name (1–128 characters)");
}
export function registryDir(home = stateHome()): string {
  return join(home, "runtime", "v1", hash(realpathSync(packageRoot)));
}
export function recordPath(session: string, home = stateHome()): string {
  validateSession(session);
  return join(registryDir(home), `${hash(session)}.json`);
}
export function privateDirectory(dir: string): void {
  mkdirSync(dir, { recursive: true, mode: 0o700 });
  const stat = lstatSync(dir);
  if (!stat.isDirectory() || stat.isSymbolicLink() ||
      (process.platform !== "win32" && (stat.uid !== process.getuid!() || (stat.mode & 0o077) !== 0)))
    throw new RuntimeError("UNSAFE_STATE_DIRECTORY", "Runtime directory must be private and owned by the current user");
}
export function endpointFor(session: string, generation: string, home = stateHome(), platform: NodeJS.Platform = process.platform): string {
  validateSession(session);
  const key = hash(`${userInfo().username}\0${resolve(home)}\0${packageRoot}\0${session}\0${generation}`);
  if (platform === "win32") return `\\\\.\\pipe\\xiaobei-browser-${key}`;
  const dir = join(tmpdir(), `xbb-${hash(`${userInfo().username}\0${resolve(home)}`)}`);
  const endpoint = join(dir, `${key}.sock`);
  if (Buffer.byteLength(endpoint) > 103)
    throw new RuntimeError("IPC_PATH_TOO_LONG", "Temporary directory path is too long for a Unix socket");
  return endpoint;
}
export function canonicalProfile(value: string): string {
  const absolute = resolve(value.startsWith("~/") ? join(homedir(), value.slice(2)) : value);
  // Resolve existing parents too, so two aliases cannot bypass the profile guard.
  if (existsSync(absolute)) return realpathSync(absolute);
  const parent = dirname(absolute);
  return parent === absolute ? absolute : join(canonicalProfile(parent), absolute.slice(parent.length + 1));
}
