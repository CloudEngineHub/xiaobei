import type { AwadaCatalogOperation } from "./presentation.js";

// Keep this module dependency-free so the Node catalog-sync script can import it.
const awadaActionId = (action: string) => action.replace(/^(?:qiweapi|worktool)\./i, "");

// Product scope, shared by catalog sync, discovery, schema lookup and submission.
// These are server administration actions, not account-dependent capability checks.
const removedActions = new Set([
  "client.createClient",
  "login.getLoginQrcode",
  "login.checkLoginQrCode",
  "login.verifyLoginQrcode",
  "login.manualLogin",
  "client.restoreClient",
  "client.stopClient",
  "user.logout",
  "message.forward",
  "queue.clear",
  "queue.remove",
  "command.batch",
  "command.prioritize",
  "account.clearStorage",
  "robot.loginLogs",
  "history.commands",
  "history.results",
  "history.callbacks",
  "callback.messageConfig",
  "callback.bind",
  "callback.bindLegacy",
  "callback.list",
  "callback.delete",
  "callback.deleteLegacy",
  "robot.encryption",
]);
const internalActions = new Set([
  "msg.voiceToTextApply",
  "msg.voiceToTextQuery",
  "drive.sendImage",
  "drive.sendFile",
]);

export function isAwadaRemovedAction(action: string): boolean {
  return removedActions.has(awadaActionId(action));
}

export function isAwadaPublicAction(action: string): boolean {
  const id = awadaActionId(action);
  return !removedActions.has(id) && !internalActions.has(id);
}

export function assertAwadaPublicAction(action: string): void {
  if (!isAwadaPublicAction(action))
    throw new Error("This action is outside the Awada client interface");
}

export const awadaTranscriptionAction: AwadaCatalogOperation = {
  id: "voice.transcribe",
  title: "语音转文字",
  notes:
    "收到语音后自动执行；手动调用时传入原始消息 ID。返回完成的文本，不需要分别申请和查询任务。",
  schema: {
    type: "object",
    properties: {
      messageId: { type: "string", minLength: 1, description: "原始语音消息 ID" },
      timeoutMs: { type: "integer", minimum: 1000, maximum: 60000, default: 30000 },
    },
    required: ["messageId"],
    additionalProperties: false,
  },
  querySchema: { type: "object", properties: {}, additionalProperties: false },
  responseSchema: {
    type: "object",
    properties: { messageId: { type: "string" }, text: { type: "string" } },
    required: ["messageId", "text"],
  },
};
