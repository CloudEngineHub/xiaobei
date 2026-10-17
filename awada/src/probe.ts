import type { AwadaProbeResult } from "./types.js";
import { awadaRequest, awadaApiUrl, getAwadaCapabilities } from "./api.js";

const PROBE_TIMEOUT_MS = 5000;

export function validateAwadaRelayBaseUrl(relayBaseUrl: string): string | null {
  const value = relayBaseUrl.trim();
  if (!value) {
    return "missing relayBaseUrl";
  }
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    return "invalid relayBaseUrl format";
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return "invalid relayBaseUrl protocol (expected http:// or https://)";
  }
  if (!parsed.hostname) {
    return "invalid relayBaseUrl host";
  }
  return null;
}

/**
 * Probe relay gateway connectivity for an awada account.
 * Hits GET /api/v2/awada/health (no auth). Returns ok=true if the gateway is reachable
 * and its Redis is up. Auth (awadaKey via X-OFB-Key header + lane scope) is verified on the first real call.
 */
export async function probeAwada(params: {
  relayBaseUrl?: string;
  accountId?: string;
  awadaKey?: string;
  lane?: string;
}): Promise<AwadaProbeResult> {
  const { relayBaseUrl } = params;

  if (!relayBaseUrl) {
    return { ok: false, error: "missing relayBaseUrl" };
  }

  const normalized = relayBaseUrl.trim();
  const validationError = validateAwadaRelayBaseUrl(normalized);
  if (validationError) {
    return { ok: false, relayBaseUrl: normalized, error: validationError };
  }

  try {
    awadaApiUrl(normalized, "/health");
    const json = await awadaRequest<{ redis?: boolean; version?: string }>(
      { relayBaseUrl: normalized, awadaKey: "", lane: "" },
      "/health",
      { public: true, timeoutMs: PROBE_TIMEOUT_MS },
    );
    if (!json.redis) {
      return { ok: false, relayBaseUrl: normalized, error: "relay reachable but redis down" };
    }
    if (params.awadaKey)
      await getAwadaCapabilities({
        relayBaseUrl: normalized,
        awadaKey: params.awadaKey,
        lane: params.lane ?? "",
      });
    return { ok: true, relayBaseUrl: normalized };
  } catch (err) {
    return {
      ok: false,
      relayBaseUrl: normalized,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}
