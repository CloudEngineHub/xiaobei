import type { AwadaCatalogOperation } from "./presentation.js";

export const awadaDriveSendAction: AwadaCatalogOperation = {
  id: "drive.send",
  title: "发送网盘文件",
  notes:
    "发送已存入网盘的文件或图片。文件名必须完全一致；不是本地路径或下载 URL。返回入队回执后查询执行结果。",
  async: true,
  schema: {
    type: "object",
    properties: {
      targets: {
        type: "array",
        minItems: 1,
        items: { type: "string", minLength: 1 },
        description: "接收人的原始名称或群名",
      },
      fileName: { type: "string", minLength: 1, description: "网盘中已存在的完整文件名" },
      kind: { type: "string", enum: ["image", "file"], default: "file" },
      caption: { type: "string", description: "可选附加留言" },
    },
    required: ["targets", "fileName"],
    additionalProperties: false,
  },
  querySchema: { type: "object", properties: {}, additionalProperties: false },
  responseSchema: { type: "object" },
};

/** Internal transport adaptation; never select a protocol based on the account. */
export function awadaDriveSendRequest(params: unknown) {
  if (!params || typeof params !== "object" || Array.isArray(params))
    throw new Error("drive.send requires params.targets and params.fileName");
  const p = params as Record<string, unknown>;
  if (
    Object.keys(p).some((key) => !["targets", "fileName", "kind", "caption"].includes(key)) ||
    !Array.isArray(p.targets) ||
    !p.targets.length ||
    p.targets.some((target) => typeof target !== "string" || !target.trim()) ||
    typeof p.fileName !== "string" ||
    !p.fileName.trim() ||
    /^(?:[\\/]|[a-z]:[\\/]|[a-z][a-z\d+.-]*:\/\/)/i.test(p.fileName) ||
    (p.kind !== undefined && p.kind !== "image" && p.kind !== "file") ||
    (p.caption !== undefined && typeof p.caption !== "string")
  )
    throw new Error(
      "Invalid drive.send params; use targets, fileName, kind (image|file), and optional caption",
    );
  return {
    operation: p.kind === "image" ? "worktool.drive.sendImage" : "worktool.drive.sendFile",
    params: {
      socketType: 2,
      list: [
        {
          type: p.kind === "image" ? 208 : 209,
          titleList: p.targets,
          objectName: p.fileName,
          ...(p.caption === undefined ? {} : { extraText: p.caption }),
        },
      ],
    },
  };
}
