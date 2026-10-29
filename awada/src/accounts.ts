import { DEFAULT_ACCOUNT_ID } from "openclaw/plugin-sdk/channel-plugin-common";
import type { ClawdbotConfig } from "./runtime-api.js";
import type { AwadaConfig, ResolvedAwadaAccount } from "./types.js";

export const DEFAULT_RELAY_BASE_URL = "https://relay.openclaw-for-business.com/api/v2/awada";

export function resolveAwadaAccount(params: {
  cfg: ClawdbotConfig;
  accountId?: string | null;
}): ResolvedAwadaAccount {
  const root = (params.cfg.channels?.awada ?? {}) as AwadaConfig;
  const accountId = params.accountId?.trim() || resolveDefaultAwadaAccountId(params.cfg);
  const { accounts, defaultAccount: _default, ...common } = root;
  const config = { ...common, ...accounts?.[accountId] };
  const exists =
    !accounts || accountId === DEFAULT_ACCOUNT_ID || Object.hasOwn(accounts, accountId);
  return {
    accountId,
    enabled: root.enabled !== false && config.enabled !== false && exists,
    configured: exists && Boolean(config.awadaKey?.trim()),
    relayBaseUrl: config.relayBaseUrl?.trim() || DEFAULT_RELAY_BASE_URL,
    awadaKey: config.awadaKey?.trim() || undefined,
    lane: config.lane?.trim() || "",
    config,
  };
}

export function listAwadaAccountIds(cfg: ClawdbotConfig): string[] {
  const root = cfg.channels?.awada as AwadaConfig | undefined;
  const ids = Object.keys(root?.accounts ?? {});
  if (root?.awadaKey || ids.length === 0) ids.unshift(DEFAULT_ACCOUNT_ID);
  return [...new Set(ids)];
}

export function resolveDefaultAwadaAccountId(cfg: ClawdbotConfig): string {
  const root = cfg.channels?.awada as AwadaConfig | undefined;
  return (
    root?.defaultAccount?.trim() ||
    (root?.awadaKey ? DEFAULT_ACCOUNT_ID : Object.keys(root?.accounts ?? {})[0]) ||
    DEFAULT_ACCOUNT_ID
  );
}
