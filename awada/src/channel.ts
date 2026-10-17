import type { ChannelMeta, ChannelPlugin } from "openclaw/plugin-sdk/core";
import type { ClawdbotConfig } from "./runtime-api.js";
import {
  buildProbeChannelStatusSummary,
  buildRuntimeAccountStatusSnapshot,
  createDefaultChannelRuntimeState,
} from "openclaw/plugin-sdk/status-helpers";
import { DEFAULT_ACCOUNT_ID } from "openclaw/plugin-sdk/channel-plugin-common";
import { createTextPairingAdapter } from "openclaw/plugin-sdk/channel-pairing";
import {
  resolveAwadaAccount,
  listAwadaAccountIds,
  resolveDefaultAwadaAccountId,
} from "./accounts.js";
import { awadaSetupWizard } from "./onboarding.js";
import { awadaOutbound, awadaMessageAdapter } from "./outbound.js";
import { probeAwada } from "./probe.js";
import { decodeAwadaTo } from "./send.js";
import type { ResolvedAwadaAccount, AwadaConfig } from "./types.js";
import { AwadaConfigJsonSchema } from "./config-schema.js";
import { sendTextToAwada } from "./send.js";

const meta: ChannelMeta = {
  id: "awada",
  label: "Awada",
  selectionLabel: "Awada (WeChat via relay gateway)",
  docsPath: "/channels/awada",
  docsLabel: "awada",
  blurb: "WeChat (enterprise/personal) via awada relay gateway (HTTP/WS transport).",
  aliases: [],
  order: 80,
};

export const awadaPlugin: ChannelPlugin<ResolvedAwadaAccount> = {
  id: "awada",
  meta,
  capabilities: {
    chatTypes: ["direct", "group"],
    polls: false,
    threads: false,
    media: true,
    reactions: false,
    edit: false,
    reply: false,
  },
  reload: { configPrefixes: ["channels.awada"] },
  configSchema: {
    schema: AwadaConfigJsonSchema,
  },
  config: {
    listAccountIds: (cfg) => listAwadaAccountIds(cfg),
    resolveAccount: (cfg, accountId) => resolveAwadaAccount({ cfg, accountId }),
    defaultAccountId: (cfg) => resolveDefaultAwadaAccountId(cfg),
    setAccountEnabled: ({ cfg, accountId, enabled }) => {
      const current = (cfg.channels?.awada ?? {}) as AwadaConfig;
      const awada =
        accountId === DEFAULT_ACCOUNT_ID && !current.accounts?.[accountId]
          ? { ...current, enabled }
          : {
              ...current,
              accounts: {
                ...current.accounts,
                [accountId]: { ...current.accounts?.[accountId], enabled },
              },
            };
      return { ...cfg, channels: { ...cfg.channels, awada } };
    },
    deleteAccount: ({ cfg, accountId }) => {
      const next = { ...cfg } as ClawdbotConfig;
      const nextChannels = { ...cfg.channels };
      const current = { ...(cfg.channels?.awada ?? {}) } as AwadaConfig;
      if (accountId === DEFAULT_ACCOUNT_ID && !current.accounts?.[accountId]) {
        if (!Object.keys(current.accounts ?? {}).length)
          delete (nextChannels as Record<string, unknown>).awada;
        else {
          delete current.awadaKey;
          delete current.lane;
          nextChannels.awada = current;
        }
      } else {
        current.accounts = { ...current.accounts };
        delete current.accounts[accountId];
        if (current.defaultAccount === accountId) delete current.defaultAccount;
        nextChannels.awada = current;
      }
      if (Object.keys(nextChannels).length > 0) {
        next.channels = nextChannels;
      } else {
        delete next.channels;
      }
      return next;
    },
    isConfigured: (account) => account.configured,
    describeAccount: (account) => ({
      accountId: account.accountId,
      enabled: account.enabled,
      configured: account.configured,
      relayBaseUrl: account.relayBaseUrl,
    }),
    resolveAllowFrom: ({ cfg, accountId }) => {
      const account = resolveAwadaAccount({ cfg, accountId });
      return (account.config?.allowFrom ?? []).map((entry) => String(entry));
    },
    formatAllowFrom: ({ allowFrom }) =>
      allowFrom.map((entry) => String(entry).trim()).filter(Boolean),
  },
  setup: {
    resolveAccountId: () => DEFAULT_ACCOUNT_ID,
    applyAccountConfig: ({ cfg, accountId: _accountId, input: _input }) => ({
      ...cfg,
      channels: {
        ...cfg.channels,
        awada: {
          ...(cfg.channels?.awada as AwadaConfig | undefined),
          enabled: true,
        },
      },
    }),
  },
  setupWizard: awadaSetupWizard,
  outbound: awadaOutbound,
  message: awadaMessageAdapter,
  actions: {
    describeMessageTool: ({ cfg }) =>
      listAwadaAccountIds(cfg).some(
        (accountId) => resolveAwadaAccount({ cfg, accountId }).configured,
      )
        ? { actions: ["send"] }
        : null,
  },
  pairing: createTextPairingAdapter({
    idLabel: "awadaUserId",
    message: "OpenClaw: your access has been approved.",
    normalizeAllowEntry: (raw) => raw.trim().replace(/[\x00-\x1f\x7f]/g, ""),
    notify: async ({ cfg, id, accountId }) => {
      const account = resolveAwadaAccount({ cfg, accountId });
      if (!account.relayBaseUrl || !account.awadaKey) throw new Error("Awada is not configured");
      await sendTextToAwada({
        relayBaseUrl: account.relayBaseUrl,
        awadaKey: account.awadaKey,
        lane: account.lane,
        target: { lane: account.lane, tenant_id: "", channel_id: "0", user_id_external: id },
        text: "OpenClaw: your access has been approved.",
      });
    },
  }),
  messaging: {
    targetResolver: {
      looksLikeId: (raw) => /^(?:awada:|user:|chat:)/.test(raw),
      resolveTarget: async ({ input }) => {
        const decoded = decodeAwadaTo(input);
        if (!decoded && !/^(?:awada:)?(?:user|chat):.+/s.test(input)) return null;
        const isGroup = decoded ? decoded.channel_id !== "0" : /^(?:awada:)?chat:/.test(input);
        return {
          to: input,
          kind: isGroup ? ("group" as const) : ("user" as const),
          source: "normalized" as const,
        };
      },
    },
  },
  status: {
    defaultRuntime: createDefaultChannelRuntimeState(DEFAULT_ACCOUNT_ID, { port: null }),
    buildChannelSummary: ({ snapshot }) => buildProbeChannelStatusSummary(snapshot, { port: null }),
    probeAccount: async ({ account }) =>
      probeAwada({
        relayBaseUrl: account.relayBaseUrl,
        accountId: account.accountId,
        awadaKey: account.awadaKey,
        lane: account.lane,
      }),
    buildAccountSnapshot: ({ account, runtime, probe }) => ({
      accountId: account.accountId,
      enabled: account.enabled,
      configured: account.configured,
      relayBaseUrl: account.relayBaseUrl,
      ...buildRuntimeAccountStatusSnapshot({ runtime, probe }),
      port: null,
    }),
  },
  gateway: {
    startAccount: async (ctx) => {
      const { monitorAwadaProvider } = await import("./monitor.js");
      ctx.log?.info(`starting awada[${ctx.accountId}]`);
      return monitorAwadaProvider({
        config: ctx.cfg,
        runtime: ctx.runtime,
        abortSignal: ctx.abortSignal,
        accountId: ctx.accountId,
      });
    },
  },
};
