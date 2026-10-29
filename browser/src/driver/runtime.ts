import { assetStatus, requireAssets } from "./sdk.js";
import { BrowserManager } from "./browser.js";
import { execute } from "../actions/commands.js";
import { RuntimeError, type Params } from "../protocol/index.js";
import type { LaunchOptions } from "../state/registry.js";
import type { Driver } from "../runtime/server.js";

export { assetStatus };
export class CamoufoxDriver implements Driver {
  readonly capabilities = ["open", "back", "forward", "reload", "url", "title", "snapshot", "click", "fill", "type", "select", "check", "hover", "press", "text", "eval", "screenshot", "pdf", "scroll", "wait", "tabs", "switch", "close-tab", "cookies", "identity", "upload"];
  private manager: BrowserManager;
  constructor(private options: LaunchOptions) {
    this.manager = new BrowserManager(options.persistent, options.proxy, options.geoip, options.locale, options.viewport);
  }
  async launch(): Promise<void> {
    requireAssets(Boolean(this.options.proxy && this.options.geoip));
    await this.manager.launch(this.options.headless);
    // Listening on IPC is not enough to report browser readiness.
    if (await this.manager.getPage().evaluate(() => 1 + 1) !== 2) throw new RuntimeError("START_FAILED", "Browser readiness check failed");
  }
  async execute(action: string, params: Params): Promise<Params> {
    if (action === "open") params = { ...params, headless: this.options.headless };
    const response = await execute(this.manager, { id: "runtime", action, params });
    if (!response.success) throw new RuntimeError(response.code ?? "ACTION_FAILED", response.error || "Browser action failed");
    return response.data ?? {};
  }
  close(): Promise<void> { return this.manager.close(); }
}
