#!/usr/bin/env node
// Explicit, checksum-verified asset installation. Runtime startup never downloads.
import { createHash } from "node:crypto";
import {
  createReadStream,
  createWriteStream,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  renameSync,
  rmSync,
  chmodSync,
  writeFileSync,
  copyFileSync,
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import { fileURLToPath } from "node:url";
import AdmZip from "adm-zip";
import { ensureModel, MODEL_PIN } from "camoufox/dist/fpgen/index.js";
import { assetPaths, lock } from "./asset-paths.mjs";
export { lock };
export async function verify(file, expected) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(file)) hash.update(chunk);
  if (hash.digest("hex") !== expected)
    throw new Error("Asset SHA-256 mismatch; nothing was installed");
}
async function download(url, file, sha256) {
  const cache = process.env.XIAOBEI_BROWSER_DOWNLOADS;
  const cached = cache && join(cache, new URL(url).pathname.split("/").pop());
  if (cached && existsSync(cached)) {
    await verify(cached, sha256);
    copyFileSync(cached, file);
    return;
  }
  process.stderr.write(`Downloading ${url}\n`);
  const response = await fetch(url, { signal: AbortSignal.timeout(600000) });
  if (!response.ok || !response.body)
    throw new Error(`Asset download failed: HTTP ${response.status}`);
  await pipeline(Readable.fromWeb(response.body), createWriteStream(file, { flags: "wx" }));
  await verify(file, sha256);
}
export function extract(file, destination) {
  const zip = new AdmZip(file);
  for (const entry of zip.getEntries()) {
    const name = entry.entryName.replaceAll("\\", "/");
    if (
      name.startsWith("/") ||
      name.split("/").includes("..") ||
      /^[a-z]:/i.test(name) ||
      ((entry.header.attr >>> 16) & 0xf000) === 0xa000
    )
      throw new Error("Unsafe archive entry");
  }
  zip.extractAllTo(destination, false);
  if (process.platform !== "win32")
    for (const entry of zip.getEntries())
      if (!entry.isDirectory && ((entry.header.attr >>> 16) & 0o111))
        chmodSync(join(destination, entry.entryName), ((entry.header.attr >>> 16) & 0o777) || 0o755);
}
function launcher(root) {
  return join(
    root,
    process.platform === "darwin"
      ? "Camoufox.app/Contents/MacOS/camoufox"
      : process.platform === "win32"
        ? "camoufox.exe"
        : "camoufox-bin",
  );
}
async function prepareModel(directory) {
  if (JSON.stringify(lock.model) !== JSON.stringify(MODEL_PIN))
    throw new Error("SDK model pin differs from assets.lock.json");
  await ensureModel({ dir: directory });
  for (const [name, digest] of Object.entries({ ...lock.model.file_sha256, ...lock.model.decompressed_sha256 }))
    await verify(join(directory, name), digest);
}
export async function installAssets({ modelInstaller = prepareModel } = {}) {
  const paths = assetPaths();
  const { directory } = paths;
  const asset = lock.assets[`${process.platform}-${process.arch}`];
  if (!asset)
    throw new Error(`Unsupported browser asset platform: ${process.platform}-${process.arch}`);
  const versionFile = join(directory, "version.json");
  const installed = existsSync(versionFile) ? JSON.parse(readFileSync(versionFile, "utf8")) : null;
  if (installed && (installed.version !== lock.version || installed.release !== lock.release))
    throw new Error(
      "Existing browser version differs from this versioned asset directory; inspect it before retrying.",
    );
  mkdirSync(dirname(directory), { recursive: true });
  const stage = mkdtempSync(join(dirname(directory), ".xiaobei-assets-"));
  try {
    if (!existsSync(launcher(directory))) {
      const archive = join(stage, "browser.zip");
      await download(
        `https://github.com/daijro/camoufox/releases/download/v${lock.version}-${lock.release}/${asset.name}`,
        archive,
        asset.sha256,
      );
      const unpacked = join(stage, "unpacked");
      extract(archive, unpacked);
      if (!existsSync(launcher(unpacked)))
        throw new Error("Verified archive lacks the browser launcher");
      const entries = readdirSync(unpacked);
      for (const name of entries) {
        if (
          [
            "profiles",
            "runtime",
            "config.json",
            "camoufox-cli.json",
            "version.json",
            "addons",
          ].includes(name) ||
          existsSync(join(directory, name))
        )
          throw new Error(`Refusing to overwrite existing asset/state: ${name}`);
      }
      mkdirSync(directory, { recursive: true });
      for (const name of entries) renameSync(join(unpacked, name), join(directory, name));
      if (process.platform !== "win32") {
        // ZIP libraries do not consistently restore Unix executable mode.
        for (const name of [
          "camoufox-bin",
          "camoufox",
          "glxtest",
          "gfxtest",
          "vaapitest",
          "pingsender",
          "updater",
        ])
          if (existsSync(join(directory, name))) chmodSync(join(directory, name), 0o755);
        chmodSync(launcher(directory), 0o755);
      }
      writeFileSync(
        versionFile,
        JSON.stringify({ version: lock.version, release: lock.release }) + "\n",
      );
    } else if (!installed)
      throw new Error(
        "Existing browser has no version metadata; refusing to replace or relabel it",
      );
    const addon = paths.addon;
    if (!existsSync(join(addon, "manifest.json"))) {
      if (existsSync(addon))
        throw new Error("Incomplete UBO directory exists; inspect it before retrying");
      const archive = join(stage, "ubo.xpi");
      await download(lock.ubo.url, archive, lock.ubo.sha256);
      const unpacked = join(stage, "ubo");
      extract(archive, unpacked);
      if (
        JSON.parse(readFileSync(join(unpacked, "manifest.json"), "utf8")).version !==
        lock.ubo.version
      )
        throw new Error("UBO version mismatch");
      mkdirSync(dirname(addon), { recursive: true });
      renameSync(unpacked, addon);
    }
    if (JSON.parse(readFileSync(join(addon, "manifest.json"), "utf8")).version !== lock.ubo.version)
      throw new Error("Installed UBO differs from the asset lock");
    if (!existsSync(paths.geoip)) {
      const file = join(stage, "geoip.mmdb");
      await download(lock.geoip.url, file, lock.geoip.sha256);
      renameSync(file, paths.geoip);
    } else await verify(paths.geoip, lock.geoip.sha256);
    await modelInstaller(paths.model);
    process.stderr.write(`Camoufox ${lock.version}-${lock.release} ready at ${directory}\n`);
  } finally {
    rmSync(stage, { recursive: true, force: true });
  }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  installAssets().catch((error) => {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  });
}
