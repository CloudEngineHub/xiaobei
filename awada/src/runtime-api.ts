// Generic host contracts only; channel behavior belongs to this plugin.
export type {
  OpenClawConfig,
  OpenClawConfig as ClawdbotConfig,
  OpenClawPluginApi,
  PluginRuntime,
  ReplyPayload,
} from "openclaw/plugin-sdk/core";
export type RuntimeEnv = {
  log: (...args: unknown[]) => void;
  error: (...args: unknown[]) => void;
  exit: (code: number) => void;
};
