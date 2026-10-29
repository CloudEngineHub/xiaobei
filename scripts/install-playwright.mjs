#!/usr/bin/env node
// Provision the browser-owned driver and headless shell for every local renderer.
import { existsSync, readFileSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { spawnSync } from "node:child_process";
import { configureInstallationNetwork } from "../browser/scripts/download-network.mjs";

configureInstallationNetwork();
let root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
let skipBrowser = false;
const args = process.argv.slice(2);
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--root" && args[i + 1]) root = resolve(args[++i]);
  else if (args[i] === "--skip-browser") skipBrowser = true;
  else throw new Error(`Unknown/missing installer argument: ${args[i]}`);
}
const browser = join(root, "browser");
const pin = JSON.parse(readFileSync(join(browser, "package.json"), "utf8")).dependencies["playwright-core"];
const manifest = join(browser, "node_modules/playwright-core/package.json");
const env = { ...process.env, PLAYWRIGHT_BROWSERS_PATH: join(browser, ".browsers"),
  PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD: "1" };
function run(args) {
  const result = spawnSync(process.execPath, args, { cwd: browser, env, stdio: "inherit" });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`Shared Playwright installation failed (exit ${result.status})`);
}
if (!existsSync(manifest) || JSON.parse(readFileSync(manifest, "utf8")).version !== pin) {
  const candidates = [
    join(root, "tools/node/lib/node_modules/npm/bin/npm-cli.js"),
    join(root, "tools/node/node_modules/npm/bin/npm-cli.js"),
    join(dirname(process.execPath), "node_modules/npm/bin/npm-cli.js"),
    join(dirname(process.execPath), "../lib/node_modules/npm/bin/npm-cli.js"),
    "/usr/share/nodejs/npm/bin/npm-cli.js",
  ];
  const npm = candidates.find(existsSync);
  if (!npm) throw new Error("npm-cli.js missing alongside the Node runtime");
  run([npm, "ci", "--omit=dev", "--ignore-scripts", "--no-audit", "--no-fund"]);
}
if (!skipBrowser) {
  // Playwright owns revision selection, extraction locks and old revision cleanup.
  run([join(browser, "node_modules/playwright-core/cli.js"), "install", "chromium-headless-shell"]);
  const { sharedPlaywrightInfo } = await import(pathToFileURL(join(browser, "scripts/shared-playwright.mjs")));
  const info = sharedPlaywrightInfo();
  run(["-e", `require('node:child_process').execFileSync(${JSON.stringify(info.executablePath)}, ['--version'], {stdio:'inherit'})`]);
  // Retire only caches owned by the old xiaobei renderers. User/system caches
  // may belong to other applications and are never uninstalled here.
  const deck = join(root, "crews/content-producer/skills/expert-video/tools/deck-render");
  rmSync(join(deck, ".browsers"), { recursive: true, force: true });
  rmSync(join(deck, ".deck-render-browser"), { force: true });
  for (const directory of [deck, join(root, "crews/main/skills/ui-demo")]) {
    const file = join(directory, "package.json");
    const pkg = existsSync(file) ? JSON.parse(readFileSync(file, "utf8")) : {};
    if (!pkg.dependencies?.["playwright-core"] && !pkg.dependencies?.playwright) {
      for (const name of ["playwright-core", "playwright"])
        rmSync(join(directory, "node_modules", name), { recursive: true, force: true });
      for (const name of ["playwright-core", "playwright"])
        for (const extension of ["", ".cmd", ".ps1"])
          rmSync(join(directory, "node_modules/.bin", name + extension), { force: true });
    }
  }
  console.log(`Shared Playwright ${pin} and Chromium ready: ${info.browsersPath}`);
} else console.log(`Shared Playwright ${pin} ready; Chromium download skipped`);
