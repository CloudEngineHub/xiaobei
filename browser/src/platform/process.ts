import { spawn } from "node:child_process";

/** Emergency cleanup only for this detached daemon's own tree. Never accepts a registry PID. */
export function terminateOwnTree(): void {
  if (process.platform === "win32") {
    const child = spawn("taskkill.exe", ["/PID", String(process.pid), "/T", "/F"], { windowsHide: true, stdio: "ignore" });
    child.on("error", () => process.exit(1));
    return;
  }
  process.removeAllListeners("SIGTERM");
  try { process.kill(-process.pid, "SIGTERM"); }
  catch { process.exit(1); }
}
