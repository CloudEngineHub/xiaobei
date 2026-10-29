export const lock: {
  sdk: { name: string; version: string };
  version: string; release: string;
  model: { sha256: string };
  ubo: { version: string };
};
export function assetPaths(): { directory: string; launcher: string; addon: string; model: string; geoip: string };
