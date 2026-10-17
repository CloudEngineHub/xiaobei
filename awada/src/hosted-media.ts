import type { IncomingMessage, ServerResponse } from "node:http";
import {
  createHostedOutboundMediaStore,
  loadOutboundMediaFromUrl,
  type HostedOutboundMediaStore,
  type HostedOutboundMediaMetaRecord,
  type HostedOutboundMediaChunkRecord,
  type OutboundMediaLoadOptions,
} from "openclaw/plugin-sdk/outbound-media";
import { safeEqualSecret } from "openclaw/plugin-sdk/security-runtime";
import type { OpenClawPluginApi, PluginRuntime } from "./runtime-api.js";
import { getAwadaRuntime } from "./runtime.js";
import { awadaAccountScope } from "./events.js";
import { listAwadaAccountIds, resolveAwadaAccount } from "./accounts.js";
import { createRuntimeConfigReader } from "openclaw/plugin-sdk/runtime-config-snapshot";

const PREFIX = "/plugins/awada/media/";
const stores = new WeakMap<PluginRuntime, Map<string, HostedOutboundMediaStore>>();
function mediaStore(scope: string): HostedOutboundMediaStore {
  const runtime = getAwadaRuntime();
  let scoped = stores.get(runtime);
  if (!scoped) {
    scoped = new Map();
    stores.set(runtime, scoped);
  }
  let store = scoped.get(scope);
  if (!store) {
    store = createHostedOutboundMediaStore({
      metadataStore: runtime.state.openKeyedStore<HostedOutboundMediaMetaRecord>({
        namespace: `media-${scope}`,
        maxEntries: 80,
      }),
      chunkStore: runtime.state.openKeyedStore<HostedOutboundMediaChunkRecord>({
        namespace: `media-chunks-${scope}`,
        maxEntries: 16_384,
      }),
      ttlMs: 60 * 60_000,
      maxEntries: 64,
      maxChunkRows: 16_384,
      maxTotalBytes: 256 * 1024 * 1024,
      overflowPolicy: "reject-new",
      resolveExpiresAtMs: (ttl) => Date.now() + ttl,
    });
    scoped.set(scope, store);
  }
  return store;
}

export async function prepareAwadaHostedMedia(params: {
  accountId: string;
  lane: string;
  publicBaseUrl: string;
  mediaUrl: string;
  maxBytes: number;
  mediaAccess?: OutboundMediaLoadOptions["mediaAccess"];
  mediaLocalRoots?: readonly string[];
  mediaReadFile?: (filePath: string) => Promise<Buffer>;
}) {
  const scope = awadaAccountScope(params.accountId, params.lane);
  const loaded = await loadOutboundMediaFromUrl(params.mediaUrl, {
    maxBytes: params.maxBytes,
    mediaAccess: params.mediaAccess,
    mediaLocalRoots: params.mediaLocalRoots,
    mediaReadFile: params.mediaReadFile,
  });
  const saved = await getAwadaRuntime().channel.media.saveMediaBuffer(
    loaded.buffer,
    loaded.contentType,
    "outbound",
    params.maxBytes,
    loaded.fileName,
  );
  return mediaStore(scope).prepareUrl({
    mediaUrl: saved.path,
    routePath: `${PREFIX}${scope}/`,
    publicBaseUrl: params.publicBaseUrl,
    maxBytes: params.maxBytes,
  });
}

export function registerAwadaMediaRoute(api: OpenClawPluginApi): void {
  const readConfig = createRuntimeConfigReader(api.config);
  api.registerHttpRoute({
    path: PREFIX,
    match: "prefix",
    auth: "plugin",
    handler: async (req: IncomingMessage, res: ServerResponse) => {
      const url = new URL(req.url ?? "/", "http://localhost");
      const match = url.pathname.match(/^\/plugins\/awada\/media\/([a-f0-9]{24})\/([a-f0-9]{24})$/);
      if (!match || !["GET", "HEAD"].includes(req.method ?? "GET")) {
        res.statusCode = 404;
        res.end();
        return;
      }
      const scope = match[1]!;
      const id = match[2]!;
      const cfg = readConfig();
      const allowed = listAwadaAccountIds(cfg).some((accountId) => {
        const account = resolveAwadaAccount({ cfg, accountId });
        return account.enabled && awadaAccountScope(accountId, account.lane) === scope;
      });
      if (!allowed) {
        res.statusCode = 404;
        res.end();
        return;
      }
      const store = mediaStore(scope);
      const metadata = await store.readMetadata(id);
      const token = url.searchParams.get("token");
      if (
        !metadata ||
        !token ||
        !safeEqualSecret(metadata.token, token) ||
        metadata.routePath !== `${PREFIX}${scope}/`
      ) {
        res.statusCode = 404;
        res.end();
        return;
      }
      const entry = await store.read(id);
      if (!entry) {
        res.statusCode = 404;
        res.end();
        return;
      }
      res.setHeader("Content-Type", metadata.contentType ?? "application/octet-stream");
      res.setHeader("Content-Length", entry.buffer.length);
      res.setHeader("Cache-Control", "private, no-store");
      res.setHeader("X-Content-Type-Options", "nosniff");
      res.end(req.method === "HEAD" ? undefined : entry.buffer);
    },
  });
}
