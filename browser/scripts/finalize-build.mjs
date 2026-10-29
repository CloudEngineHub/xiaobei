import { chmodSync } from "node:fs";

// npm global entries link directly into dist; rebuilding must keep them executable.
if (process.platform !== "win32") {
  for (const entry of ["../dist/cli.js", "../dist/compat/cli.js"])
    chmodSync(new URL(entry, import.meta.url), 0o755);
}
