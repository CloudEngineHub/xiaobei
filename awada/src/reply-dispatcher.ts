import { createChannelMessageReplyPipeline } from "openclaw/plugin-sdk/channel-outbound";
import type { ClawdbotConfig, RuntimeEnv } from "./runtime-api.js";
import type { OutboundTarget } from "./redis-types.js";
import { deliverAwadaReply } from "./outbound.js";
import { waitForAwadaOperation } from "./api.js";

export type CreateAwadaReplyDispatcherParams = {
  cfg: ClawdbotConfig;
  agentId: string;
  runtime: RuntimeEnv;
  relayBaseUrl: string;
  awadaKey: string;
  lane: string;
  target: OutboundTarget;
  inboundEventId: string;
  accountId?: string;
};

export function formatAwadaReplyRecipient(target: OutboundTarget): string {
  const user = target.user_id_external?.trim() ?? "";
  const channel = target.channel_id?.trim() ?? "";
  return channel ? `${user}[${channel}]` : user || "[unknown-channel]";
}

/** Let core own the same buffered dispatcher, prefix, hooks, and error semantics as Feishu. */
export function createAwadaReplyDispatcher(params: CreateAwadaReplyDispatcherParams) {
  const pipeline = createChannelMessageReplyPipeline({
    cfg: params.cfg,
    agentId: params.agentId,
    channel: "awada",
    accountId: params.accountId,
  });
  let deliveryIndex = 0;
  return {
    dispatcherOptions: {
      responsePrefix: pipeline.responsePrefix,
      responsePrefixContextProvider: pipeline.responsePrefixContextProvider,
    },
    replyOptions: { onModelSelected: pipeline.onModelSelected },
    delivery: {
      observeMessageSent: true as const,
      preparePayload: pipeline.transformReplyPayload,
      deliver: async (
        payload: Parameters<typeof deliverAwadaReply>[0]["payload"],
        info: { kind: string },
      ) => {
        const { getAgentScopedMediaLocalRoots } = await import("openclaw/plugin-sdk/media-runtime");
        // Stable IDs make a repeated accepted HTTP submission safe without replaying unknown writes.
        const messageIds = await deliverAwadaReply({
          ...params,
          payload,
          mediaLocalRoots: getAgentScopedMediaLocalRoots(params.cfg, params.agentId),
          requestId: `reply-${params.inboundEventId}-${info.kind}-${deliveryIndex++}`,
        });
        return {
          messageIds,
          visibleReplySent: false,
          finalization: Promise.all(messageIds.map((id) => waitForAwadaOperation(params, id))).then(
            (results) => {
              const failed = results.find(
                (result) => result.state === "failed" || result.state === "unknown",
              );
              if (failed)
                throw new Error(
                  `Awada execution ${failed.state}; inspect operation results before retrying`,
                );
              return {
                messageIds,
                visibleReplySent:
                  results.length > 0 && results.every((result) => result.state === "succeeded"),
              };
            },
          ),
        };
      },
    },
  };
}
