// Installation-only routing. Never changes the user's Git config or runtime env files.
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const githubHosts = new Set([
  "github.com", "api.github.com", "raw.githubusercontent.com",
  "codeload.github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com",
]);

export function githubProxy(env = process.env) {
  const value = env.XIAOBEI_GITHUB_PROXY || "";
  if (!value) return "";
  let url;
  try { url = new URL(value); } catch { /* Report the same error for all invalid prefixes. */ }
  if (!url || url.protocol !== "https:" || !url.hostname || url.username || url.password ||
      url.search || url.hash || /[\s?#]/.test(value)) {
    throw new Error("XIAOBEI_GITHUB_PROXY must be an HTTPS URL prefix without credentials, query or fragment");
  }
  return value.replace(/\/+$/, "") + "/";
}

export function githubDownloadUrl(input, env = process.env) {
  const prefix = githubProxy(env);
  const value = String(input);
  if (!prefix || value.startsWith(prefix)) return value;
  const url = new URL(value);
  return url.protocol === "https:" && githubHosts.has(url.host) ? prefix + value : value;
}

export function installationNetworkEnv(env = process.env) {
  const prefix = githubProxy(env);
  if (!prefix) return {};
  const result = { XIAOBEI_GITHUB_PROXY: prefix };
  const registry = env.npm_config_registry || env.NPM_CONFIG_REGISTRY || env.pnpm_config_registry ||
    "https://registry.npmmirror.com";
  for (const key of ["npm_config_registry", "NPM_CONFIG_REGISTRY", "pnpm_config_registry", "NPM_REGISTRY"])
    if (!env[key]) result[key] = registry;
  if (!env.npm_config_disturl && !env.NPM_CONFIG_DISTURL)
    result.npm_config_disturl = "https://npmmirror.com/mirrors/node";
  if (!env.PLAYWRIGHT_DOWNLOAD_HOST)
    result.PLAYWRIGHT_DOWNLOAD_HOST = "https://registry.npmmirror.com/-/binary/playwright";
  if (!env.PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT)
    result.PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT = "120000";
  result.MATRIX_SDK_CRYPTO_DOWNLOADS_BASE_URL = githubDownloadUrl(
    env.MATRIX_SDK_CRYPTO_DOWNLOADS_BASE_URL ||
      "https://github.com/matrix-org/matrix-rust-sdk-crypto-nodejs/releases/download", env,
  );

  // Git and npm/pnpm Git dependencies inherit these process-scoped URL rewrites.
  // Preserve caller-supplied entries and avoid adding them again in child installers.
  let count = Number(env.GIT_CONFIG_COUNT || 0);
  if (!Number.isSafeInteger(count) || count < 0) throw new Error("Invalid GIT_CONFIG_COUNT");
  for (const from of ["https://github.com/", "git@github.com:", "ssh://git@github.com/"]) {
    const key = `url.${prefix}https://github.com/.insteadOf`;
    let present = false;
    for (let i = 0; i < count; i++) {
      if ((result[`GIT_CONFIG_KEY_${i}`] ?? env[`GIT_CONFIG_KEY_${i}`]) === key &&
          (result[`GIT_CONFIG_VALUE_${i}`] ?? env[`GIT_CONFIG_VALUE_${i}`]) === from) present = true;
    }
    if (!present) {
      result[`GIT_CONFIG_KEY_${count}`] = key;
      result[`GIT_CONFIG_VALUE_${count++}`] = from;
    }
  }
  result.GIT_CONFIG_COUNT = String(count);
  return result;
}

export function configureInstallationNetwork() {
  Object.assign(process.env, installationNetworkEnv());
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const env = installationNetworkEnv();
    if (process.argv.length !== 3) throw new Error("Usage: download-network.mjs --shell|--json");
    // Name/value records also work with PowerShell 5.1's case-insensitive JSON parser.
    if (process.argv[2] === "--json") console.log(JSON.stringify(
      Object.entries(env).map(([name, value]) => ({ name, value })),
    ));
    else if (process.argv[2] === "--shell") {
      for (const [key, value] of Object.entries(env))
        console.log(`export ${key}='${value.replaceAll("'", "'\\''")}'`);
    } else throw new Error("Usage: download-network.mjs --shell|--json");
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
