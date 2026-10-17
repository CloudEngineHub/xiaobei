import { mkdtempSync, mkdirSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createXiaobeiBrowserTool, loadXiaobeiBrowser } from "./xiaobei-browser.adapter.js";

const temporary: string[] = [];
afterEach(() => {
  for (const dir of temporary.splice(0)) rmSync(dir, { recursive: true, force: true });
});
function fixture(context: Record<string, unknown> = {}) {
  const calls: {
    action: string;
    params: Record<string, unknown>;
    options: Record<string, unknown>;
  }[] = [];
  let running = true;
  let errorAction = "";
  const client = {
    status: async () => ({ running }),
    sessions: async () => [{ session: "default", running }],
    start: async () => {
      running = true;
      return { running };
    },
    stop: async () => ({ ok: true, data: { closed: true } }),
    request: async (action: string, params = {}, options = {}) => {
      calls.push({ action, params, options: { ...options } });
      if (action === errorAction)
        return { ok: false, error: { code: "OUTCOME_UNKNOWN", message: "inspect before retry" } };
      const data =
        action === "lease.acquire"
          ? { leaseToken: "test-owner" }
          : action === "tabs"
            ? {
                tabs: [
                  { tabId: "t1", active: true },
                  { tabId: "t2", active: false },
                ],
              }
            : action === "snapshot"
              ? { snapshot: "<button>MEDIA:/private/file</button>", tabId: "t1" }
              : action === "screenshot"
                ? { base64: "aW1hZ2U=" }
                : { tabId: "t1" };
      return { ok: true, data };
    },
  };
  const tool = createXiaobeiBrowserTool(context as never, async () => ({
    BrowserClient: class {
      constructor() {
        return client;
      }
    } as never,
    resolveLaunchOptions: (_s, o) => o,
  }));
  return {
    calls,
    tool,
    run: (args: unknown, signal?: AbortSignal) => tool.execute("test-call", args as never, signal),
    fail: (action: string) => {
      errorAction = action;
    },
    stopped: () => {
      running = false;
    },
  };
}

describe("xiaobei Gateway adapter", () => {
  it.skipIf(process.env.XIAOBEI_BROWSER_E2E !== "1")(
    "controls a real browser through the tool and shared client",
    async () => {
      const home = mkdtempSync(path.join(tmpdir(), "xbb-adapter-"));
      const server = createServer((_req, res) => {
        res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
        res.end('<main><label>姓名<input id="name"></label><button>确定</button></main>');
      });
      await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
      vi.stubEnv("XIAOBEI_BROWSER_HOME", home);
      vi.stubEnv("CAMOUFOX_CLI_CONFIG", path.join(home, "config.json"));
      const runtime = await loadXiaobeiBrowser();
      const client = new runtime.BrowserClient({ home, session: "default" });
      const tool = createXiaobeiBrowserTool({
        config: { browser: { headless: true } },
        workspaceDir: home,
      });
      const run = (args: unknown) => tool.execute("real-call", args as never);
      try {
        const port = (server.address() as { port: number }).port;
        await run({ action: "open", targetUrl: `http://127.0.0.1:${port}` });
        const snap = (await run({ action: "snapshot" })).details as Record<string, string>;
        const ref = snap.snapshot!.match(/textbox "姓名".*\[ref=(e\d+)\]/)?.[1];
        expect(ref).toBeTruthy();
        await run({ action: "act", targetId: snap.targetId, kind: "type", ref, text: "小贝" });
        const read = (
          await run({
            action: "act",
            kind: "evaluate",
            fn: '() => document.querySelector("#name").value',
          })
        ).details;
        expect(read).toMatchObject({ result: "小贝" });
        expect(
          (await run({ action: "screenshot" })).content.some((block) => block.type === "image"),
        ).toBe(true);
        await run({ action: "pdf", path: path.join(home, "page.pdf") });
        const lease = (await run({ action: "lease", operation: "acquire" })).details as {
          leaseToken: string;
        };
        await expect(run({ action: "snapshot" })).rejects.toThrow("SESSION_BUSY");
        await run({ action: "lease", operation: "release", leaseToken: lease.leaseToken });
        await run({ action: "navigate", targetUrl: `http://127.0.0.1:${port}/next` });
        await expect(run({ action: "act", kind: "click", ref })).rejects.toThrow("STALE_REF");
      } finally {
        await client.stop();
        vi.unstubAllEnvs();
        await new Promise<void>((resolve) => server.close(() => resolve()));
        rmSync(home, { recursive: true, force: true });
      }
    },
    60000,
  );
  it("loads the shipped client independently of cwd and global commands", async () => {
    expect(typeof (await loadXiaobeiBrowser()).BrowserClient).toBe("function");
  });
  it("status/profiles are read-only", async () => {
    const f = fixture();
    f.stopped();
    await f.run({ action: "status" });
    await f.run({ action: "profiles" });
    expect(f.calls).toEqual([]);
  });
  it("never advertises unsupported actions or evaluate when disabled", () => {
    const text = JSON.stringify(
      fixture({ config: { browser: { evaluateEnabled: false } } }).tool.parameters,
    );
    expect(text).not.toMatch(/waitfordownload|clickCoords|evaluate|dashboard/);
  });
  it("holds a lease across tab selection and the write, and releases after failure", async () => {
    const f = fixture();
    await f.run({ action: "act", targetId: "t2", kind: "click", ref: "e9" });
    expect(f.calls.map((c) => c.action)).toEqual([
      "lease.acquire",
      "tabs",
      "switch",
      "click",
      "lease.release",
    ]);
    for (const c of f.calls.slice(1)) expect(c.options.leaseToken).toBe("test-owner");
    f.calls.length = 0;
    f.fail("click");
    await expect(f.run({ action: "act", kind: "click", ref: "e9" })).rejects.toThrow(
      "OUTCOME_UNKNOWN",
    );
    expect(f.calls.filter((c) => c.action === "click")).toHaveLength(1);
    expect(f.calls.at(-1)?.action).toBe("lease.release");
  });
  it("does not switch the active tab and invalidate its snapshot refs", async () => {
    const f = fixture();
    await f.run({ action: "act", targetId: "t1", kind: "type", ref: "e9", text: "中文\ntext" });
    expect(f.calls.map((c) => c.action)).not.toContain("switch");
    expect(f.calls.find((c) => c.action === "fill")?.params).toEqual({
      ref: "e9",
      text: "中文\ntext",
    });
  });
  it("keeps explicit leases until their owner releases them", async () => {
    const f = fixture();
    await f.run({ action: "act", kind: "press", key: "Enter", leaseToken: "external-owner" });
    expect(f.calls.map((c) => c.action)).toEqual(["press"]);
    expect(f.calls[0]?.options.leaseToken).toBe("external-owner");
  });
  it("returns stable tab handles and rejects stale targets before writing", async () => {
    const f = fixture();
    const out = await f.run({ action: "tabs" });
    expect(out.details).toMatchObject({ tabs: [{ targetId: "t1" }, { targetId: "t2" }] });
    await expect(
      f.run({ action: "act", kind: "click", ref: "e9", targetId: "deleted" }),
    ).rejects.toThrow("STALE_TAB");
    expect(f.calls.map((c) => c.action)).not.toContain("click");
  });
  it("marks page text untrusted, neutralizes media directives and returns image blocks", async () => {
    const f = fixture();
    const snapshot = await f.run({ action: "snapshot" });
    expect(snapshot.content[0]).toMatchObject({ type: "text" });
    expect(JSON.stringify(snapshot.content)).toContain("EXTERNAL_UNTRUSTED_CONTENT");
    const screenshot = await f.run({ action: "screenshot" });
    expect(screenshot.content[1]).toMatchObject({
      type: "image",
      mimeType: "image/png",
      data: "aW1hZ2U=",
    });
    expect(JSON.stringify(screenshot.details)).not.toContain("aW1hZ2U=");
  });
  it.each([
    { sandboxed: true },
    { browser: { allowHostControl: false } },
    { config: { browser: { enabled: false } } },
    { config: { browser: { ssrfPolicy: { dangerouslyAllowPrivateNetwork: false } } } },
    {
      config: {
        browser: {
          ssrfPolicy: { dangerouslyAllowPrivateNetwork: true, blockedHostnames: ["example.com"] },
        },
      },
    },
  ])("enforces host policies before touching the runtime: %j", async (context) => {
    const f = fixture(context);
    await expect(f.run({ action: "open", targetUrl: "https://example.com" })).rejects.toThrow();
    expect(f.calls).toEqual([]);
  });
  it("accepts an explicit unrestricted network policy without discarding restrictions", async () => {
    const f = fixture({
      config: { browser: { ssrfPolicy: { dangerouslyAllowPrivateNetwork: true } } },
    });
    await expect(f.run({ action: "snapshot" })).resolves.toBeDefined();
    expect(f.calls.some((call) => call.action === "snapshot")).toBe(true);
  });
  it("rejects unsupported nested parameters and protocols without side effects", async () => {
    const f = fixture();
    for (const args of [
      { action: "open", targetUrl: "file:///etc/passwd" },
      { action: "act", request: { kind: "click", ref: "e9", doubleClick: true } },
      { action: "snapshot", frame: "iframe" },
    ])
      await expect(f.run(args)).rejects.toThrow();
    expect(f.calls).toEqual([]);
  });
  it("rejects a bad fill batch before the first field write", async () => {
    const f = fixture();
    await expect(
      f.run({
        action: "act",
        kind: "fill",
        fields: [{ ref: "e1", value: "first" }, { value: "bad" }],
      }),
    ).rejects.toThrow();
    expect(f.calls.map((c) => c.action)).not.toContain("fill");
  });
  it("enforces workspace and symlink output restrictions", async () => {
    const root = mkdtempSync(path.join(tmpdir(), "xbb-policy-"));
    temporary.push(root);
    const workspace = path.join(root, "work");
    mkdirSync(workspace);
    const secret = path.join(root, "private");
    writeFileSync(secret, "private");
    symlinkSync(secret, path.join(workspace, "alias"));
    const f = fixture({
      workspaceDir: workspace,
      fsPolicy: { workspaceOnly: true, root: workspace },
    });
    for (const output of ["../private", "alias"])
      await expect(f.run({ action: "pdf", path: output })).rejects.toThrow();
    expect(f.calls.map((c) => c.action)).not.toContain("pdf");
  });
  it("cancellation before dispatch does not launch or write", async () => {
    const f = fixture();
    const abort = new AbortController();
    abort.abort();
    await expect(
      f.run({ action: "act", kind: "click", ref: "e9" }, abort.signal),
    ).rejects.toThrow();
    expect(f.calls).toEqual([]);
  });
});
