/** Snapshot refs bind to captured DOM nodes, never a later role/name match. */
import { randomInt, randomUUID } from "node:crypto";
import type { ElementHandle, Locator, Page } from "playwright-core";
import { RuntimeError } from "../protocol/index.js";

type NodeHandle = ElementHandle<Node>;
const INTERACTIVE = new Set(["link", "button", "combobox", "textbox", "textarea", "checkbox", "radio", "switch", "slider", "tab", "tabpanel", "menuitem", "option", "select", "listbox", "searchbox"]);
const LINE = /^(\s*-\s+)([a-z]+)(?:\s+("(?:[^"\\]|\\.)*"))?/;

export class RefRegistry {
  private entries = new Map<string, NodeHandle>();
  private counter = randomInt(1000000, 1000000000);
  private epoch = 0;
  private page: Page | undefined;
  snapshotId: string | undefined;

  async capture(page: Page, target: Locator, interactive = false): Promise<string> {
    this.invalidate();
    const epoch = this.epoch;
    const root = await target.elementHandle();
    if (!root) throw new RuntimeError("STALE_REF", "Snapshot scope disappeared; refresh the snapshot");
    const observer = await root.evaluateHandle(root => {
      const state = { changed: false, observer: new MutationObserver(() => { state.changed = true; }) };
      state.observer.observe(root.ownerDocument, { subtree: true, childList: true, attributes: true, characterData: true });
      return state;
    });
    const acquired: NodeHandle[] = [];
    try {
      if (await root.evaluate(root => !!root.ownerDocument.querySelector("[aria-owns]")))
        throw new RuntimeError("ACTION_UNSUPPORTED", "ARIA ownership can reorder snapshot nodes; action ref capture is not supported on this page yet");
      const aria = await target.ariaSnapshot();
      const lines = aria.split("\n");
      const parsed = lines.map(line => {
        const m = line.match(LINE);
        if (!m || m[2] === "text") return undefined;
        const name: string = m[3] ? JSON.parse(m[3]) : "";
        return { role: m[2], name, key: JSON.stringify([m[2], name]) };
      });
      const counts = new Map<string, number>();
      for (const item of parsed) if (item && (!interactive || INTERACTIVE.has(item.role))) counts.set(item.key, (counts.get(item.key) ?? 0) + 1);
      if ([...counts.values()].reduce((a, b) => a + b, 0) > 2000) throw new RuntimeError("PAYLOAD_TOO_LARGE", "Too many action refs; use snapshot -s to narrow the scope");
      const groups = new Map<string, NodeHandle[]>();
      for (const [key, count] of counts) {
        const [role, name] = JSON.parse(key);
        const candidates = await page.getByRole(role, { name, exact: true }).elementHandles();
        acquired.push(...candidates);
        const scoped: NodeHandle[] = [];
        for (const candidate of candidates) if (await root.evaluate((root, node) => root.contains(node), candidate)) scoped.push(candidate);
        // ARIA ownership/hidden nodes may change tree order/count. Do not guess.
        if (scoped.length === count) groups.set(key, scoped);
      }
      if (epoch !== this.epoch || await observer.evaluate(state => state.changed))
        throw new RuntimeError("STALE_REF", "Page changed while capturing refs; refresh the snapshot");
      const output: string[] = [];
      const retained = new Set<NodeHandle>();
      for (let i = 0; i < lines.length; i++) {
        const item = parsed[i];
        if (interactive && (!item || !INTERACTIVE.has(item.role))) continue;
        const handle = item ? groups.get(item.key)?.shift() : undefined;
        if (!handle) { output.push(lines[i]); continue; }
        const ref = `e${++this.counter}`;
        this.entries.set(ref, handle); retained.add(handle);
        output.push(`${lines[i].trimEnd()} [ref=${ref}]`);
      }
      await Promise.all(acquired.filter(h => !retained.has(h)).map(h => h.dispose().catch(() => {})));
      if (epoch !== this.epoch || await observer.evaluate(state => state.changed))
        throw new RuntimeError("STALE_REF", "Page changed while capturing refs; refresh the snapshot");
      this.page = page;
      this.snapshotId = randomUUID();
      return output.join("\n");
    } catch (error) {
      this.invalidate();
      await Promise.all(acquired.map(h => h.dispose().catch(() => {})));
      throw error;
    } finally {
      await observer.evaluate(state => state.observer.disconnect()).catch(() => {});
      await observer.dispose().catch(() => {});
      await root.dispose().catch(() => {});
    }
  }

  async resolve(ref: string, page: Page): Promise<NodeHandle> {
    const handle = this.entries.get(ref.replace(/^@/, ""));
    if (!handle || page !== this.page || page.isClosed() || !await handle.evaluate(node => node.isConnected).catch(() => false))
      throw new RuntimeError("STALE_REF", "Ref is missing or detached; run snapshot again before acting");
    return handle;
  }
  invalidate(): void {
    this.epoch++;
    for (const handle of this.entries.values()) void handle.dispose().catch(() => {});
    this.entries.clear(); this.page = undefined; this.snapshotId = undefined;
  }
  get size(): number { return this.entries.size; }
}
