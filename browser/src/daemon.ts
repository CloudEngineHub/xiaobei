import { lstatSync, readlinkSync } from "node:fs";
import { join } from "node:path";
import { RuntimeServer } from "./runtime/server.js";
import { CamoufoxDriver } from "./driver/runtime.js";
import { isAlive, readRecord, removeRecord, withLock } from "./state/registry.js";
import { stateHome } from "./platform/paths.js";
import { terminateOwnTree } from "./platform/process.js";

async function main(): Promise<void> {
  const [session, generation] = process.argv.slice(2);
  const home = stateHome();
  // Parent writes the actual child PID before granting startup ownership.
  let record = readRecord(session, home);
  for (let i = 0; i < 100 && record?.generation === generation && record.pid !== process.pid; i++) {
    await new Promise(r => setTimeout(r, 20)); record = readRecord(session, home);
  }
  if (!record || record.generation !== generation || record.pid !== process.pid) throw new Error("Startup ownership was not granted");
  const active = record;
  const run = async () => {
    const driver = new CamoufoxDriver(active.options);
    const closeDriver = driver.close.bind(driver);
    driver.close = async () => {
      const emergency = setTimeout(terminateOwnTree, 15000);
      try { await closeDriver(); } finally { clearTimeout(emergency); }
    };
    const runtime = new RuntimeServer(active, driver, error => {
      // Launch arguments may contain proxy credentials: log a type, not raw upstream arguments.
      process.stderr.write(`Browser runtime failed: ${error instanceof Error ? error.name : "Error"}\n`);
    });
    let shutdownTimer: ReturnType<typeof setTimeout> | undefined;
    const shutdown = () => {
      shutdownTimer ??= setTimeout(terminateOwnTree, 15000);
      void runtime.close().catch(() => terminateOwnTree());
    };
    process.on("SIGTERM", shutdown);
    process.on("SIGINT", shutdown);
    try {
      await runtime.start();
      await runtime.closed;
    } finally {
      if (shutdownTimer) clearTimeout(shutdownTimer);
      process.removeListener("SIGTERM", shutdown);
      process.removeListener("SIGINT", shutdown);
    }
  };
  try {
    if (active.options.persistent) {
      const profile = active.options.persistent;
      // Never unlink native profile locks or kill a process inferred from them.
      let nativeLocked = false;
      try {
        const lock = join(profile, "lock");
        if (lstatSync(lock).isSymbolicLink()) {
          const owner = readlinkSync(lock).match(/[:+](\d+)$/);
          // Firefox retains this symlink after a normal close. Leave a dead owner's
          // native lock in place for Firefox to reclaim; never unlink it ourselves.
          nativeLocked = !owner || isAlive(Number(owner[1]));
        }
      } catch (error) {
        if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
      }
      if (nativeLocked) throw new Error("PROFILE_IN_USE: native browser lock exists");
      await withLock(join(profile, ".xiaobei-runtime", "owner.lock"), run, 1500);
    } else { await run(); }
  } finally { removeRecord(active, home); }
}
main().then(() => process.exit(0)).catch(error => {
  process.stderr.write(`Startup failed: ${error instanceof Error ? error.message.replace(/https?:\/\/[^\s]+/g, "[url]") : "Error"}\n`);
  process.exit(1);
});
