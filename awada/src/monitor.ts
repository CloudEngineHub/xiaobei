import { createStandardRawEventIngressMonitor } from "openclaw/plugin-sdk/channel-ingress-runtime";
import type { ClawdbotConfig, RuntimeEnv } from "./runtime-api.js";
import type { InboundEvent } from "./redis-types.js";
import { resolveAwadaAccount } from "./accounts.js";
import { createAwadaMessageHandler } from "./message-handler.js";
import { runGatewayClient } from "./transport.js";
import { getAwadaRuntime } from "./runtime.js";
import { awadaConversationKey } from "./policy.js";
import { recordAwadaSystemEvent } from "./events.js";
import { parseAwadaJson, stringifyAwadaJson } from "./api.js";

export type MonitorAwadaOpts = {
  config?: ClawdbotConfig;
  runtime?: RuntimeEnv;
  abortSignal?: AbortSignal;
  accountId?: string;
};

export function validateAwadaEvent(raw: unknown): InboundEvent {
  if (!raw || typeof raw !== "object") throw new Error("Awada event must be an object");
  const event = raw as InboundEvent;
  if (
    event.schema_version !== 1 ||
    !event.event_id ||
    typeof event.event_id !== "string" ||
    !event.type ||
    !Number.isFinite(event.timestamp) ||
    !event.meta ||
    typeof event.meta !== "object" ||
    !Array.isArray(event.payload)
  ) {
    throw new Error("Invalid Awada envelope");
  }
  if (
    event.type === "MESSAGE_NEW" &&
    (typeof event.meta.user_id_external !== "string" ||
      !event.meta.user_id_external ||
      typeof event.meta.channel_id !== "string" ||
      typeof event.meta.lane !== "string")
  )
    throw new Error("Invalid Awada message identity");
  return event;
}

export function createAwadaIngressMonitor(params: {
  cfg: ClawdbotConfig;
  accountId: string;
  runtime?: RuntimeEnv;
  abortSignal?: AbortSignal;
}) {
  const handler = createAwadaMessageHandler(params);
  const core = getAwadaRuntime();
  const ingress = createStandardRawEventIngressMonitor({
    queue: () =>
      core.state.openChannelIngressQueue<{ version: 1; rawEvent: string }>({
        accountId: params.accountId,
      }),
    inspect: (raw: InboundEvent) => {
      const event = validateAwadaEvent(raw);
      return {
        eventId: JSON.stringify([event.meta.lane, event.event_id]),
        laneKey:
          event.type === "MESSAGE_NEW"
            ? awadaConversationKey(event)
            : JSON.stringify([event.meta.lane, "system"]),
      };
    },
    payload: {
      serialize: (event) => stringifyAwadaJson(event),
      deserialize: (raw) => validateAwadaEvent(parseAwadaJson(raw)),
      createClaimError: (kind) => new Error(`Invalid Awada ingress claim: ${kind}`),
    },
    deliver: async (event, lifecycle) => {
      if (event.type === "MESSAGE_NEW") return handler.receive(event, lifecycle);
      await recordAwadaSystemEvent(
        params.accountId,
        event,
        resolveAwadaAccount({ cfg: params.cfg, accountId: params.accountId }).lane,
      );
      await lifecycle.onAdopted();
      return undefined;
    },
    drain: { deferredLaneOccupancy: "release", onLog: (message) => params.runtime?.error(message) },
    abortSignal: params.abortSignal,
    onError: (error) => params.runtime?.error(`awada ingress: ${String(error)}`),
    classifyAdmissionError: () => undefined,
  });
  return {
    ...ingress,
    stop: async () => {
      await handler.stop();
      await ingress.stop();
    },
  };
}

export async function monitorAwadaProvider(opts: MonitorAwadaOpts = {}): Promise<void> {
  const { config: cfg, runtime, abortSignal, accountId } = opts;
  if (!cfg) throw new Error("Config is required for awada monitor");
  const account = resolveAwadaAccount({ cfg, accountId });
  if (!account.enabled || !account.configured || !account.relayBaseUrl || !account.awadaKey)
    throw new Error("Awada channel not enabled or configured");
  const ingress = createAwadaIngressMonitor({
    cfg,
    accountId: account.accountId,
    runtime,
    abortSignal,
  });
  ingress.start();
  try {
    await runGatewayClient({
      relayBaseUrl: account.relayBaseUrl,
      awadaKey: account.awadaKey,
      lane: account.lane,
      abortSignal,
      log: runtime?.log,
      error: runtime?.error,
      onEvent: async (_id, event) => {
        await ingress.receive(event);
      },
    });
  } finally {
    await ingress.stop();
  }
}
