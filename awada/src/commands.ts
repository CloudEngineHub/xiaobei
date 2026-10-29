import { spawn } from "node:child_process";
import { readFileSync, existsSync } from "node:fs";
import { dirname, isAbsolute, resolve } from "node:path";
import type { OpenClawPluginApi, PluginRuntime, ReplyPayload } from "./runtime-api.js";
import { getAwadaRuntime } from "./runtime.js";

type LocalCommand = {
  name: string;
  description: string;
  acceptsArgs?: boolean;
  requireAuth?: boolean;
  reply?: { text?: string; mediaUrl?: string; mediaUrls?: string[] };
  exec?: { command: string; args?: string[]; timeoutMs?: number };
};
const names = new WeakMap<PluginRuntime, Set<string>>();

export function isAwadaLocalCommand(text: string): boolean {
  const name = text
    .trim()
    .match(/^\/([a-z][a-z0-9_-]*)(?:\s|$)/i)?.[1]
    ?.toLowerCase();
  return Boolean(name && names.get(getAwadaRuntime())?.has(name));
}

function readCommands(file: string): LocalCommand[] {
  if (!existsSync(file)) return [];
  const parsed = JSON.parse(readFileSync(file, "utf8"));
  if (parsed.version !== 1 || !Array.isArray(parsed.commands))
    throw new Error("Awada commands file requires version:1 and commands:[]");
  const seen = new Set<string>();
  for (const c of parsed.commands) {
    if (
      !c ||
      typeof c.name !== "string" ||
      !/^[a-z][a-z0-9_-]*$/.test(c.name) ||
      seen.has(c.name) ||
      typeof c.description !== "string" ||
      !c.description ||
      Boolean(c.reply) === Boolean(c.exec)
    ) {
      throw new Error(
        "Invalid or duplicate Awada local command; configure exactly one reply or exec handler",
      );
    }
    if (c.requireAuth !== undefined && typeof c.requireAuth !== "boolean")
      throw new Error("requireAuth must be boolean");
    if (c.acceptsArgs !== undefined && typeof c.acceptsArgs !== "boolean")
      throw new Error("acceptsArgs must be boolean");
    if (
      c.exec &&
      (typeof c.exec.command !== "string" ||
        !c.exec.command ||
        (c.exec.args !== undefined &&
          (!Array.isArray(c.exec.args) ||
            !c.exec.args.every((arg: unknown) => typeof arg === "string"))) ||
        (c.exec.timeoutMs !== undefined &&
          (!Number.isInteger(c.exec.timeoutMs) ||
            c.exec.timeoutMs < 1 ||
            c.exec.timeoutMs > 30_000)))
    ) {
      throw new Error("Invalid Awada command exec settings");
    }
    if (c.reply) validateReply(c.reply);
    seen.add(c.name);
  }
  return parsed.commands;
}

function validateReply(value: unknown): ReplyPayload {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("Command handler must return a reply JSON object");
  const reply = value as Record<string, unknown>;
  if (
    Object.keys(reply).some((key) => !["text", "mediaUrl", "mediaUrls"].includes(key)) ||
    (reply.text !== undefined && typeof reply.text !== "string") ||
    (reply.mediaUrl !== undefined && typeof reply.mediaUrl !== "string") ||
    (reply.mediaUrls !== undefined &&
      (!Array.isArray(reply.mediaUrls) || !reply.mediaUrls.every((url) => typeof url === "string")))
  ) {
    throw new Error("Command reply accepts text, mediaUrl and mediaUrls");
  }
  return reply as ReplyPayload;
}

function runCommand(
  definition: NonNullable<LocalCommand["exec"]>,
  file: string,
  context: Record<string, unknown>,
): Promise<ReplyPayload> {
  return new Promise((resolveReply, reject) => {
    const child = spawn(definition.command, definition.args ?? [], {
      cwd: dirname(file),
      stdio: ["pipe", "pipe", "pipe"],
      shell: false,
    });
    const chunks: Buffer[] = [];
    let length = 0;
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      reject(new Error("Awada local command timed out"));
    }, definition.timeoutMs ?? 15_000);
    child.stdout.on("data", (chunk: Buffer) => {
      length += chunk.length;
      if (length > 1024 * 1024) {
        child.kill("SIGKILL");
        reject(new Error("Awada local command output exceeds 1 MiB"));
      } else chunks.push(chunk);
    });
    // Do not expose script diagnostics, user text, or environment secrets as chat replies.
    child.stderr.resume();
    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      if (code !== 0) {
        reject(new Error(`Awada local command exited with code ${code}`));
        return;
      }
      try {
        resolveReply(validateReply(JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}")));
      } catch (error) {
        reject(error);
      }
    });
    child.stdin.on("error", () => {});
    child.stdin.end(JSON.stringify(context));
  });
}

export function registerAwadaCommands(api: OpenClawPluginApi, commandsFile?: string): void {
  const file = commandsFile
    ? isAbsolute(commandsFile)
      ? commandsFile
      : resolve(api.runtime.state.resolveStateDir(), commandsFile)
    : resolve(api.runtime.state.resolveStateDir(), "awada", "commands.json");
  if (commandsFile && !existsSync(file))
    throw new Error("Configured Awada commands file does not exist");
  const definitions = readCommands(file);
  names.set(api.runtime, new Set(definitions.map((command) => command.name)));
  for (const definition of definitions) {
    api.registerCommand({
      name: definition.name,
      description: definition.description,
      channels: ["awada"],
      acceptsArgs: definition.acceptsArgs ?? true,
      requireAuth: definition.requireAuth ?? true,
      handler: async (ctx) => {
        // Handler edits apply immediately; adding/removing names uses normal plugin reload.
        const current = readCommands(file).find((command) => command.name === definition.name);
        if (!current) return {};
        if (current.requireAuth !== false && !ctx.isAuthorizedSender)
          throw new Error("This command requires an authorized sender");
        if (current.reply) return validateReply(current.reply);
        return runCommand(current.exec!, file, {
          command: definition.name,
          args: ctx.args ?? "",
          commandBody: ctx.commandBody,
          senderId: ctx.senderId,
          channel: ctx.channel,
          accountId: ctx.accountId,
          agentId: ctx.agentId,
          sessionKey: ctx.sessionKey,
          sessionId: ctx.sessionId,
          from: ctx.from,
          to: ctx.to,
          isAuthorizedSender: ctx.isAuthorizedSender,
        });
      },
    });
  }
}
