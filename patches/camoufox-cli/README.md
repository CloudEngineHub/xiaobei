> 5.8 legacy：此目录仅保留历史参考；正式浏览器在仓根 `browser/`。新版安装入口为 `scripts/install-browser.mjs`，不要用本目录 build.sh 覆盖新版命令。

# camoufox-cli — wiseflow fork

Vendored fork of [`Bin-Huang/camoufox-cli`](https://github.com/Bin-Huang/camoufox-cli), initially based on **0.6.2**; the current package is **0.7.3-wiseflow.2**. Not published to npm; built and globally installed from this tree by `build.sh`.

This fork is the **线 1** browser backend of the current stack. The approved 5.8 plan develops it into a WiseFlow-owned browser runtime; implementation has not started. See [browser architecture and development plan](../../docs/browser-architecture.md).

## Changes vs upstream 0.6.2

The initial fork added the following three capabilities. This historical list does not cover subsequent fixes; consult the current source for runtime behavior.

### 1. `upload` command

```
camoufox-cli upload @ref|selector <file> [more files...]
```

- Backed by Playwright `locator.setInputFiles(paths)`.
- Accepts a snapshot ref (`@e1`) **or** a raw CSS selector.
- Variadic — one or more file paths. (Upstream has no upload at all.)
- Fails fast with `File not found: <p>` before touching the browser if any path is missing.

Used by the publish skills (`douyin-publish` / `xhs-publish` / `weibo-publish` / `zhihu-publish` / `wechat-channels-publish` / `youtube-publish`).

### 2. Fail-first queue (daemon-side)

A session runs **one command at a time**. A command that arrives while another is mid-flight on the same session **fails immediately** with:

```
session <name> 正忙，请等待当前操作完成后再试
```

- No hidden queueing, no auto-wait — the agent reads the fail text and decides to retry.
- `close` **bypasses** the queue, so a stuck session can always be torn down (`close --all` from the client side).
- Rationale: same-session concurrency isn't a benign failure but mutual stomping (`server.js` had no lock + shared `page.goto`). See spec §1.1.
- No timeout on the lock for now (spec §12 未定点) — if a command hangs, recover with `camoufox-cli close --all`.

### 3. `identity export` command

```
camoufox-cli identity              # print UA + fingerprint summary to stdout
camoufox-cli identity export <f>   # write it to <f> as JSON
```

Symmetric with `cookies export`. Writes the **effective** UA the browser reports (Camoufox spoofs it from the frozen fingerprint) plus a stable fingerprint hash, so scripts can import the UA alongside cookies (spec 原则 4) and detect identity drift:

```json
{
  "userAgent": "Mozilla/5.0 ...",
  "platform": "Win32",
  "language": "zh-CN",
  "languages": ["zh-CN", "zh", "en-US", "en"],
  "viewport": { "width": 1920, "height": 1080 },
  "persistent": "/home/u/.camoufox-cli/profiles/xhs",
  "identity": { "os": "windows", "locale": "zh-CN", "fingerprintHash": "a1b2…16hex" },
  "exportedAt": "2026-07-11T…"
}
```

`identity` is `null` for non-persistent (temporary) sessions. Requires a launched page (like `cookies`).

## What is **not** changed

- `--persistent` fingerprint freeze, `camoufox-cli.json` format, first-launch generation.
- `cookies export/import` JSON format (= Playwright `add_cookies`).
- Daemon model, `--session` isolation, `--json` envelope, `--headed`（默认 headless）, `--viewport WxH`（固定窗口尺寸，覆盖指纹默认的移动端比例）, config-file precedence.
- All other commands and flags.

## Build & install

```bash
patches/camoufox-cli/build.sh
```

This runs `npm install` (pulls deps incl. `typescript` for the build), `npm run build` (`tsc` → `dist/`), then `npm install -g .` so the `camoufox-cli` bin on `$PATH` points at this fork. Re-run after editing fork source. Idempotent in effect.

After install, `camoufox-cli install` (run by `scripts/apply-addons.sh`) downloads the Camoufox browser binary — same as upstream, unchanged.

## Tests

```bash
cd patches/camoufox-cli && npm test
```

Upstream tests are vendored unchanged. New tests:
- `../../test/camoufox-cli/cli.test.ts` — `upload` / `identity` arg parsing.
- `../../test/camoufox-cli/server-queue.test.ts` — fail-first queue + `close` bypass (mocks `execute`).

## Attribution

Upstream by **Benn Huang** — see `LICENSE` and the upstream repo. This fork only adds the three features above; all credit for the daemon, fingerprint freeze, and command set belongs upstream.
