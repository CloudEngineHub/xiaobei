#!/usr/bin/env node
// Shared source/tarball/Docker installer; invocation is an explicit deployment step.
import { chmodSync, existsSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const args = process.argv.slice(2);
if (args.includes("--help")) {
  console.log(
    "node scripts/install-browser.mjs [--root PATH] [--build] [--skip-assets] [--global]",
  );
  process.exit(0);
}
let root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
let build = false,
  assets = true,
  global = false;
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--root" && args[i + 1]) root = resolve(args[++i]);
  else if (args[i] === "--build") build = true;
  else if (args[i] === "--skip-assets") assets = false;
  else if (args[i] === "--global") global = true;
  else throw new Error(`Unknown/missing installer argument: ${args[i]}`);
}
const browser = join(root, "browser");
if (!existsSync(join(browser, "package-lock.json")))
  throw new Error("Browser package/lockfile missing from distribution");
const candidates = [
  join(root, "tools", "node", "lib", "node_modules", "npm", "bin", "npm-cli.js"),
  join(root, "tools", "node", "node_modules", "npm", "bin", "npm-cli.js"),
  join(dirname(process.execPath), "node_modules", "npm", "bin", "npm-cli.js"),
  join(dirname(process.execPath), "..", "lib", "node_modules", "npm", "bin", "npm-cli.js"),
  "/usr/share/nodejs/npm/bin/npm-cli.js",
];
const npm = candidates.find((file) => existsSync(file));
if (!npm) throw new Error("npm-cli.js missing alongside the Node runtime");
function run(argv) {
  const result = spawnSync(process.execPath, argv, {
    cwd: browser,
    stdio: "inherit",
    env: {
      ...process.env,
      PATH: `${dirname(process.execPath)}${process.platform === "win32" ? ";" : ":"}${process.env.PATH ?? ""}`,
    },
  });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`Browser installation failed (exit ${result.status})`);
}
run([npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund", ...(build ? [] : ["--omit=dev"])]);
if (build) run([npm, "run", "build"]);
if (!existsSync(join(browser, "dist", "client", "index.js")))
  throw new Error("Browser distribution has no built client");
const bin = join(root, "bin");
mkdirSync(bin, { recursive: true });
const quote = (value) => `'${value.replaceAll("'", "'\\''")}'`;
for (const [name, entry] of [
  ["xiaobei-browser", "cli.js"],
  ["camoufox-cli", "compat/cli.js"],
]) {
  const script = join(browser, "dist", entry);
  if (process.platform !== "win32") chmodSync(script, 0o755);
  if (process.platform === "win32") {
    writeFileSync(
      join(bin, `${name}.cmd`),
      `@echo off\r\n"${process.execPath}" "${script}" %*\r\n`,
    );
  } else {
    // Replace an old npm symlink itself, without truncating its target.
    const { unlinkSync } = await import("node:fs");
    try {
      unlinkSync(join(bin, name));
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }
    writeFileSync(
      join(bin, name),
      `#!/bin/sh\nexec ${quote(process.execPath)} ${quote(script)} "$@"\n`,
      { mode: 0o755 },
    );
  }
}
if (global)
  run([npm, "install", "--global", "--ignore-scripts", "--no-audit", "--no-fund", browser]);
if (assets) run([join(browser, "scripts", "install-assets.mjs")]);
console.log("xiaobei-browser and the camoufox-cli compatibility entry are ready");
