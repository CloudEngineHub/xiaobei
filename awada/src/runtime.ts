import type { PluginRuntime } from "openclaw/plugin-sdk/core";
import { createPluginRuntimeStore } from "openclaw/plugin-sdk/runtime-store";

export const {
  setRuntime: setAwadaRuntime,
  getRuntime: getAwadaRuntime,
  tryGetRuntime: tryGetAwadaRuntime,
} = createPluginRuntimeStore<PluginRuntime>({
  pluginId: "awada",
  errorMessage: "Awada runtime not initialized",
});
