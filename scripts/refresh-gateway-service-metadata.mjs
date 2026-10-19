#!/usr/bin/env node
import fs from "node:fs";
import { pathToFileURL } from "node:url";

/** Remove retired install-time version stamps from a standard managed systemd unit. */
export function refreshGatewayServiceMetadata(content) {
  const lines = content.split("\n");
  const assignments = new Map();
  const versionLines = new Set();
  let service = false;
  for (const [index, raw] of lines.entries()) {
    const line = raw.trim();
    if (/^\[[^\]]+\]$/.test(line)) service = line === "[Service]";
    if (!service) continue;
    // The upstream generator writes one assignment per line. Preserve custom compound
    // Environment directives rather than rewriting their quoting or unrelated variables.
    const match = /^Environment=(?:"([^"\\]*)"|'([^'\\]*)'|([^\s"'\\]+))\s*$/.exec(line);
    const assignment = match?.[1] ?? match?.[2] ?? match?.[3];
    if (!assignment) continue;
    const split = assignment.indexOf("=");
    if (split < 1) continue;
    const key = assignment.slice(0, split);
    const value = assignment.slice(split + 1);
    assignments.set(key, value);
    if (key === "OPENCLAW_SERVICE_VERSION" && /^\d{4}\.\d+\.\d+(?:[-+][\w.-]+)?$/.test(value))
      versionLines.add(index);
  }
  if (
    assignments.get("OPENCLAW_SERVICE_MARKER") !== "openclaw" ||
    assignments.get("OPENCLAW_SERVICE_KIND") !== "gateway" ||
    !versionLines.size
  )
    return content;
  // A previous updater may already have changed Description while leaving the env stamp old.
  return lines
    .filter((_line, index) => !versionLines.has(index))
    .map((line) =>
      line.replace(
        /^Description=OpenClaw Gateway \((?:(profile: [^,)\r\n]+), )?v\d{4}\.\d+\.\d+(?:[-+][\w.-]+)?\)$/,
        (_all, profile) =>
          profile ? `Description=OpenClaw Gateway (${profile})` : "Description=OpenClaw Gateway",
      ),
    )
    .join("\n");
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const file = process.argv[2];
  if (!file || process.argv.length !== 3)
    throw new Error("Usage: node refresh-gateway-service-metadata.mjs UNIT_FILE");
  if (fs.existsSync(file)) {
    const before = fs.readFileSync(file, "utf8");
    const after = refreshGatewayServiceMetadata(before);
    if (before !== after) {
      fs.writeFileSync(file, after);
      console.log("Removed retired Gateway service version metadata");
    }
  }
}
