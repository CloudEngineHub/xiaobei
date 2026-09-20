import { fileURLToPath } from "node:url";

export default {
  root: fileURLToPath(new URL("../", import.meta.url)),
  resolve: {
    alias: [{
      find: /^openclaw\/plugin-sdk\/(.+)$/,
      replacement: fileURLToPath(new URL("../openclaw/dist/plugin-sdk/", import.meta.url)) + "$1.js",
    }],
  },
  test: {
    include: ["test/camoufox-cli/**/*.test.ts", "test/awada/**/*.test.ts"],
  },
};
