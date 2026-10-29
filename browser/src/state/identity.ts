/** A persistent SDK identity. Version 1 (Apify/BrowserForge) requires a new profile. */
import { existsSync, mkdirSync, writeFileSync, renameSync, unlinkSync } from "node:fs";
import { join } from "node:path";
import { createHash, randomUUID } from "node:crypto";
import { newFingerprint, proxyGeo } from "../driver/sdk.js";
import { IDENTITY_FILENAME, IDENTITY_VERSION, SDK, hostOS, validateProfile, type Identity, type HostOS } from "./identity-schema.js";
export type { Identity, HostOS };

function writeIdentity(path: string, identity: Identity): void {
  const temp = `${path}.${randomUUID()}.tmp`;
  try {
    writeFileSync(temp, JSON.stringify(identity, null, 2), { mode: 0o600, flag: "wx" });
    renameSync(temp, path);
  } finally { try { unlinkSync(temp); } catch {} }
}
export function readIdentitySummary(persistentDir: string): { os: HostOS; locale: string | null; fingerprintHash: string } | null {
  const path = join(persistentDir, IDENTITY_FILENAME);
  if (!existsSync(path)) return null;
  const identity = validateProfile(persistentDir)!;
  return { os: identity.os, locale: identity.locale,
    fingerprintHash: createHash("sha256").update(JSON.stringify(identity.fingerprint)).digest("hex").slice(0, 16) };
}
export async function loadOrCreate(persistentDir: string, locale: string | null, proxy: string | null,
  geoip: boolean, window?: [number, number] | null): Promise<Identity> {
  const path = join(persistentDir, IDENTITY_FILENAME);
  let identity: Identity;
  const previous = validateProfile(persistentDir);
  if (previous) identity = previous;
  else {
    // A populated Firefox profile with no matching identity must not silently get a new device.
    identity = { version: IDENTITY_VERSION, sdk: SDK, created_at: new Date().toISOString(),
      os: hostOS(), locale, fingerprint: newFingerprint(hostOS(), window), config: {} };
  }
  if (locale !== null) identity.locale = locale;
  if (proxy && geoip) {
    const config = await proxyGeo(proxy, identity.config);
    delete identity.config["webrtc:ipv4"]; delete identity.config["webrtc:ipv6"];
    Object.assign(identity.config, config);
  } else identity.config = {};
  mkdirSync(persistentDir, { recursive: true });
  writeIdentity(path, identity);
  return identity;
}
export function toLaunchOptions(identity: Identity): Record<string, unknown> {
  const opts: Record<string, unknown> = { fingerprint: identity.fingerprint, os: identity.os, config: { ...identity.config } };
  if (identity.locale) {
    const locales = identity.locale.split(",").map(s => s.trim()).filter(Boolean);
    if (locales.length) opts.locale = locales.length > 1 ? locales : locales[0];
  }
  if (identity.config["webrtc:ipv4"]) opts.firefox_user_prefs = { "network.dns.disableIPv6": true };
  return opts;
}
