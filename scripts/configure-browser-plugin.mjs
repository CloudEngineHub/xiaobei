#!/usr/bin/env node
import { existsSync, readFileSync, writeFileSync, renameSync, unlinkSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { homedir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { configureBrowserPlugin } from './lib/browser-plugin-config.mjs';

let root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
let config = process.env.OPENCLAW_CONFIG_PATH ?? process.env.OPENCLAW_JSON ??
  join(process.env.OPENCLAW_STATE_DIR ?? join(homedir(), '.openclaw'), 'openclaw.json');
let write = false;
const args = process.argv.slice(2);
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--root' && args[i + 1]) root = resolve(args[++i]);
  else if (args[i] === '--config' && args[i + 1]) config = resolve(args[++i]);
  else if (args[i] === '--write') write = true;
  else throw new Error('Usage: configure-browser-plugin.mjs [--root PATH] [--config FILE] [--write]');
}
if (!existsSync(join(root, 'browser/openclaw.plugin.json')) || !existsSync(join(root, 'browser/dist/broker/server.js')))
  throw new Error('Build/install the xiaobei-browser plugin before migrating configuration');
if (!existsSync(config)) {
  console.log(JSON.stringify({ skipped: true, reason: 'no runtime configuration' }));
} else {
  const original = readFileSync(config), raw = JSON.parse(original);
  if (Object.hasOwn(raw, '$include')) throw new Error('Included configs require the upstream ownership-aware config workflow');
  const candidate = configureBrowserPlugin(raw, root);
  const changed = JSON.stringify(candidate) !== JSON.stringify(raw);
  const summary = { changed, written: false };
  if (write && changed) {
    const temporary = `${config}.${randomUUID()}.tmp`;
    try {
      writeFileSync(temporary, JSON.stringify(candidate, null, 2) + '\n', { mode: 0o600, flag: 'wx' });
      const host = join(root, 'openclaw/dist/index.js');
      if (!existsSync(host)) throw new Error('Built OpenClaw CLI missing; configuration was not changed');
      const validation = spawnSync(process.execPath, [host, 'config', 'validate', '--json'], {
        env: { ...process.env, OPENCLAW_CONFIG_PATH: temporary }, encoding: 'utf8', timeout: 120000,
      });
      if (validation.status !== 0) throw new Error('Browser plugin configuration failed native validation; source unchanged');
      if (!readFileSync(config).equals(original)) throw new Error('Configuration changed during browser migration; retry against the current file');
      const backup = `${config}.browser-backup-${Date.now()}`;
      writeFileSync(backup, original, { mode: 0o600, flag: 'wx' });
      renameSync(temporary, config);
      summary.written = true;
      summary.backup = backup;
    } finally { try { unlinkSync(temporary); } catch {} }
  }
  console.log(JSON.stringify(summary));
}
