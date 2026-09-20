import { describe, expect, it } from "vitest";
import {
  DEFAULT_RELAY_BASE_URL,
  listAwadaAccountIds,
  resolveAwadaAccount,
  resolveDefaultAwadaAccountId,
} from "../../awada/src/accounts.js";
import type { ClawdbotConfig } from "openclaw/plugin-sdk";

function makeConfig(awada?: Record<string, unknown>): ClawdbotConfig {
  return { channels: awada !== undefined ? { awada } : undefined } as ClawdbotConfig;
}

const FULL = { awadaKey: "awada_123", lane: "user" };

describe("resolveAwadaAccount", () => {
  it("returns default values when no awada config is present", () => {
    const account = resolveAwadaAccount({ cfg: makeConfig() });
    expect(account.accountId).toBe("default");
    expect(account.enabled).toBe(true);
    expect(account.configured).toBe(false);
    expect(account.relayBaseUrl).toBe(DEFAULT_RELAY_BASE_URL);
    expect(account.awadaKey).toBeUndefined();
    expect(account.lane).toBe("");
  });

  it("resolves awadaKey and marks configured=true with only awadaKey", () => {
    const account = resolveAwadaAccount({ cfg: makeConfig({ awadaKey: "awada_123" }) });
    expect(account.configured).toBe(true);
    expect(account.awadaKey).toBe("awada_123");
    expect(account.relayBaseUrl).toBe(DEFAULT_RELAY_BASE_URL);
    expect(account.lane).toBe("");
  });

  it("resolves relayBaseUrl+awadaKey+lane and marks configured=true", () => {
    const account = resolveAwadaAccount({ cfg: makeConfig(FULL) });
    expect(account.configured).toBe(true);
    expect(account.relayBaseUrl).toBe(DEFAULT_RELAY_BASE_URL);
    expect(account.awadaKey).toBe("awada_123");
    expect(account.lane).toBe("user");
  });

  it("trims whitespace from relayBaseUrl/awadaKey/lane", () => {
    const account = resolveAwadaAccount({
      cfg: makeConfig({
        relayBaseUrl: "  https://relay.example.com  ",
        awadaKey: "  awada_123  ",
        lane: "  user  ",
      }),
    });
    expect(account.relayBaseUrl).toBe("https://relay.example.com");
    expect(account.awadaKey).toBe("awada_123");
    expect(account.lane).toBe("user");
  });

  it("marks configured=false when awadaKey missing", () => {
    const account = resolveAwadaAccount({
      cfg: makeConfig({ relayBaseUrl: "https://relay.example.com", lane: "user" }),
    });
    expect(account.configured).toBe(false);
  });

  it("defaults relayBaseUrl to the official relay domain when unset", () => {
    const account = resolveAwadaAccount({ cfg: makeConfig({ awadaKey: "awada_123" }) });
    expect(account.relayBaseUrl).toBe(DEFAULT_RELAY_BASE_URL);
    expect(account.configured).toBe(true);
  });

  it("marks configured=true when lane missing (server defaults to User)", () => {
    const account = resolveAwadaAccount({
      cfg: makeConfig({ awadaKey: "awada_123" }),
    });
    expect(account.configured).toBe(true);
    expect(account.lane).toBe("");
  });

  it("respects enabled=false", () => {
    const account = resolveAwadaAccount({ cfg: makeConfig({ ...FULL, enabled: false }) });
    expect(account.enabled).toBe(false);
  });

  it("defaults enabled to true when not set", () => {
    const account = resolveAwadaAccount({ cfg: makeConfig(FULL) });
    expect(account.enabled).toBe(true);
  });

  it("uses custom lane when provided", () => {
    const account = resolveAwadaAccount({ cfg: makeConfig({ ...FULL, lane: "cs" }) });
    expect(account.lane).toBe("cs");
  });

  it("uses provided accountId", () => {
    const account = resolveAwadaAccount({ cfg: makeConfig(), accountId: "custom-id" });
    expect(account.accountId).toBe("custom-id");
  });

  it("trims and falls back to default when accountId is blank", () => {
    const account = resolveAwadaAccount({ cfg: makeConfig(), accountId: "  " });
    expect(account.accountId).toBe("default");
  });
});

describe("listAwadaAccountIds", () => {
  it("always returns [default]", () => {
    expect(listAwadaAccountIds({} as ClawdbotConfig)).toEqual(["default"]);
  });
});

describe("resolveDefaultAwadaAccountId", () => {
  it("always returns default", () => {
    expect(resolveDefaultAwadaAccountId({} as ClawdbotConfig)).toBe("default");
  });
});
