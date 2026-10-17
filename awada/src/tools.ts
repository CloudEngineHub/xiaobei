import { createHash } from "node:crypto";
import { Type, type Static } from "typebox";
import { jsonResult } from "openclaw/plugin-sdk/agent-runtime";
import type { OpenClawPluginApi } from "./runtime-api.js";
import { resolveAwadaAccount } from "./accounts.js";
import {
  awadaRequest,
  getAwadaCapabilities,
  getAwadaOperation,
  submitAwadaOperation,
  waitForAwadaOperation,
  type ProviderOperation,
} from "./api.js";
import { listAwadaSystemEvents } from "./events.js";
import { withAwadaSubmissionLedger } from "./ledger.js";
import { awadaPublicValue } from "./presentation.js";
import { assertAwadaPublicAction, awadaTranscriptionAction } from "./action-policy.js";
import { transcribeAwadaVoice } from "./transcription.js";

const Schema = Type.Object({
  action: Type.Union(
    ["health", "capabilities", "schema", "operation", "result", "events"].map((value) =>
      Type.Literal(value),
    ),
  ),
  accountId: Type.Optional(Type.String()),
  operation: Type.Optional(
    Type.String({
      description: "Awada action ID from capabilities, e.g. room.getRoomList or todo.create.",
    }),
  ),
  params: Type.Optional(
    Type.Union([Type.Record(Type.String(), Type.Unknown()), Type.Array(Type.Unknown())]),
  ),
  query: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
  file: Type.Optional(
    Type.Object({
      filename: Type.String(),
      base64: Type.String(),
      contentType: Type.Optional(Type.String()),
    }),
  ),
  requestId: Type.Optional(Type.String({ minLength: 1, maxLength: 200 })),
  operationId: Type.Optional(Type.String()),
  waitMs: Type.Optional(Type.Integer({ minimum: 0, maximum: 60_000 })),
  eventType: Type.Optional(
    Type.String({ description: "MESSAGE_NEW, SERVICE_EVENT or OPERATION_RESULT." }),
  ),
  limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 100 })),
});

/** One schema-driven surface for the client business scope. */
export function registerAwadaTools(api: OpenClawPluginApi): void {
  api.registerTool(
    {
      contextVersion: 2,
      create: (ctx) => ({
        name: "awada_api",
        label: "Awada Relay V2",
        description:
          "Discover and call Awada business actions. Use capabilities, then schema for exact params/query/response. Use the same action IDs for every account; the server decides execution support and permissions. operation enqueues a call; result checks execution. voice.transcribe completes transcription and returns text directly; inbound voice is transcribed automatically. queued/submitted are not successful delivery; unknown must be reconciled without blind resend. events reads service/result callbacks without starting chat turns. Large IDs must be strings.",
        parameters: Schema,
        execute: async (toolCallId, rawInput, signal) => {
          const input = rawInput as Static<typeof Schema>;
          const cfg = ctx.getRuntimeConfig?.() ?? ctx.runtimeConfig ?? ctx.config ?? api.config;
          const account = resolveAwadaAccount({
            cfg,
            accountId: input.accountId ?? ctx.agentAccountId,
          });
          if (!account.enabled || !account.configured || !account.awadaKey || !account.relayBaseUrl)
            throw new Error("Awada account is not configured");
          const credentials = {
            relayBaseUrl: account.relayBaseUrl,
            awadaKey: account.awadaKey,
            lane: account.lane,
          };
          ctx.assertInvocationCurrent();
          let result: unknown;
          switch (input.action) {
            case "health":
              result = await awadaRequest(credentials, "/health", { public: true, signal });
              break;
            case "capabilities":
              result = await getAwadaCapabilities(credentials, undefined, signal);
              break;
            case "schema":
              if (!input.operation) throw new Error("operation is required");
              result = await getAwadaCapabilities(credentials, input.operation, signal);
              break;
            case "operation": {
              if (ctx.requesterSenderId && ctx.senderIsOwner !== true)
                throw new Error("Native Awada account operations require the channel owner");
              if (!input.operation) throw new Error("operation is required");
              assertAwadaPublicAction(input.operation);
              const body: ProviderOperation = {
                operation: input.operation,
                params: input.params,
                query: input.query,
                file: input.file,
                request_id:
                  input.requestId ??
                  `tool-${createHash("sha256")
                    .update(JSON.stringify([ctx.sessionId, toolCallId]))
                    .digest("hex")}`,
              };
              if (input.operation === awadaTranscriptionAction.id) {
                const params = input.params as Record<string, unknown> | undefined;
                if (!params || Array.isArray(params) || typeof params.messageId !== "string")
                  throw new Error("voice.transcribe requires params.messageId");
                result = await transcribeAwadaVoice(credentials, params.messageId, {
                  requestId: body.request_id,
                  timeoutMs: params.timeoutMs as number | undefined,
                  signal,
                });
                ctx.assertInvocationCurrent();
                break;
              }
              ctx.assertInvocationCurrent();
              const receipt = await withAwadaSubmissionLedger(
                credentials,
                body.request_id!,
                body,
                () => {
                  ctx.assertInvocationCurrent();
                  return submitAwadaOperation(credentials, body, signal);
                },
              );
              result = input.waitMs
                ? {
                    ...receipt,
                    result: await waitForAwadaOperation(credentials, receipt.eventId, {
                      timeoutMs: input.waitMs,
                      signal,
                    }),
                  }
                : receipt;
              break;
            }
            case "result":
              if (ctx.requesterSenderId && ctx.senderIsOwner !== true)
                throw new Error("Account-wide Awada results require the channel owner");
              if (!input.operationId) throw new Error("operationId is required");
              result = input.waitMs
                ? await waitForAwadaOperation(credentials, input.operationId, {
                    timeoutMs: input.waitMs,
                    signal,
                  })
                : await getAwadaOperation(credentials, input.operationId, signal);
              break;
            case "events": {
              const events = await listAwadaSystemEvents(account.accountId, account.lane, {
                type: input.eventType === "SERVICE_EVENT" ? "PROVIDER_EVENT" : input.eventType,
                operationId: input.operationId,
                limit: input.limit,
              });
              result =
                ctx.requesterSenderId && ctx.senderIsOwner !== true
                  ? events.filter(
                      (event) =>
                        event.type === "MESSAGE_NEW" &&
                        event.meta.user_id_external === ctx.requesterSenderId &&
                        (!ctx.nativeChannelId ||
                          event.meta.channel_id === ctx.nativeChannelId ||
                          (event.meta.channel_id === "0" &&
                            ctx.nativeChannelId === event.meta.user_id_external)),
                    )
                  : events;
              break;
            }
            default:
              throw new Error("Unknown Awada API action");
          }
          return jsonResult(awadaPublicValue(result));
        },
      }),
    },
    { name: "awada_api" },
  );
}
