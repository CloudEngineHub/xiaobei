import { createHash } from "node:crypto";
import { stringifyAwadaJson, type GatewayCredentials, type OperationReceipt } from "./api.js";
import { tryGetAwadaRuntime } from "./runtime.js";

type Submission = {
  fingerprint: string;
  requestId: string;
  createdAt: number;
  receipt?: OperationReceipt;
};
const hash = (value: string) => createHash("sha256").update(value).digest("hex");

/** Keep accepted/uncertain writes across reloads. Reusing an ID never creates a fresh operation. */
export async function withAwadaSubmissionLedger(
  credentials: GatewayCredentials,
  requestId: string,
  body: unknown,
  submit: () => Promise<OperationReceipt>,
): Promise<OperationReceipt> {
  const runtime = tryGetAwadaRuntime();
  if (!runtime) return submit(); // Standalone API consumers own their persistence.
  const scope = hash(
    JSON.stringify([credentials.relayBaseUrl, credentials.lane, credentials.awadaKey]),
  ).slice(0, 24);
  const store = runtime.state.openKeyedStore<Submission>({
    namespace: `submissions-${scope}`,
    maxEntries: 20_000,
    overflowPolicy: "reject-new",
  });
  const key = hash(requestId);
  const pending = { fingerprint: hash(stringifyAwadaJson(body)), requestId, createdAt: Date.now() };
  await store.registerIfAbsent(key, pending, { ttlMs: 30 * 86_400_000 });
  const record = await store.lookup(key);
  if (!record) throw new Error("Awada submission ledger could not retain the request");
  if (record.fingerprint !== pending.fingerprint)
    throw new Error("Awada request ID already belongs to different content");
  if (record.receipt) return record.receipt;
  if (Date.now() - record.createdAt >= 7 * 86_400_000)
    throw new Error(
      "Awada uncertain request is outside the server idempotency window; reconcile manually",
    );
  const receipt = await submit();
  await store.register(key, { ...record, receipt }, { ttlMs: 30 * 86_400_000 });
  return receipt;
}
