#!/usr/bin/env node
// Refresh the client snapshot from the complete server contract, independent of any account.
import fs from "node:fs";
import { createHash } from "node:crypto";
import { awadaActionId, awadaSchema, awadaTechnicalText } from "../awada/src/presentation.ts";
import { isAwadaRemovedAction } from "../awada/src/action-policy.ts";

const [source] = process.argv.slice(2);
if (!source) throw new Error("Usage: node scripts/sync-awada-catalog.mjs CATALOG_JSON");
const bytes = fs.readFileSync(source);
const catalog = JSON.parse(bytes.toString("utf8"));
if (!Array.isArray(catalog.operations) || !catalog.operations.length)
  throw new Error("Empty operation catalog");
if (
  typeof catalog.retrievedAt !== "string" ||
  catalog.operations.some(
    (operation) =>
      typeof operation.id !== "string" ||
      !operation.schema ||
      !operation.querySchema ||
      !operation.responseSchema,
  )
) {
  throw new Error(
    "Use the complete server contract with schemas and retrievedAt, not account capabilities",
  );
}
const seen = new Set();
const operations = catalog.operations
  .filter((operation) => !isAwadaRemovedAction(operation.id))
  .map((operation) => {
    const id = awadaActionId(operation.id);
    if (seen.has(id))
      throw new Error(`Action ID collision: ${id}; define a distinct Awada action before syncing`);
    seen.add(id);
    const { title, notes, async, custom, deprecated, scope, schema, querySchema, responseSchema } =
      operation;
    return {
      id,
      transportOperation: operation.id,
      title: awadaTechnicalText(title ?? id),
      notes: awadaTechnicalText(notes ?? ""),
      async,
      custom,
      deprecated,
      scope,
      schema: awadaSchema(schema),
      querySchema: awadaSchema(querySchema),
      responseSchema: awadaSchema(responseSchema),
    };
  });
const destination = new URL("../awada/src/internal/operation-catalog.json", import.meta.url);
fs.mkdirSync(new URL(".", destination), { recursive: true });
fs.writeFileSync(
  destination,
  JSON.stringify(
    {
      catalogDate: catalog.retrievedAt,
      sourceSha256: createHash("sha256").update(bytes).digest("hex"),
      operations,
    },
    null,
    2,
  ) + "\n",
);
console.log(`Synced ${operations.length} Awada actions (${catalog.retrievedAt})`);
