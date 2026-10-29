import { createHash } from "node:crypto";
import { getAwadaRuntime } from "./runtime.js";
import type { InboundEvent } from "./redis-types.js";

export function awadaAccountScope(accountId: string, lane: string): string {
  return createHash("sha256")
    .update(JSON.stringify([accountId, lane]))
    .digest("hex")
    .slice(0, 24);
}

function eventStore(accountId: string) {
  return getAwadaRuntime().state.openKeyedStore<{ event: InboundEvent; configuredLane: string }>({
    namespace: `events-${awadaAccountScope(accountId, "")}`,
    maxEntries: 2000,
  });
}

/** System events remain inspectable without becoming user turns or triggering an LLM. */
export async function recordAwadaSystemEvent(
  accountId: string,
  event: InboundEvent,
  configuredLane = event.meta.lane ?? "",
): Promise<void> {
  await eventStore(accountId).register(
    JSON.stringify([event.meta.lane, event.event_id]),
    { event, configuredLane },
    { ttlMs: 7 * 86_400_000 },
  );
}

export async function listAwadaSystemEvents(
  accountId: string,
  lane: string,
  options: { type?: string; operationId?: string; limit?: number } = {},
) {
  const rows = await eventStore(accountId).entries();
  return rows
    .filter((row) => row.value.configuredLane === lane)
    .map((row) => row.value.event)
    .filter(
      (event) =>
        (!options.type || event.type === options.type) &&
        (!options.operationId || event.meta.operation_id === options.operationId),
    )
    .sort((a, b) => b.timestamp - a.timestamp)
    .slice(0, Math.min(100, Math.max(1, options.limit ?? 20)));
}
