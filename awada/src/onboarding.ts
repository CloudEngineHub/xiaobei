import type { ChannelSetupWizard, DmPolicy, OpenClawConfig } from "openclaw/plugin-sdk/setup";
import { createTopLevelChannelDmPolicy, DEFAULT_ACCOUNT_ID } from "openclaw/plugin-sdk/setup";
import { DEFAULT_RELAY_BASE_URL } from "./accounts.js";
import { probeAwada } from "./probe.js";
import type { AwadaConfig } from "./types.js";

const channel = "awada" as const;

function getAwadaCfg(cfg: OpenClawConfig): AwadaConfig | undefined {
  return cfg.channels?.awada as AwadaConfig | undefined;
}

function isAwadaConfigured(cfg: OpenClawConfig): boolean {
  const c = getAwadaCfg(cfg);
  return Boolean(c?.awadaKey?.trim());
}

function setAwadaAllowFrom(cfg: OpenClawConfig, allowFrom: string[]): OpenClawConfig {
  return {
    ...cfg,
    channels: {
      ...cfg.channels,
      awada: {
        ...getAwadaCfg(cfg),
        allowFrom,
      },
    },
  };
}

const awadaDmPolicy = createTopLevelChannelDmPolicy({
  label: "Awada",
  channel,
  policyKey: "channels.awada.dmPolicy",
  allowFromKey: "channels.awada.allowFrom",
  getCurrent: (cfg) => (getAwadaCfg(cfg)?.dmPolicy ?? "pairing") as DmPolicy,
  getAllowFrom: (cfg) => getAwadaCfg(cfg)?.allowFrom,
  promptAllowFrom: async ({ cfg, prompter }) => {
    const existing = getAwadaCfg(cfg)?.allowFrom ?? [];
    const entry = await prompter.text({
      message: "Awada allowFrom (user_id_external values, comma-separated)",
      placeholder: "user_123, user_456",
      initialValue: existing.join(", "),
      validate: (value) => (String(value ?? "").trim() ? undefined : "Required"),
    });
    const parts = String(entry)
      .split(/[\n,;]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    const unique = [...new Set([...existing, ...parts])];
    return setAwadaAllowFrom(cfg, unique);
  },
});

export const awadaSetupWizard: ChannelSetupWizard = {
  channel,
  resolveAccountIdForConfigure: () => DEFAULT_ACCOUNT_ID,
  resolveShouldPromptAccountIds: () => false,
  status: {
    configuredLabel: "configured",
    unconfiguredLabel: "needs awadaKey",
    configuredHint: "configured",
    unconfiguredHint: "needs awadaKey",
    configuredScore: 2,
    unconfiguredScore: 0,
    resolveConfigured: ({ cfg }) => isAwadaConfigured(cfg),
    resolveStatusLines: async ({ cfg, configured }) => {
      const awadaCfg = getAwadaCfg(cfg);
      const relayBaseUrl = awadaCfg?.relayBaseUrl?.trim() || DEFAULT_RELAY_BASE_URL;
      let probeResult = null;
      if (configured && relayBaseUrl) {
        try {
          probeResult = await probeAwada({
            relayBaseUrl,
            awadaKey: awadaCfg?.awadaKey,
            lane: awadaCfg?.lane,
          });
        } catch {
          // ignore probe errors
        }
      }
      if (!configured) {
        return ["Awada: needs awadaKey"];
      }
      if (probeResult?.ok) {
        return ["Awada: relay reachable"];
      }
      return ["Awada: configured (relay not verified)"];
    },
    resolveSelectionHint: ({ cfg }) => (isAwadaConfigured(cfg) ? "configured" : "needs awadaKey"),
    resolveQuickstartScore: ({ cfg }) => (isAwadaConfigured(cfg) ? 2 : 0),
  },
  credentials: [],
  finalize: async ({ cfg, prompter }) => {
    const awadaCfg = getAwadaCfg(cfg);
    const currentUrl = awadaCfg?.relayBaseUrl?.trim() ?? "";
    const currentKey = awadaCfg?.awadaKey?.trim() ?? "";
    const currentLane = awadaCfg?.lane?.trim() ?? "";

    await prompter.note(
      [
        "Configure awada channel to receive WeChat messages via the relay gateway.",
        "You need:",
        "  1. A running relay with awada-server gateway (exposes /api/v2/awada)",
        "  2. awadaKey issued by relay admin (carries awada:lane:<lane> scope) — required",
        `  3. relayBaseUrl (optional, defaults to ${DEFAULT_RELAY_BASE_URL})`,
        '  4. Lane (optional, server resolves "user" when omitted; ambiguous matches require a lane)',
      ].join("\n"),
      "Awada setup",
    );

    const awadaKey = String(
      await prompter.text({
        message: "awadaKey",
        placeholder: "awada_...",
        initialValue: currentKey,
        validate: (value) => (String(value ?? "").trim() ? undefined : "Required"),
      }),
    ).trim();

    const relayBaseUrl = String(
      await prompter.text({
        message: `Relay base URL (blank = default ${DEFAULT_RELAY_BASE_URL})`,
        placeholder: DEFAULT_RELAY_BASE_URL,
        initialValue: currentUrl,
      }),
    ).trim();

    const laneInput = String(
      await prompter.text({
        message: 'Lane (blank = server default "user")',
        placeholder: "lane id from relay admin",
        initialValue: currentLane,
      }),
    ).trim();

    const awadaChannel: AwadaConfig = { ...awadaCfg, enabled: true, awadaKey };
    if (relayBaseUrl) awadaChannel.relayBaseUrl = relayBaseUrl;
    else delete awadaChannel.relayBaseUrl;
    if (laneInput) awadaChannel.lane = laneInput;
    else delete awadaChannel.lane;
    const next: OpenClawConfig = {
      ...cfg,
      channels: {
        ...cfg.channels,
        awada: awadaChannel,
      },
    };

    // Test connection
    const probeUrl = relayBaseUrl || DEFAULT_RELAY_BASE_URL;
    try {
      const probe = await probeAwada({
        relayBaseUrl: probeUrl,
        awadaKey,
        lane: laneInput,
      });
      if (probe.ok) {
        await prompter.note("Relay reachable!", "Awada connection test");
      } else {
        await prompter.note(
          `Connection failed: ${probe.error ?? "unknown error"}`,
          "Awada connection test",
        );
      }
    } catch (err) {
      await prompter.note(`Connection test failed: ${String(err)}`, "Awada connection test");
    }

    return { cfg: next };
  },
  dmPolicy: awadaDmPolicy,
  disable: (cfg) => ({
    ...cfg,
    channels: {
      ...cfg.channels,
      awada: { ...getAwadaCfg(cfg), enabled: false },
    },
  }),
};
