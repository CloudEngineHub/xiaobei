import {
  formatAgentEnvelope,
  resolveEnvelopeFormatOptions,
} from "openclaw/plugin-sdk/channel-inbound";
import {
  bindIngressLifecycleToReplyOptions,
  type ChannelIngressMonitorLifecycle,
} from "openclaw/plugin-sdk/channel-outbound";
import { fanInChannelIngressLifecycles } from "openclaw/plugin-sdk/channel-ingress-runtime";
import { createRuntimeConfigReader } from "openclaw/plugin-sdk/runtime-config-snapshot";
import type { ClawdbotConfig, RuntimeEnv } from "./runtime-api.js";
import type { InboundEvent } from "./redis-types.js";
import { resolveAwadaAccount } from "./accounts.js";
import { getAwadaRuntime } from "./runtime.js";
import {
  awadaConversationKey,
  isAwadaGroup,
  resolveAwadaIngress,
  resolveAwadaGroupPolicy,
} from "./policy.js";
import { createChannelHistoryWindow, type HistoryEntry } from "openclaw/plugin-sdk/reply-history";
import { resolvePromptHistoryLimit } from "openclaw/plugin-sdk/number-runtime";
import { buildOutboundTarget, encodeAwadaTo } from "./send.js";
import { createAwadaReplyDispatcher } from "./reply-dispatcher.js";
import { resolveAwadaInboundMedia } from "./inbound-media.js";
import { recordAwadaSystemEvent } from "./events.js";
import { isAwadaLocalCommand } from "./commands.js";
import { prepareAwadaMentions } from "./mentions.js";
import { createAwadaSequentialQueue } from "./sequential-queue.js";
import { awadaVoiceMessageId, transcribeAwadaVoice } from "./transcription.js";

export type AwadaIngressLifecycle = Omit<ChannelIngressMonitorLifecycle, "admission">;
export function extractAwadaText(event: InboundEvent): string {
  return event.payload
    .filter((item) => item.type === "text")
    .map((item) => (item.type === "text" ? item.text : ""))
    .join("\n")
    .trim();
}

type Entry = { event: InboundEvent; lifecycle?: AwadaIngressLifecycle };

export async function dispatchAwadaMessage(params: {
  cfg: ClawdbotConfig;
  event: InboundEvent;
  accountId: string;
  runtime?: RuntimeEnv;
  lifecycle?: AwadaIngressLifecycle;
  mentionsPrepared?: boolean;
  chatHistories?: Map<string, HistoryEntry[]>;
}): Promise<void> {
  const { cfg, accountId, lifecycle } = params;
  const event = params.mentionsPrepared ? params.event : prepareAwadaMentions(params.event);
  if (event.type !== "MESSAGE_NEW") throw new Error("Only MESSAGE_NEW may enter the chat pipeline");
  const runtime = params.runtime ?? { log: console.log, error: console.error, exit: () => {} };
  const account = resolveAwadaAccount({ cfg, accountId });
  if (!account.enabled || !account.configured || !account.relayBaseUrl || !account.awadaKey) return;
  const core = getAwadaRuntime();
  const rawText = extractAwadaText(event);
  const isGroup = isAwadaGroup(event);
  const sender = event.meta.sender_name ?? event.meta.user_id_external;
  const { requireMention } = resolveAwadaGroupPolicy(cfg, account);
  const historyLimit = resolvePromptHistoryLimit(
    account.config.historyLimit ?? cfg.messages?.groupChat?.historyLimit,
  );
  const historyKey = awadaConversationKey(event);
  const history = params.chatHistories
    ? createChannelHistoryWindow({ historyMap: params.chatHistories })
    : undefined;
  const ingress = await resolveAwadaIngress({ cfg, account, event, commandText: rawText });
  if (ingress.ingress.admission !== "dispatch") {
    if (
      isGroup &&
      ingress.senderAccess.decision === "allow" &&
      requireMention &&
      event.meta.at_me !== true
    ) {
      history?.record({
        historyKey,
        limit: historyLimit,
        entry: {
          sender: event.meta.user_id_external,
          body: `${sender}: ${rawText}`,
          timestamp: event.timestamp * 1000,
          messageId: event.event_id,
        },
      });
    }
    return;
  }
  const credentials = {
    relayBaseUrl: account.relayBaseUrl,
    awadaKey: account.awadaKey,
    lane: event.meta.lane || account.lane,
  };
  const target = buildOutboundTarget(event.meta);
  const to = encodeAwadaTo(target);
  let transcript: string | undefined;
  const voiceMessageId = awadaVoiceMessageId(event);
  if (voiceMessageId) {
    try {
      transcript = (
        await transcribeAwadaVoice(credentials, voiceMessageId, {
          requestId: `inbound-${event.event_id}`,
          signal: lifecycle?.abortSignal,
        })
      ).text;
    } catch (error) {
      lifecycle?.abortSignal.throwIfAborted();
      runtime.log(
        `awada: native transcription failed; trying shared audio preflight: ${String(error)}`,
      );
    }
  }
  const { media, failures } = await resolveAwadaInboundMedia({
    event,
    credentials,
    maxBytes: (account.config.mediaMaxMb ?? 20) * 1024 * 1024,
    log: runtime.log,
  });
  // Match Feishu's shared audio preflight; raw slash/control text never gains authority from a quote.
  if (!transcript && event.payload.some((item) => item.type === "audio") && media.length) {
    try {
      const { transcribeFirstAudio } = await import("openclaw/plugin-sdk/media-runtime");
      transcript = await transcribeFirstAudio({
        ctx: { media, ChatType: isGroup ? "group" : "direct" },
        cfg,
      });
    } catch (err) {
      runtime.log(`awada: audio preflight failed: ${String(err)}`);
    }
  }
  const commandText = rawText || transcript || "";
  let content = [rawText, transcript !== rawText ? transcript : undefined, ...failures]
    .filter(Boolean)
    .join("\n\n");
  const providerItems = event.payload.filter((item) => item.type === "provider");
  if (providerItems.length || failures.length) {
    await recordAwadaSystemEvent(accountId, event, account.lane);
  }
  if (providerItems.length) {
    content = [
      content,
      "[Awada message contains structured content; inspect it with awada_api events]",
    ]
      .filter(Boolean)
      .join("\n\n");
  }
  // A supplied quote is context only. Never promote it into raw/command bodies.
  const quote = event.meta.quote;
  const quoted =
    quote && typeof quote === "object" ? (quote as { id?: string; body?: string }) : undefined;
  if (!content && media.length === 0 && !quoted?.body) return;
  const messageBody = `[message_id: ${event.event_id}]\n${sender}: ${quoted?.body ? `[Replying to: "${quoted.body}"]\n\n` : ""}${content}`;
  const route = core.channel.routing.resolveAgentRoute({
    cfg,
    channel: "awada",
    accountId,
    peer: { kind: isGroup ? "group" : "direct", id: awadaConversationKey(event) },
  });
  const boundIngress = await resolveAwadaIngress({
    cfg,
    account,
    event,
    commandText,
    mayPair: false,
    contextBinding: {
      agentId: route.agentId,
      sessionKey: route.sessionKey,
      nativeChannelId: isGroup ? event.meta.channel_id : event.meta.user_id_external,
      messageId: event.event_id,
      inboundEventKind: "user_request",
    },
  });
  if (boundIngress.ingress.admission !== "dispatch") return;
  const timestamp = event.timestamp * 1000;
  const body = formatAgentEnvelope({
    channel: "Awada",
    from: isGroup
      ? `${event.meta.channel_id}:${event.meta.user_id_external}`
      : event.meta.user_id_external,
    timestamp: new Date(timestamp),
    envelope: resolveEnvelopeFormatOptions(cfg),
    body: messageBody,
  });
  const combinedBody =
    isGroup && history
      ? history.buildPendingContext({
          historyKey,
          limit: historyLimit,
          currentMessage: body,
          formatEntry: (entry) =>
            formatAgentEnvelope({
              channel: "Awada",
              from: `${event.meta.channel_id}:${entry.sender}`,
              timestamp: entry.timestamp,
              body: entry.body,
              envelope: resolveEnvelopeFormatOptions(cfg),
            }),
        })
      : body;
  const ctxPayload = await core.channel.inbound.buildContext({
    channel: "awada",
    channelIngress: boundIngress,
    messageId: event.event_id,
    timestamp,
    from: `awada:${event.meta.user_id_external}`,
    sender: { id: event.meta.user_id_external, name: sender, isBot: false },
    conversation: {
      kind: isGroup ? "group" : "direct",
      id: isGroup ? event.meta.channel_id : event.meta.user_id_external,
      nativeChannelId: isGroup ? event.meta.channel_id : event.meta.user_id_external,
      routePeer: { kind: isGroup ? "group" : "direct", id: awadaConversationKey(event) },
      label: isGroup ? event.meta.channel_name : undefined,
    },
    route: { ...route, routeSessionKey: route.sessionKey },
    reply: { to },
    message: {
      body: combinedBody,
      bodyForAgent: messageBody,
      rawBody: commandText,
      commandBody: commandText,
      inboundHistory: isGroup
        ? history?.buildInboundHistory({ historyKey, limit: historyLimit })
        : undefined,
    },
    media,
    sessionTranscript: { historyLimit: isGroup ? historyLimit : 0 },
    supplemental: { quote: quoted?.body ? { id: quoted.id, body: quoted.body } : undefined },
    access: {
      commands: { authorized: boundIngress.commandAccess.authorized },
      mentions: {
        canDetectMention: isGroup,
        wasMentioned: event.meta.at_me === true,
        requireMention: isGroup && requireMention,
      },
    },
    extra: {
      Transcript: transcript,
      GroupSubject: isGroup ? (event.meta.channel_name ?? event.meta.channel_id) : undefined,
    },
  });
  const { dispatcherOptions, delivery, replyOptions } = createAwadaReplyDispatcher({
    cfg,
    agentId: route.agentId,
    runtime,
    ...credentials,
    target,
    inboundEventId: event.event_id,
    accountId,
  });
  await core.channel.inbound.run({
    channel: "awada",
    accountId,
    raw: event,
    adapter: {
      ingest: () => ({
        id: event.event_id,
        timestamp,
        rawText: commandText,
        textForAgent: ctxPayload.BodyForAgent,
        textForCommands: ctxPayload.CommandBody,
        raw: event,
      }),
      resolveTurn: () => ({
        cfg,
        channel: "awada",
        accountId,
        route: { agentId: route.agentId, sessionKey: route.sessionKey },
        ctxPayload,
        record: {
          updateLastRoute: { sessionKey: route.sessionKey, channel: "awada", to, accountId },
        },
        history: { isGroup, historyKey, historyMap: params.chatHistories, limit: historyLimit },
        dispatcherOptions,
        delivery,
        replyOptions: {
          ...replyOptions,
          ...(lifecycle ? bindIngressLifecycleToReplyOptions(lifecycle) : {}),
        },
      }),
    },
  });
}

/** Same host debouncer and key dimensions as Feishu, with explicit Relay lane isolation. */
export function createAwadaMessageHandler(params: {
  cfg: ClawdbotConfig;
  accountId: string;
  runtime?: RuntimeEnv;
}) {
  const core = getAwadaRuntime();
  const readConfig = createRuntimeConfigReader(params.cfg);
  const chatHistories = new Map<string, HistoryEntry[]>();
  const keys = new Set<string>();
  const enqueue = createAwadaSequentialQueue({
    onTaskTimeout: (key, timeout) => {
      params.runtime?.error(
        `awada: turn exceeded ${timeout} ms in ${key}; releasing the chat queue`,
      );
    },
  });
  const resolveDelay = () =>
    core.channel.debounce.resolveInboundDebounceMs({ cfg: readConfig(), channel: "awada" });
  const debouncer = core.channel.debounce.createInboundDebouncer<Entry>({
    debounceMs: resolveDelay(),
    resolveDebounceMs: resolveDelay,
    buildKey: ({ event }) => {
      const key = JSON.stringify([
        params.accountId,
        awadaConversationKey(event),
        event.meta.user_id_external,
      ]);
      keys.add(key);
      return key;
    },
    shouldDebounce: ({ event }) =>
      event.payload.every((item) => item.type === "text") &&
      Boolean(extractAwadaText(event)) &&
      !isAwadaLocalCommand(extractAwadaText(event)) &&
      !core.channel.commands.isControlCommandMessage(extractAwadaText(event), readConfig()),
    onFlush: (entries, createFlush) => {
      const active = entries.filter((entry) => !entry.lifecycle?.abortSignal.aborted);
      const aggregate = fanInChannelIngressLifecycles(active.map((entry) => entry.lifecycle));
      return createFlush({
        lifecycle: aggregate.lifecycle,
        dispatch: async (lifecycle) => {
          if (!active.length) return;
          const last = active[active.length - 1]!;
          const event =
            active.length === 1
              ? last.event
              : {
                  ...last.event,
                  meta: {
                    ...last.event.meta,
                    at_me: active.some((entry) => entry.event.meta.at_me === true),
                  },
                  payload: [
                    {
                      type: "text" as const,
                      text: active.map((entry) => extractAwadaText(entry.event)).join("\n"),
                    },
                  ],
                };
          const key = awadaConversationKey(event);
          const task = enqueue(key, async () => {
            if (lifecycle.abortSignal.aborted) {
              await aggregate.cancel();
              return;
            }
            await dispatchAwadaMessage({
              ...params,
              cfg: readConfig(),
              event,
              lifecycle,
              mentionsPrepared: true,
              chatHistories,
            });
            await aggregate.settle();
          });
          try {
            await task;
          } catch (err) {
            await aggregate.abandon(err);
            throw err;
          }
        },
      });
    },
    onError: (err) =>
      (params.runtime?.error ?? console.error)(`awada: inbound flush failed: ${String(err)}`),
  });
  return {
    receive: async (event: InboundEvent, lifecycle?: AwadaIngressLifecycle) => {
      await debouncer.enqueue({ event: prepareAwadaMentions(event), lifecycle });
      return lifecycle ? { kind: "deferred" as const } : undefined;
    },
    stop: async () => {
      await Promise.all([...keys].map((key) => debouncer.flushKey(key)));
      await debouncer.drain();
      keys.clear();
    },
  };
}

export async function handleAwadaMessage(params: {
  cfg: ClawdbotConfig;
  event: InboundEvent;
  runtime?: RuntimeEnv;
  accountId?: string;
}) {
  const handler = createAwadaMessageHandler({
    ...params,
    accountId: params.accountId ?? "default",
  });
  await handler.receive(params.event);
  await handler.stop();
}
