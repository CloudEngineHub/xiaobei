import { exchange } from "../client/transport.js";
import { isObject, PROTOCOL_VERSION, requestId, RuntimeError, type Params } from "../protocol/index.js";
import { isAlive, type LaunchOptions } from "../state/registry.js";
import { readBrokerRecord } from "./state.js";

/** Missing owner is the only local-launch fallback. Never retry a dispatched start. */
export async function startThroughBroker(home: string, session: string, options: LaunchOptions): Promise<Params | null> {
  const record = readBrokerRecord(home);
  if (!record || !isAlive(record.pid)) return null;
  const send = async (action: string, params: Params = {}) => {
    const response = await exchange(record.endpoint, { protocolVersion: PROTOCOL_VERSION,
      requestId: requestId(), generation: record.generation, session: record.session,
      authorization: record.authorization, action, params,
      deadlineMs: Date.now() + (action === "hello" ? 2000 : 120000) });
    if (!response.ok) throw new RuntimeError(response.error!.code, response.error!.message);
    if (!isObject(response.data)) throw new RuntimeError("PROTOCOL_MISMATCH", "Browser broker response has no structured data");
    return response.data;
  };
  const hello = await send("hello");
  if (hello.kind !== "xiaobei-browser-broker") throw new RuntimeError("PROTOCOL_MISMATCH", "Expected browser broker");
  return send("start", { session, options });
}
