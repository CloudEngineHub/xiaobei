#!/usr/bin/env node
/** Compatibility wrapper for existing follow-up tasks; core owns config, routing and V2 transport. */
import { spawn } from "node:child_process";
import { parseArgs } from "node:util";

try {
  const { values } = parseArgs({
    options: {
      "user-id-external": { type: "string" },
      text: { type: "string" },
      account: { type: "string" },
    },
    strict: true,
  });
  if (!values["user-id-external"]?.trim() || !values.text?.trim()) {
    throw new Error(
      "Usage: proactive-send --user-id-external <id> --text <message> [--account <id>]",
    );
  }
  const args = [
    "message",
    "send",
    "--channel",
    "awada",
    "--target",
    `user:${values["user-id-external"]}`,
    "--message",
    values.text,
    "--json",
    ...(values.account ? ["--account", values.account] : []),
  ];
  const child = spawn("openclaw", args, { stdio: "inherit", shell: false });
  child.once("error", (error) => {
    console.error(`proactive-send: ${error.message}`);
    process.exitCode = 1;
  });
  child.once("exit", (code, signal) => {
    process.exitCode = signal ? 1 : (code ?? 1);
  });
} catch (error) {
  console.error(`proactive-send: ${error.message}`);
  process.exitCode = 1;
}
