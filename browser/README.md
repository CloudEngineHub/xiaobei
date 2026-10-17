# xiaobei-browser runtime

The 5.8 browser runtime uses the main-repository TypeScript SDK `camoufox 0.5.8`, `playwright-core 1.62.1` and its paired browser `156.0.1-beta.36`. Node >=22.15 is required; the full product follows OpenClaw's higher Node requirement. The runtime owns its dependency tree. Do not hoist it into OpenClaw's Playwright 1.63.

The architecture, remaining validation, profile reset policy and snapshot/OSBI roadmap are maintained in [the browser development guide](../docs/browser-architecture.md). This package does not switch installed commands or production services merely by being built.

## Build and isolated validation

```bash
npm ci --ignore-scripts --prefix browser
npm run build --prefix browser

# All state and downloaded assets in ignored test/, away from existing profiles/cache.
export XIAOBEI_BROWSER_HOME="$PWD/test/browser/manual-state"
export XIAOBEI_BROWSER_ASSETS="$PWD/test/browser/manual-assets"
node browser/dist/cli.js doctor --json
node browser/scripts/install-assets.mjs
node browser/dist/cli.js --session demo --no-geoip start --json
node browser/dist/cli.js --session demo open about:blank --json
node browser/dist/cli.js --session demo snapshot --json
node browser/dist/cli.js --session demo stop --json

XIAOBEI_BROWSER_E2E=1 node --test test/browser/*.test.mjs
```

Asset installation is explicit and checksum verified, including the fpgen model, GeoIP AIO and uBlock Origin. Runtime startup fails if required assets are missing. Default assets live in `~/.camoufox-cli/assets/<version>-<release>/`; `CAMOUFOX_INSTALL_DIR` overrides the parent, `XIAOBEI_BROWSER_ASSETS` overrides the complete directory. `XIAOBEI_BROWSER_DOWNLOADS` optionally points the installer at pre-downloaded browser/addon/GeoIP files, which are still verified. The new asset directory does not replace the old SDK cache. PowerShell uses the same Node/JS entries and `$env:XIAOBEI_BROWSER_HOME` / `$env:XIAOBEI_BROWSER_ASSETS` for isolation.

Identity schema v2 records the SDK and fpgen identity. Old v1, corrupt or populated profiles without a compatible identity return `PROFILE_RESET_REQUIRED`; archive the whole old profile after stopping its session and use a fresh profile with a new login. Do not inject old cookies into a new identity. This release does not implement an automatic profile purge or lossless old-identity conversion.

## Interfaces

- `@wiseflow/browser/client`: shared `BrowserClient` and `resolveLaunchOptions`; start/status/sessions/request/stop. Status is read-only; stop waits for registration release.
- `@wiseflow/browser/protocol`: versioned requests, responses and errors.
- `@wiseflow/browser/driver`: controlled SDK launcher for isolated rendering/recording, sharing the same SDK/assets. Normal session callers use the client.
- `dist/cli.js`: `xiaobei-browser`, default persistent `default` profile.
- `dist/compat/cli.js`: `camoufox-cli` grammar/envelope; implicit ephemeral behavior retained, use `--persistent` when needed.
- `bridge/xiaobei_browser.py`: explicit Node + JS with JSON stdin and no shell, not a Python Camoufox SDK. Supply `node=` / `XIAOBEI_BROWSER_NODE`, and `home=` for isolated tests.

`--request-file FILE` / `--request-stdin` accept `{ "action": "eval", "params": { "expression": "document.title" } }` and optional requestId. Task ownership uses lease acquire/renew/wait/release and `--lease-token`. UTF-8 output is a single JSON result. A timeout after dispatch means `OUTCOME_UNKNOWN`; do not retry side effects automatically. `close --all` remains unsupported.

OpenClaw 2026.10.4 adapter source/tests ship in `patches/browser-camoufox-pivot/`. It uses the same client and a limited schema, with host/file/evaluate checks. Unsupported explicit SSRF/sandbox/run-bound policies are rejected. Current snapshots are public default ARIA snapshots plus DOM-bound action refs; AI mode, text/link projections and extraction SaaS remain planned.

Tests and fixtures live exclusively in ignored repository-root `test/browser/`; they must be transferred separately to other machines. Real E2E uses fresh profiles and local HTTP pages. Recording additionally needs the Playwright-version-specific FFmpeg executable; native Windows/macOS, actual platform logins, deployment, cancellation and special DOM coverage remain separate acceptance items. See the guide for evidence and limitations, including the observed varying `deBG` PNG ancillary chunk on FF156.
