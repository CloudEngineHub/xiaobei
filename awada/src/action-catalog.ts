import { readFileSync } from "node:fs";
import { awadaActionId, awadaOperationView, type AwadaCatalogOperation } from "./presentation.js";
import { awadaTranscriptionAction, isAwadaPublicAction } from "./action-policy.js";
import { awadaDriveSendAction } from "./drive.js";

const snapshot = JSON.parse(
  readFileSync(new URL("./internal/operation-catalog.json", import.meta.url), "utf8"),
) as {
  catalogDate: string;
  operations: AwadaCatalogOperation[];
};
const baseline = new Map(snapshot.operations.map((operation) => [operation.id, operation]));
const discovered = new Map<string, Map<string, string>>();
const scopeKey = (scope: { relayBaseUrl: string; lane: string }) =>
  JSON.stringify([scope.relayBaseUrl, scope.lane]);

export function awadaTransportAction(
  scope: { relayBaseUrl: string; lane: string },
  action: string,
): string {
  // Do not reject actions absent from an account's advertised capabilities.
  return (
    discovered.get(scopeKey(scope))?.get(action) ??
    baseline.get(action)?.transportOperation ??
    action
  );
}

export function awadaKnownAction(action: string) {
  return baseline.get(awadaActionId(action));
}

export function awadaCatalogView(
  scope: { relayBaseUrl: string; lane: string },
  remote: Record<string, unknown>,
) {
  const operations = new Map([...baseline].filter(([id]) => isAwadaPublicAction(id)));
  operations.set(awadaTranscriptionAction.id, awadaTranscriptionAction);
  operations.set(awadaDriveSendAction.id, awadaDriveSendAction);
  const routes = new Map<string, string>();
  for (const operation of Array.isArray(remote.operations) ? remote.operations : []) {
    if (!operation || typeof operation.id !== "string") continue;
    const id = awadaActionId(operation.id);
    if (
      !isAwadaPublicAction(id) ||
      id === awadaTranscriptionAction.id ||
      id === awadaDriveSendAction.id
    )
      continue;
    routes.set(id, operation.id);
    operations.set(id, { ...operations.get(id), ...operation, id });
  }
  discovered.set(scopeKey(scope), routes);
  return {
    catalogDate: typeof remote.catalogDate === "string" ? remote.catalogDate : snapshot.catalogDate,
    operations: [...operations.values()].map((operation) => awadaOperationView(operation)),
  };
}
