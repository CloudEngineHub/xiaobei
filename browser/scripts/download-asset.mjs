// Stream installation assets to disk, retry transient failures, then verify the pin.
import { createHash } from "node:crypto";
import { createReadStream, createWriteStream, statSync, truncateSync } from "node:fs";
import { basename } from "node:path";
import { Readable, Transform } from "node:stream";
import { pipeline } from "node:stream/promises";
import { setTimeout as delay } from "node:timers/promises";

class DownloadError extends Error {
  constructor(message, retryable = false, cause) {
    super(message, { cause });
    this.retryable = retryable;
  }
}

const diskErrors = new Set([
  "ENOSPC", "EDQUOT", "EACCES", "EPERM", "EROFS", "EIO", "EISDIR",
  "EMFILE", "ENFILE", "ENOENT", "ENAMETOOLONG",
]);
const detail = error => `${error.message}${error.cause?.code ? ` (${error.cause.code})` : ""}`;
function size(file) {
  try { return statSync(file).size; }
  catch (error) { if (error.code === "ENOENT") return 0; throw error; }
}

export async function verify(file, expected) {
  const hash = createHash("sha256");
  for await (const chunk of createReadStream(file)) hash.update(chunk);
  if (hash.digest("hex") !== expected)
    throw new Error("Asset SHA-256 mismatch; nothing was installed");
}

async function transfer(url, file, options) {
  let offset = size(file), received = offset, total;
  const controller = new AbortController();
  let idleTimer;
  const resetIdle = () => {
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => controller.abort(new Error(
      `No download progress for ${options.idleTimeoutMs / 1000}s`,
    )), options.idleTimeoutMs);
    idleTimer.unref();
  };
  const name = basename(new URL(url).pathname);
  const progressTimer = setInterval(() => {
    const progress = `${(received / 1048576).toFixed(1)} MiB` +
      (total ? ` / ${(total / 1048576).toFixed(1)} MiB (${Math.floor(received * 100 / total)}%)` : "");
    options.log(`Downloading ${name}: ${progress}`);
  }, options.progressIntervalMs);
  progressTimer.unref();
  resetIdle();
  try {
    const headers = { "Accept-Encoding": "identity" };
    if (offset) headers.Range = `bytes=${offset}-`;
    let response;
    try { response = await options.fetchImpl(url, { headers, signal: controller.signal }); }
    catch (error) { throw new DownloadError(`Asset request failed: ${detail(error)}`, true, error); }

    // A previous response may have delivered all bytes before its connection failed.
    if (response.status === 416 && offset &&
        response.headers.get("content-range") === `bytes */${offset}`) return;
    if (response.status === 416 && offset) {
      truncateSync(file, 0);
      throw new DownloadError("Server rejected the saved range; retrying from the beginning", true);
    }
    if (!response.ok || !response.body)
      throw new DownloadError(`Asset download failed: HTTP ${response.status}`,
        [408, 429].includes(response.status) || response.status >= 500);

    if (response.status === 206) {
      const range = /^bytes (\d+)-(\d+)\/(\d+|\*)$/.exec(response.headers.get("content-range") || "");
      if (!range || Number(range[1]) !== offset || Number(range[2]) < offset ||
          (range[3] !== "*" && Number(range[2]) >= Number(range[3]))) {
        if (offset) truncateSync(file, 0);
        throw new DownloadError("Invalid download Content-Range; refusing to append", offset > 0);
      }
      if (range[3] !== "*") total = Number(range[3]);
    } else if (response.status === 200) {
      if (offset) options.log("Server does not support resuming; restarting this asset download");
      offset = 0;
      const length = response.headers.get("content-length");
      if (length && /^\d+$/.test(length)) total = Number(length);
    } else throw new DownloadError(`Unexpected download response: HTTP ${response.status}`);

    received = offset;
    resetIdle();
    const progress = new Transform({
      transform(chunk, encoding, callback) {
        received += chunk.length;
        resetIdle();
        callback(null, chunk);
      },
    });
    try {
      await pipeline(Readable.fromWeb(response.body), progress,
        createWriteStream(file, { flags: offset ? "a" : "w", mode: 0o600 }));
    } catch (error) {
      if (diskErrors.has(error.code)) throw error;
      const reason = controller.signal.aborted ? controller.signal.reason : error;
      throw new DownloadError(`Asset transfer interrupted: ${detail(reason)}`, true, error);
    }
    if (total !== undefined && size(file) !== total)
      throw new DownloadError("Asset transfer incomplete; retrying the remaining bytes", true);
  } finally {
    clearTimeout(idleTimer);
    clearInterval(progressTimer);
    controller.abort();
  }
}

export async function downloadAsset(url, file, sha256, {
  fetchImpl = globalThis.fetch,
  maxAttempts = 5,
  retryDelayMs = 3000,
  idleTimeoutMs = 120000,
  progressIntervalMs = 30000,
  sleep = delay,
  log = message => process.stderr.write(message + "\n"),
} = {}) {
  if (!Number.isSafeInteger(maxAttempts) || maxAttempts < 1 ||
      !Number.isFinite(retryDelayMs) || retryDelayMs < 0 ||
      !Number.isFinite(idleTimeoutMs) || idleTimeoutMs <= 0 ||
      !Number.isFinite(progressIntervalMs) || progressIntervalMs <= 0)
    throw new Error("Invalid asset download retry/timeout options");
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const offset = size(file);
    log(`Downloading ${url} (attempt ${attempt}/${maxAttempts}${offset ? `, resume at ${offset} bytes` : ""})`);
    try {
      await transfer(url, file, { fetchImpl, idleTimeoutMs, progressIntervalMs, log });
      await verify(file, sha256);
      log(`Download verified: ${basename(new URL(url).pathname)}`);
      return;
    } catch (error) {
      if (!error.retryable) throw error;
      if (attempt === maxAttempts) throw new Error(
        `Asset download failed after ${maxAttempts} attempts: ${detail(error)}. ` +
        "For a persistent local download, use XIAOBEI_BROWSER_DOWNLOADS.", { cause: error },
      );
      const waitMs = Math.min(retryDelayMs * 2 ** (attempt - 1), 30000);
      log(`${detail(error)}; retrying in ${waitMs / 1000}s (${attempt + 1}/${maxAttempts})`);
      await sleep(waitMs);
    }
  }
}
