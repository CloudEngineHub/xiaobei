import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

/** Product migration only. Preserve user browser options and unrelated plugins/policies. */
export function configureBrowserPlugin(original, root) {
  const config = structuredClone(original);
  const pluginPath = resolve(root, 'browser');
  config.plugins ??= {};
  config.plugins.entries ??= {};
  const entries = config.plugins.entries;
  const wasEnabled = entries.browser?.enabled !== false && config.browser?.enabled !== false &&
    !(config.plugins.deny ?? []).includes('browser');
  entries['xiaobei-browser'] ??= { enabled: wasEnabled };
  entries.browser = { ...entries.browser, enabled: false };
  if (config.plugins.deny?.includes('browser') && !config.plugins.deny.includes('xiaobei-browser'))
    config.plugins.deny.push('xiaobei-browser');
  config.plugins.load ??= {};
  const ownedPath = value => {
    if (typeof value !== 'string') return false;
    const expanded = value.replaceAll('${XIAOBEI_HOME}', root);
    if (resolve(expanded) === pluginPath) return true;
    try { return JSON.parse(readFileSync(join(expanded, 'openclaw.plugin.json'), 'utf8')).id === 'xiaobei-browser'; }
    catch { return false; }
  };
  config.plugins.load.paths = [...(config.plugins.load.paths ?? []).filter(value => !ownedPath(value)), pluginPath];
  // A plugin allowlist must include the newly installed plugin, while a pre-existing
  // deny continues to win. Do not enable or remove any unrelated plugin.
  if (Array.isArray(config.plugins.allow) && !config.plugins.allow.includes('xiaobei-browser'))
    config.plugins.allow.push('xiaobei-browser');

  const normalize = value => typeof value === 'string' ? value.trim().toLowerCase() : '';
  const matches = (pattern, name) => {
    const source = normalize(pattern).split('*').map(part => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*');
    return new RegExp(`^${source}$`).test(name);
  };
  const policy = tools => {
    if (!tools || typeof tools !== 'object') return;
    for (const key of ['allow', 'alsoAllow', 'deny']) {
      if (!Array.isArray(tools[key])) continue;
      const values = tools[key];
      const containsBrowser = values.some(value => matches(value, 'browser') ||
        ['group:ui', 'group:openclaw'].includes(normalize(value)));
      tools[key] = [...new Set(values.map(value => normalize(value) === 'browser' ? 'xiaobei_browser' : value))];
      if (containsBrowser && !tools[key].some(value => matches(value, 'xiaobei_browser'))) tools[key].push('xiaobei_browser');
    }
  };
  const visit = value => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return;
    for (const [key, child] of Object.entries(value)) {
      if (key === 'tools' && child && typeof child === 'object') {
        policy(child);
        for (const provider of Object.values(child.byProvider ?? {})) policy(provider);
      }
      if (key === 'toolsBySender' && child && typeof child === 'object') {
        for (const sender of Object.values(child)) policy(sender);
      }
      visit(child);
    }
  };
  visit({ tools: config.tools, agents: config.agents, channels: config.channels });
  return config;
}
