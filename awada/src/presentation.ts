/** The agent-facing Awada contract; transport brands stay inside the adapter. */
export function awadaActionId(value: string): string {
  return value.replace(/^(?:qiweapi|worktool)\./i, "");
}

export function awadaTechnicalText(value: string): string {
  return value
    .replace(/https?:\/\/[^\s)<>"']*(?:qiweapi|worktool)[^\s)<>"']*/gi, "[Awada documentation]")
    .replace(/\b(?:qiweapi|worktool)\.([a-zA-Z0-9_.]+)/gi, "$1")
    .replace(/qiweapi|qiwei|qiwe|worktool/gi, "Awada");
}

/** Schema prose is technical documentation; property names and validation rules are unchanged. */
export function awadaSchema(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(awadaSchema);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [
      key,
      ["title", "description", "markdownDescription", "$comment"].includes(key) &&
      typeof item === "string"
        ? awadaTechnicalText(item)
        : ["enum", "const", "default", "examples", "example", "pattern", "required"].includes(key)
          ? item
          : awadaSchema(item),
    ]),
  );
}

/** Project technical envelopes while preserving customer text, IDs, files and business data. */
export function awadaPublicValue(value: unknown, technical = false): unknown {
  if (typeof value === "string") return technical ? awadaTechnicalText(value) : value;
  if (Array.isArray(value)) return value.map((item) => awadaPublicValue(item, technical));
  if (!value || typeof value !== "object") return value;
  const result: Record<string, unknown> = Object.create(null);
  for (const [key, item] of Object.entries(value)) {
    if (
      ["provider", "platformType"].includes(key) &&
      typeof item === "string" &&
      /^(qiweapi|worktool)$/i.test(item)
    )
      continue;
    if (key === "platform" && typeof item === "string" && /^(qiweapi|worktool)$/i.test(item)) {
      result[key] = "awada";
    } else if (key === "operation" && typeof item === "string") {
      result[key] = awadaActionId(item);
    } else if (key === "type" && item === "PROVIDER_EVENT") {
      result[key] = "SERVICE_EVENT";
    } else if (key === "type" && item === "provider") {
      result[key] = "structured";
    } else {
      const name =
        (
          {
            provider_raw: "details",
            provider_data: "details",
            provider_type: "contentType",
            provider_account_id: "accountRef",
            provider_event: "eventName",
          } as Record<string, string>
        )[key] ?? key;
      result[name] = ["data", "text", "receivedContent", "content", "body"].includes(key)
        ? item
        : awadaPublicValue(
            item,
            technical ||
              ["response", "error", "reason", "provider_type", "provider_event"].includes(key),
          );
    }
  }
  return result;
}

export type AwadaCatalogOperation = {
  id: string;
  transportOperation?: string;
  title?: string;
  notes?: string;
  async?: boolean;
  custom?: boolean;
  deprecated?: boolean;
  scope?: string;
  schema?: unknown;
  querySchema?: unknown;
  responseSchema?: unknown;
};

export function awadaOperationView(operation: AwadaCatalogOperation, includeSchemas = false) {
  return {
    id: awadaActionId(operation.id),
    title: awadaTechnicalText(operation.title ?? awadaActionId(operation.id)),
    ...(includeSchemas && operation.notes ? { notes: awadaTechnicalText(operation.notes) } : {}),
    async: operation.async === true,
    custom: operation.custom === true,
    deprecated: operation.deprecated === true,
    authorizationScope: operation.scope === "token" ? "service" : "account",
    ...(includeSchemas
      ? {
          schema: awadaSchema(operation.schema ?? {}),
          querySchema: awadaSchema(operation.querySchema ?? {}),
          responseSchema: awadaSchema(operation.responseSchema ?? {}),
        }
      : {}),
  };
}
