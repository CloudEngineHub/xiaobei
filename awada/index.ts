import type { OpenClawPluginApi, OpenClawPluginDefinition } from "openclaw/plugin-sdk/core";
import { awadaPlugin } from "./src/channel.js";
import { setAwadaRuntime } from "./src/runtime.js";
import { registerCustomerDb } from "./src/customerdb.js";
import { registerAwadaTools } from "./src/tools.js";
import { registerAwadaCommands } from "./src/commands.js";
import { registerAwadaMediaRoute } from "./src/hosted-media.js";
import { AwadaPluginConfigSchema, AwadaPluginConfigJsonSchema } from "./src/config-schema.js";

export { monitorAwadaProvider } from "./src/monitor.js";
export { probeAwada } from "./src/probe.js";
export { sendTextToAwada, encodeAwadaTo, decodeAwadaTo } from "./src/send.js";
export { publishTextToAwada } from "./src/publisher.js";
export { awadaPlugin } from "./src/channel.js";
export { transcribeAwadaVoice } from "./src/transcription.js";
export {
  getAwadaCapabilities,
  submitAwadaOperation,
  getAwadaOperation,
  waitForAwadaOperation,
  readAwadaInbound,
} from "./src/api.js";

const plugin = {
  id: "awada",
  name: "Awada",
  description: "Awada Relay V2 channel and business action API",
  configSchema: {
    jsonSchema: AwadaPluginConfigJsonSchema,
    validate(value: unknown) {
      const result = AwadaPluginConfigSchema.safeParse(value ?? {});
      return result.success
        ? { ok: true as const, value: result.data }
        : {
            ok: false as const,
            errors: result.error.issues.map((issue) => `${issue.path.join(".")}: ${issue.message}`),
          };
    },
  },
  register(api: OpenClawPluginApi) {
    setAwadaRuntime(api.runtime);
    api.registerChannel({ plugin: awadaPlugin });
    const config = AwadaPluginConfigSchema.parse(api.pluginConfig ?? {});
    registerAwadaTools(api);
    registerAwadaCommands(api, config.commandsFile);
    registerAwadaMediaRoute(api);
    if (config.customerdb?.enabled !== false && config.customerdb?.agentId)
      registerCustomerDb(api, config.customerdb);
  },
} satisfies OpenClawPluginDefinition;
export default plugin;
