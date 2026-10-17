import { createChannelPairingController } from "openclaw/plugin-sdk/channel-pairing";
import type { ChannelIngressContextBinding } from "openclaw/plugin-sdk/channel-ingress-runtime";
import {
  resolveDefaultGroupPolicy,
  resolveOpenProviderRuntimeGroupPolicy,
} from "openclaw/plugin-sdk/runtime-group-policy";
import { getAwadaRuntime } from "./runtime.js";
import { sendTextToAwada, buildOutboundTarget } from "./send.js";
import type { ClawdbotConfig } from "./runtime-api.js";
import type { InboundEvent } from "./redis-types.js";
import type { ResolvedAwadaAccount } from "./types.js";
import { isAwadaLocalCommand } from "./commands.js";

export function normalizeAwadaPeer(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/[\x00-\x1f\x7f]/g, "");
}
export function isAwadaGroup(event: InboundEvent): boolean {
  return Boolean(event.meta.channel_id && event.meta.channel_id !== "0");
}
export function awadaConversationKey(event: InboundEvent): string {
  return JSON.stringify([
    event.meta.lane,
    event.meta.provider_account_id ?? event.meta.tenant_id,
    isAwadaGroup(event) ? "group" : "direct",
    isAwadaGroup(event) ? event.meta.channel_id : event.meta.user_id_external,
  ]);
}

export function resolveAwadaGroupPolicy(cfg: ClawdbotConfig, account: ResolvedAwadaAccount) {
  const { groupPolicy } = resolveOpenProviderRuntimeGroupPolicy({
    providerConfigPresent: cfg.channels?.awada !== undefined,
    groupPolicy: account.config.groupPolicy,
    defaultGroupPolicy: resolveDefaultGroupPolicy(cfg),
  });
  return { groupPolicy, requireMention: account.config.requireMention ?? groupPolicy !== "open" };
}

/** Feishu's same two-stage group checks and host-owned DM/command authorization. */
export async function resolveAwadaIngress(params: {
  cfg: ClawdbotConfig;
  account: ResolvedAwadaAccount;
  event: InboundEvent;
  commandText: string;
  contextBinding?: ChannelIngressContextBinding;
  mayPair?: boolean;
}) {
  const { cfg, account, event } = params;
  const core = getAwadaRuntime();
  const config = account.config;
  const isGroup = isAwadaGroup(event);
  const { groupPolicy, requireMention } = resolveAwadaGroupPolicy(cfg, account);
  const mutable =
    event.meta.identity_kind === "normalized_nickname" || event.meta.platform === "worktool";
  const pairing = createChannelPairingController({
    core,
    channel: "awada",
    accountId: account.accountId,
  });
  const resolver = core.channel.inbound.ingress.createResolver({
    channelId: "awada",
    accountId: account.accountId,
    cfg,
    identity: {
      primary: {
        normalize: mutable
          ? normalizeAwadaPeer
          : (raw) => raw.trim().replace(/[\x00-\x1f\x7f]/g, ""),
        authentication: mutable ? "mutable" : "asserted",
      },
    },
    // WorkTool only offers names. Retain that classification while allowing explicitly configured name matches.
    ...(mutable ? { mutableIdentifierMatching: "enabled" as const } : {}),
    readStoreAllowFrom: pairing.readAllowFromStore,
  });
  const conversation = {
    kind: isGroup ? ("group" as const) : ("direct" as const),
    id: isGroup ? event.meta.channel_id : event.meta.user_id_external,
  };
  if (isGroup) {
    const group = await resolver.message({
      subject: { stableId: event.meta.channel_id },
      conversation,
      dmPolicy: "disabled",
      groupPolicy,
      groupAllowFrom: config.groupAllowFrom ?? [],
    });
    if (group.ingress.admission !== "dispatch") return group;
  }
  const result = await resolver.message({
    subject: { stableId: event.meta.user_id_external },
    conversation,
    event: { mayPair: !isGroup && params.mayPair !== false },
    dmPolicy: config.dmPolicy ?? "pairing",
    groupPolicy: config.groupSenderAllowFrom?.length ? "allowlist" : "open",
    allowFrom: config.allowFrom ?? [],
    groupAllowFrom: config.groupSenderAllowFrom ?? [],
    ...(isGroup
      ? {
          mentionFacts: { canDetectMention: true, wasMentioned: event.meta.at_me === true },
          policy: {
            activation: { requireMention, allowTextCommands: false },
          },
        }
      : {}),
    command: {
      hasControlCommand:
        isAwadaLocalCommand(params.commandText) ||
        core.channel.commands.isControlCommandMessage(params.commandText, cfg),
    },
    ...(params.contextBinding ? { contextBinding: params.contextBinding } : {}),
  });
  if (
    result.ingress.admission === "pairing-required" &&
    params.mayPair !== false &&
    account.relayBaseUrl &&
    account.awadaKey
  ) {
    await pairing.issueChallenge({
      senderId: event.meta.user_id_external,
      senderIdLine: `Your Awada user id: ${event.meta.user_id_external}`,
      meta: { name: event.meta.sender_name ?? event.meta.user_id_external },
      sendPairingReply: async (text) => {
        await sendTextToAwada({
          relayBaseUrl: account.relayBaseUrl!,
          awadaKey: account.awadaKey!,
          lane: account.lane,
          target: buildOutboundTarget(event.meta),
          text,
          sourceEventId: event.event_id,
          requestId: `pairing-${event.event_id}`,
        });
      },
    });
  }
  return result;
}
