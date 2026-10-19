import { createHash } from "node:crypto";
import { stringifyAwadaJson, type GatewayCredentials, type OperationReceipt } from "./api.js";
import { tryGetAwadaRuntime } from "./runtime.js";

type Submission = {
  fingerprint: string;
  requestId: string;
  createdAt: number;
  receipt?: OperationReceipt;
  owner?: string;
};
const hash = (value: string) => createHash("sha256").update(value).digest("hex");
const RETENTION_MS = 7 * 86_400_000;
const pendingClaims = new Map<string, Set<Promise<void>>>();
const credentialScope = (credentials: GatewayCredentials) =>
  hash(JSON.stringify([credentials.relayBaseUrl, credentials.lane, credentials.awadaKey])).slice(
    0,
    24,
  );

export function awadaSessionOwner(context: {
  agentId?: string;
  sessionId?: string;
}): string | undefined {
  return context.agentId && context.sessionId
    ? hash(JSON.stringify([context.agentId, context.sessionId]))
    : undefined;
}

function operationStore(credentials: GatewayCredentials) {
  return tryGetAwadaRuntime()?.state.openKeyedStore<{ requestId: string; owner?: string }>({
    namespace: `operations-${credentialScope(credentials)}`,
    maxEntries: 20_000,
    overflowPolicy: "reject-new",
  });
}

/** Only locally accepted sends can acquire a session claim through the message tool hook. */
export async function claimAwadaOperation(
  credentials: GatewayCredentials,
  operationId: string,
  owner: string,
): Promise<void> {
  const store = operationStore(credentials);
  const record = await store?.lookup(hash(operationId));
  if (!store || !record || (record.owner && record.owner !== owner)) return;
  await store.registerIfAbsent(hash(JSON.stringify([operationId, owner])), record, {
    ttlMs: RETENTION_MS,
  });
}

export async function assertAwadaOperationOwner(
  credentials: GatewayCredentials,
  operationId: string,
  owner?: string,
): Promise<void> {
  if (owner) await Promise.all(pendingClaims.get(owner) ?? []);
  const store = operationStore(credentials);
  if (!owner || !(await store?.lookup(hash(JSON.stringify([operationId, owner])))))
    throw new Error(
      "Awada result is not owned by this agent session; account-wide results require the channel owner",
    );
}

/** Embedded-runtime tool completion hooks may still be finishing when the next tool starts. */
export function retainAwadaMessageClaims(owner: string, claim: () => Promise<void>): Promise<void> {
  const pending = pendingClaims.get(owner) ?? new Set<Promise<void>>();
  pendingClaims.set(owner, pending);
  const work = Promise.resolve().then(claim);
  const settled = work.finally(() => {
    pending.delete(settled);
    if (!pending.size) pendingClaims.delete(owner);
  });
  pending.add(settled);
  return settled;
}

/** Keep accepted/uncertain writes across reloads. Reusing an ID never creates a fresh operation. */
export async function withAwadaSubmissionLedger(
  credentials: GatewayCredentials,
  requestId: string,
  body: unknown,
  submit: () => Promise<OperationReceipt>,
  owner?: string,
): Promise<OperationReceipt> {
  const runtime = tryGetAwadaRuntime();
  if (!runtime) {
    if (owner) throw new Error("Awada session submission requires persistent runtime state");
    return submit(); // Standalone API consumers own their persistence.
  }
  const scope = credentialScope(credentials);
  const store = runtime.state.openKeyedStore<Submission>({
    namespace: `submissions-${scope}`,
    maxEntries: 20_000,
    overflowPolicy: "reject-new",
  });
  const key = hash(requestId);
  const pending = {
    fingerprint: hash(stringifyAwadaJson(body)),
    requestId,
    createdAt: Date.now(),
    ...(owner ? { owner } : {}),
  };
  await store.registerIfAbsent(key, pending, { ttlMs: 30 * 86_400_000 });
  const record = await store.lookup(key);
  if (!record) throw new Error("Awada submission ledger could not retain the request");
  if (record.fingerprint !== pending.fingerprint)
    throw new Error("Awada request ID already belongs to different content");
  if (record.owner !== owner)
    throw new Error("Awada request ID already belongs to another agent session");
  const retainReceipt = async (receipt: OperationReceipt) => {
    if (!receipt.eventId || !receipt.streamId)
      throw new Error("Awada returned an invalid enqueue receipt");
    await operationStore(credentials)!.registerIfAbsent(
      hash(receipt.eventId),
      { requestId, ...(owner ? { owner } : {}) },
      { ttlMs: RETENTION_MS },
    );
    if (owner) await claimAwadaOperation(credentials, receipt.eventId, owner);
    return receipt;
  };
  if (record.receipt) return retainReceipt(record.receipt);
  if (Date.now() - record.createdAt >= 7 * 86_400_000)
    throw new Error(
      "Awada uncertain request is outside the server idempotency window; reconcile manually",
    );
  const receipt = await submit();
  await store.register(key, { ...record, receipt }, { ttlMs: 30 * 86_400_000 });
  return retainReceipt(receipt);
}
