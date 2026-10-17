/** Gateway tool adapter. The browser package owns IPC, launch and Playwright. */
import { existsSync, realpathSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import type { AnyAgentTool, OpenClawPluginToolContext } from "openclaw/plugin-sdk/plugin-entry";
import { wrapExternalContent } from "openclaw/plugin-sdk/security-runtime";
import { Type } from "typebox";
import { resolveExistingUploadPaths } from "./browser/paths.js";
import { neutralizeMediaDirectives } from "./browser/vision.js";

type Data = Record<string, unknown>;
type Reply = { ok: boolean; data?: Data; error?: { code: string; message: string } };
type Client = {
  status(): Promise<Data>;
  sessions(): Promise<Data[]>;
  start(options: Data): Promise<Data>;
  request(action: string, params?: Data, options?: Data): Promise<Reply>;
  stop(options?: Data): Promise<Reply>;
};
type Runtime = {
  BrowserClient: new (options: Data) => Client;
  resolveLaunchOptions: (session: string, overrides: Data) => Data;
};

// Resolve from the shipped product layout, never from PATH, npm globals or cwd.
export async function loadXiaobeiBrowser(): Promise<Runtime> {
  const roots = [process.env.XIAOBEI_HOME];
  for (let dir = path.dirname(fileURLToPath(import.meta.url)); ; dir = path.dirname(dir)) {
    roots.push(dir);
    if (path.dirname(dir) === dir) break;
  }
  for (const root of roots) {
    if (!root) continue;
    const entry = path.join(root, "browser", "dist", "client", "index.js");
    if (existsSync(entry)) return (await import(pathToFileURL(entry).href)) as Runtime;
  }
  throw new Error("xiaobei-browser is missing; build/install the product browser package first");
}

const ACTIONS = [
  "status",
  "start",
  "stop",
  "profiles",
  "tabs",
  "open",
  "focus",
  "close",
  "navigate",
  "snapshot",
  "screenshot",
  "text",
  "pdf",
  "upload",
  "act",
  "lease",
] as const;
const KINDS = [
  "click",
  "type",
  "press",
  "hover",
  "select",
  "fill",
  "wait",
  "evaluate",
  "close",
] as const;
const optionalText = () => Type.Optional(Type.String());
const fields = {
  kind: optionalText(),
  ref: optionalText(),
  text: optionalText(),
  key: optionalText(),
  values: Type.Optional(Type.Array(Type.String())),
  fields: Type.Optional(Type.Array(Type.Object({ ref: Type.String(), value: Type.String() }))),
  timeMs: Type.Optional(Type.Integer({ minimum: 0, maximum: 30000 })),
  fn: optionalText(),
};

function schema(evaluateEnabled: boolean) {
  const kind = Type.Optional(
    Type.Union(
      KINDS.filter((k) => evaluateEnabled || k !== "evaluate").map((k) => Type.Literal(k)),
    ),
  );
  return Type.Object(
    {
      action: Type.Union(ACTIONS.map((a) => Type.Literal(a))),
      session: Type.Optional(
        Type.String({
          description:
            "Persistent browser session; default for ordinary sites. Use platform sessions only where the platform skill requires one.",
        }),
      ),
      targetId: optionalText(),
      targetUrl: optionalText(),
      selector: optionalText(),
      interactive: Type.Optional(Type.Boolean()),
      fullPage: Type.Optional(Type.Boolean()),
      path: optionalText(),
      paths: Type.Optional(Type.Array(Type.String())),
      inputRef: optionalText(),
      timeoutMs: Type.Optional(Type.Integer({ minimum: 1, maximum: 120000 })),
      leaseToken: optionalText(),
      operation: Type.Optional(
        Type.Union(["acquire", "renew", "wait", "release"].map((v) => Type.Literal(v))),
      ),
      ...fields,
      kind,
      request: Type.Optional(Type.Object({ ...fields, kind })),
    },
    { additionalProperties: false },
  );
}

function record(value: unknown): Data {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("Expected object parameters");
  return value as Data;
}
function required(data: Data, key: string): string {
  const value = data[key];
  if (typeof value !== "string" || !value.trim()) throw new Error(`${key} is required`);
  return value;
}
function unwrap(reply: Reply): Data {
  if (!reply.ok)
    throw new Error(
      `${reply.error?.code ?? "ACTION_FAILED"}: ${reply.error?.message ?? "Browser command failed"}`,
    );
  return reply.data ?? {};
}
function result(data: Data, image?: string) {
  const text = wrapExternalContent(neutralizeMediaDirectives(JSON.stringify(data)), {
    source: "browser",
  });
  return {
    content: [
      { type: "text" as const, text },
      ...(image ? [{ type: "image" as const, data: image, mimeType: "image/png" }] : []),
    ],
    details: data,
  };
}

function checkedPath(value: string, ctx: OpenClawPluginToolContext, writing: boolean): string {
  const resolved = path.resolve(ctx.workspaceDir ?? process.cwd(), value);
  const real = writing
    ? path.join(realpathSync(path.dirname(resolved)), path.basename(resolved))
    : realpathSync(resolved);
  if (writing && existsSync(resolved) && realpathSync(resolved) !== real)
    throw new Error("Refusing a symlink output path");
  if (ctx.fsPolicy?.workspaceOnly) {
    const root = realpathSync(ctx.fsPolicy.root ?? ctx.workspaceDir ?? ".");
    const relative = path.relative(root, real);
    if (relative === ".." || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative))
      throw new Error("Path is outside the permitted workspace");
  }
  return real;
}

export function createXiaobeiBrowserTool(
  ctx: OpenClawPluginToolContext,
  load = loadXiaobeiBrowser,
): AnyAgentTool {
  const getConfig = () => ctx.getRuntimeConfig?.() ?? ctx.runtimeConfig ?? ctx.config;
  const evaluateEnabled = getConfig()?.browser?.evaluateEnabled !== false;
  return {
    name: "browser",
    label: "Browser",
    resultContentSource: "network",
    description:
      "Control xiaobei-browser (Camoufox). Ordinary sites share persistent session=default; platform skills specify their own session. Snapshot refs and targetId are temporary: keep the tab from the snapshot. open/navigate operates on the current tab. type replaces a field; fill accepts ref/value fields. pdf saves a raster screenshot PDF. Unsupported Chrome/node/dashboard actions are unavailable. For a multi-step task acquire a lease, pass leaseToken to every call, renew while working, use wait for human login, and release afterwards. A timeout means outcome unknown: inspect state and never replay a submit automatically.",
    parameters: schema(evaluateEnabled),
    execute: async (_id, args, signal) => {
      signal?.throwIfAborted();
      const config = getConfig();
      if (config?.browser?.enabled === false) throw new Error("Browser is disabled");
      if (ctx.sandboxed || ctx.browser?.sandboxBridgeUrl || ctx.browser?.allowHostControl === false)
        throw new Error("Local browser access is blocked by sandbox/host policy");
      if (ctx.toolBindings?.browser)
        throw new Error("Run-bound native browser tabs are unsupported by xiaobei-browser");
      const p = record(args);
      for (const key of [
        "target",
        "node",
        "profile",
        "dashboard",
        "frame",
        "snapshotFormat",
        "refs",
        "mode",
        "compact",
        "depth",
        "maxChars",
        "doubleClick",
        "button",
        "modifiers",
        "submit",
        "slowly",
        "loadState",
        "textGone",
      ]) {
        if (p[key] !== undefined || (p.request && record(p.request)[key] !== undefined))
          throw new Error(`Unsupported xiaobei-browser parameter: ${key}`);
      }
      const action = required(p, "action");
      if (!(ACTIONS as readonly string[]).includes(action))
        throw new Error(`Unsupported browser action: ${action}`);
      // A bare allow-all policy matches this runtime. Restrictions require interception.
      const policy = config?.browser?.ssrfPolicy;
      const unrestricted =
        policy?.dangerouslyAllowPrivateNetwork === true &&
        Object.keys(policy).every((key) => key === "dangerouslyAllowPrivateNetwork");
      if (policy && Object.keys(policy).length && !unrestricted)
        throw new Error(
          "Configured browser SSRF policy requires network interception; xiaobei-browser does not support it yet",
        );
      const { BrowserClient, resolveLaunchOptions } = await load();
      const session = p.session === undefined ? "default" : required(p, "session");
      const client = new BrowserClient({ session });
      const timeout = p.timeoutMs ?? 60000;
      if (!Number.isSafeInteger(timeout) || Number(timeout) < 1 || Number(timeout) > 120000)
        throw new Error("timeoutMs must be 1..120000");
      const options: Data = {
        deadlineMs: timeout,
        ...(p.leaseToken ? { leaseToken: required(p, "leaseToken") } : {}),
      };
      const send = async (name: string, params: Data = {}) => {
        signal?.throwIfAborted();
        const data = unwrap(await client.request(name, params, options));
        // Side effects may already have happened if cancellation arrives in flight.
        if (signal?.aborted)
          throw new Error(
            "OUTCOME_UNKNOWN: browser action may have completed after cancellation; inspect state before continuing",
          );
        return data;
      };
      if (action === "status") return result(await client.status());
      if (action === "profiles")
        return result({ sessions: await client.sessions(), defaultSession: "default" });
      const start = async () =>
        client.start(
          resolveLaunchOptions(
            session,
            config?.browser?.headless === undefined ? {} : { headless: config.browser.headless },
          ),
        );
      if (action === "start") return result(await start());
      if (action === "stop") return result(unwrap(await client.stop(options)));
      if (action === "lease") {
        const operation = required(p, "operation");
        if (!["acquire", "renew", "wait", "release"].includes(operation))
          throw new Error("Invalid lease operation");
        return result(await send(`lease.${operation}`));
      }
      if (action === "open" || action === "navigate") {
        const url = new URL(required(p, "targetUrl"));
        if (!["https:", "http:"].includes(url.protocol) || url.username || url.password)
          throw new Error("Navigation requires HTTP(S) without embedded credentials");
        if (!(await client.status()).running) await start();
      }
      // Keep tab selection and the following operation in one ownership window.
      const ownLease = !options.leaseToken;
      if (ownLease)
        options.leaseToken = (await send("lease.acquire", { ttlMs: 180000 })).leaseToken;
      try {
        if (action === "tabs") {
          const data = await send("tabs");
          return result({
            ...data,
            tabs: (data.tabs as Data[]).map((tab) => ({ ...tab, targetId: tab.tabId })),
          });
        }
        // RefRegistry invalidates on a real tab switch, so do not switch the active tab.
        if (p.targetId) {
          const tabs = (await send("tabs")).tabs as Data[];
          const selected = tabs.find((tab) => tab.tabId === p.targetId);
          if (!selected) throw new Error("STALE_TAB: targetId does not identify a current tab");
          if (!selected.active && action !== "close") await send("switch", { tabId: p.targetId });
        }
        if (action === "focus") {
          if (!p.targetId) throw new Error("targetId is required");
          return result({ targetId: p.targetId });
        }
        if (action === "close")
          return result(await send("close-tab", p.targetId ? { tabId: p.targetId } : {}));
        if (action === "open" || action === "navigate") {
          const data = await send("open", { url: p.targetUrl });
          return result({ ...data, targetId: data.tabId });
        }
        if (action === "snapshot") {
          const data = await send("snapshot", {
            interactive: p.interactive === true,
            ...(p.selector ? { selector: p.selector } : {}),
          });
          return result({ ...data, targetId: data.tabId });
        }
        if (action === "text") return result(await send("text", { target: p.selector ?? "body" }));
        if (action === "screenshot") {
          const data = await send("screenshot", {
            full_page: p.fullPage === true,
            ...(p.path ? { path: checkedPath(required(p, "path"), ctx, true) } : {}),
          });
          const { base64, ...metadata } = data;
          return result(metadata, typeof base64 === "string" ? base64 : undefined);
        }
        if (action === "pdf")
          return result(await send("pdf", { path: checkedPath(required(p, "path"), ctx, true) }));
        if (action === "upload") {
          if (!Array.isArray(p.paths) || p.paths.some((v) => typeof v !== "string"))
            throw new Error("paths must be a string array");
          const resolved = await resolveExistingUploadPaths({
            requestedPaths: p.paths as string[],
          });
          if (!resolved.ok) throw new Error(resolved.error);
          return result(
            await send("upload", {
              paths: resolved.paths.map((v) => checkedPath(v, ctx, false)),
              ...(p.inputRef ? { ref: p.inputRef } : { selector: required(p, "selector") }),
            }),
          );
        }
        const request = p.request ? record(p.request) : p;
        const kind = required(request, "kind");
        if (!(KINDS as readonly string[]).includes(kind))
          throw new Error(`Unsupported act kind: ${kind}`);
        if (kind === "evaluate") {
          if (config?.browser?.evaluateEnabled === false || ctx.fsPolicy?.workspaceOnly)
            throw new Error("Browser evaluate is blocked by policy");
          return result(await send("eval", { expression: `(${required(request, "fn")})()` }));
        }
        if (kind === "close") return result(await send("close-tab"));
        if (kind === "fill") {
          if (!Array.isArray(request.fields) || request.fields.length > 100)
            throw new Error("fill requires at most 100 fields");
          // Validate the entire batch before the first write.
          const entries = request.fields.map((v) => {
            const field = record(v);
            return {
              ref: required(field, "ref"),
              text: typeof field.value === "string" ? field.value : required(field, "value"),
            };
          });
          for (const entry of entries) await send("fill", entry);
          return result({ filled: entries.length });
        }
        if (kind === "wait") {
          if (
            !Number.isSafeInteger(request.timeMs) ||
            Number(request.timeMs) < 0 ||
            Number(request.timeMs) > 30000
          )
            throw new Error("wait requires timeMs=0..30000");
          return result(await send("wait", { ms: request.timeMs }));
        }
        if (kind === "press") return result(await send("press", { key: required(request, "key") }));
        const ref = required(request, "ref");
        if (kind === "type") return result(await send("fill", { ref, text: request.text ?? "" }));
        if (kind === "select") {
          if (
            !Array.isArray(request.values) ||
            request.values.length !== 1 ||
            typeof request.values[0] !== "string"
          )
            throw new Error("select supports exactly one option label");
          return result(await send("select", { ref, value: request.values[0] }));
        }
        return result(await send(kind, { ref }));
      } finally {
        if (ownLease) {
          // A timed-out command remains busy; release must not hide its result.
          await client.request("lease.release", {}, options).catch(() => undefined);
        }
      }
    },
  };
}
