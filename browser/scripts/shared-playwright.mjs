// One Playwright owner and browser cache per installation, independent of cwd.
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const browserRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export const browsersPath = join(browserRoot, ".browsers");
const require = createRequire(join(browserRoot, "package.json"));
export const playwrightVersion = JSON.parse(readFileSync(join(browserRoot, "package.json"), "utf8")).dependencies["playwright-core"];
const repair = "Run node scripts/install-playwright.mjs from the xiaobei installation";

export function requirePlaywright() {
  const manifest = join(browserRoot, "node_modules/playwright-core/package.json");
  if (!existsSync(manifest) || JSON.parse(readFileSync(manifest, "utf8")).version !== playwrightVersion)
    throw new Error(`Shared playwright-core@${playwrightVersion} is missing or mismatched. ${repair}`);
  // Set before loading Playwright: its registry captures this at import time.
  process.env.PLAYWRIGHT_BROWSERS_PATH = browsersPath;
  return require("playwright-core");
}

export function sharedPlaywrightInfo({ required = true } = {}) {
  requirePlaywright();
  // Version-sensitive registry access stays here, alongside the owner version check.
  const { registry, registryDirectory } = require("playwright-core/lib/coreBundle").registry;
  // Another caller may have loaded the registry before our env was set. Resolve
  // its version/platform suffix under our cache and always launch explicitly.
  const registered = registry.findExecutable("chromium-headless-shell").executablePath();
  const executablePath = registered && join(browsersPath, relative(registryDirectory, registered));
  const installed = !!executablePath && existsSync(executablePath);
  if (required && !installed) throw new Error(`Shared Chromium headless shell is missing. ${repair}`);
  return { playwrightVersion, browsersPath, executablePath, installed };
}

export async function launchChromium(options = {}) {
  const { executablePath } = sharedPlaywrightInfo();
  return requirePlaywright().chromium.launch({ ...options, executablePath, headless: true });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { console.log(JSON.stringify(sharedPlaywrightInfo())); }
  catch (error) { console.error(error.message); process.exitCode = 1; }
}
