import type { OpenClawPluginApi, OpenClawPluginDefinition } from "openclaw/plugin-sdk/plugin-entry";
import { BrowserBroker } from "../dist/broker/server.js";
import { setInstallationRoot } from "../dist/platform/paths.js";
import { createXiaobeiBrowserTool } from "./tool.js";
import { dirname } from "node:path";

export default {
  id: "xiaobei-browser",
  name: "Xiaobei Browser",
  description: "Managed Camoufox browser tool and persistent runtime service",
  register(api: OpenClawPluginApi) {
    setInstallationRoot(api.rootDir ?? dirname(dirname(api.source)));
    const broker = new BrowserBroker(undefined, error =>
      api.logger.error(`Browser broker failed: ${error instanceof Error ? error.name : "Error"}`));
    api.registerService({
      id: "xiaobei-browser-runtime",
      start: () => broker.start(),
      stop: () => broker.close(),
    });
    api.registerTool(ctx => createXiaobeiBrowserTool(ctx), { name: "xiaobei_browser" });
  },
} satisfies OpenClawPluginDefinition;
