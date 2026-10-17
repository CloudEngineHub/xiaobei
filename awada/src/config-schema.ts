import { z } from "zod";
export { z };

const accountFields = {
  enabled: z.boolean().optional(),
  name: z.string().optional(),
  relayBaseUrl: z.string().optional(),
  awadaKey: z.string().optional(),
  lane: z.string().optional(),
  dmPolicy: z.enum(["open", "pairing", "allowlist", "disabled"]).optional(),
  allowFrom: z.array(z.string()).optional(),
  groupPolicy: z.enum(["open", "allowlist", "disabled"]).optional(),
  groupAllowFrom: z.array(z.string()).optional(),
  groupSenderAllowFrom: z.array(z.string()).optional(),
  requireMention: z.boolean().optional(),
  historyLimit: z.number().int().nonnegative().optional(),
  perMsgMaxLen: z.number().int().positive().optional(),
  mediaMaxMb: z.number().positive().max(20).optional(),
  mediaPublicBaseUrl: z.string().url().optional(),
};
export const AwadaAccountConfigSchema = z.object(accountFields).strict();
export const AwadaConfigSchema = z
  .object({
    ...accountFields,
    defaultAccount: z.string().optional(),
    accounts: z.record(z.string(), AwadaAccountConfigSchema).optional(),
  })
  .strict();
export const AwadaConfigJsonSchema = z.toJSONSchema(AwadaConfigSchema);
export const AwadaPluginConfigSchema = z
  .object({
    commandsFile: z.string().optional(),
    customerdb: z
      .object({
        enabled: z.boolean().optional(),
        accountId: z.string().optional(),
        agentId: z.string().optional(),
        workspaceDir: z.string().optional(),
      })
      .strict()
      .optional(),
  })
  .strict();
export const AwadaPluginConfigJsonSchema = z.toJSONSchema(AwadaPluginConfigSchema);
