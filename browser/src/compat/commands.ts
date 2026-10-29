// Command syntax retained from the WiseFlow camoufox-cli fork. See LICENSE.
function require_(args: string[], idx: number, usage: string): string {
  if (idx >= args.length) {
    throw new Error(usage);
  }
  return args[idx];
}

export function buildCommand(action: string, rest: string[]): Record<string, unknown> {
  switch (action) {
    case "open":
      return { id: "r1", action: "open", params: { url: require_(rest, 1, "Usage: camoufox-cli open <url>") } };
    case "back":
      return { id: "r1", action: "back", params: {} };
    case "forward":
      return { id: "r1", action: "forward", params: {} };
    case "reload":
      return { id: "r1", action: "reload", params: {} };
    case "url":
      return { id: "r1", action: "url", params: {} };
    case "title":
      return { id: "r1", action: "title", params: {} };
    case "close":
      return { id: "r1", action: "close", params: { all: rest.includes("--all") } };

    case "snapshot": {
      const interactive = rest.includes("-i");
      let selector: string | undefined;
      const sIdx = rest.indexOf("-s");
      if (sIdx >= 0) selector = require_(rest, sIdx + 1, "Usage: camoufox-cli snapshot -s <selector>");
      const params: Record<string, unknown> = { interactive };
      if (selector) params.selector = selector;
      return { id: "r1", action: "snapshot", params };
    }

    case "click":
      return { id: "r1", action: "click", params: { ref: require_(rest, 1, "Usage: camoufox-cli click @e1") } };
    case "fill":
      return { id: "r1", action: "fill", params: { ref: require_(rest, 1, 'Usage: camoufox-cli fill @e1 "text"'), text: require_(rest, 2, 'Usage: camoufox-cli fill @e1 "text"') } };
    case "type":
      return { id: "r1", action: "type", params: { ref: require_(rest, 1, 'Usage: camoufox-cli type @e1 "text"'), text: require_(rest, 2, 'Usage: camoufox-cli type @e1 "text"') } };
    case "select":
      return { id: "r1", action: "select", params: { ref: require_(rest, 1, 'Usage: camoufox-cli select @e1 "option"'), value: require_(rest, 2, 'Usage: camoufox-cli select @e1 "option"') } };
    case "check":
      return { id: "r1", action: "check", params: { ref: require_(rest, 1, "Usage: camoufox-cli check @e1") } };
    case "hover":
      return { id: "r1", action: "hover", params: { ref: require_(rest, 1, "Usage: camoufox-cli hover @e1") } };
    case "press":
      return { id: "r1", action: "press", params: { key: require_(rest, 1, "Usage: camoufox-cli press Enter") } };

    case "text":
      return { id: "r1", action: "text", params: { target: require_(rest, 1, "Usage: camoufox-cli text @e1") } };
    case "eval":
      return { id: "r1", action: "eval", params: { expression: require_(rest, 1, 'Usage: camoufox-cli eval "document.title"') } };
    case "screenshot": {
      const params: Record<string, unknown> = {};
      for (const arg of rest.slice(1)) {
        if (arg === "--full") params.full_page = true;
        else params.path = arg;
      }
      return { id: "r1", action: "screenshot", params };
    }
    case "pdf":
      return { id: "r1", action: "pdf", params: { path: require_(rest, 1, "Usage: camoufox-cli pdf output.pdf") } };

    case "scroll":
      return { id: "r1", action: "scroll", params: { direction: require_(rest, 1, "Usage: camoufox-cli scroll down [px]"), amount: rest.length > 2 ? parseInt(rest[2], 10) : 500 } };
    case "wait": {
      const target = require_(rest, 1, 'Usage: camoufox-cli wait @e1 | camoufox-cli wait 2000 | camoufox-cli wait --url "pattern"');
      if (target === "--url") return { id: "r1", action: "wait", params: { url: require_(rest, 2, 'Usage: camoufox-cli wait --url "*/dashboard"') } };
      if (target.startsWith("@")) return { id: "r1", action: "wait", params: { ref: target } };
      if (/^\d/.test(target)) return { id: "r1", action: "wait", params: { ms: parseInt(target, 10) } };
      return { id: "r1", action: "wait", params: { selector: target } };
    }

    case "tabs":
      return { id: "r1", action: "tabs", params: {} };
    case "switch": {
      if (rest[1] === "--tab") return { id: "r1", action: "switch", params: { tabId: require_(rest, 2, "Usage: switch --tab <tabId>") } };
      const value = require_(rest, 1, "Usage: camoufox-cli switch <tab-index>");
      if (!/^\d+$/.test(value) || !Number.isSafeInteger(Number(value))) throw new Error("Tab index must be a non-negative integer");
      return { id: "r1", action: "switch", params: { index: Number(value) } };
    }
    case "close-tab":
      if (rest[1] === "--tab") return { id: "r1", action: "close-tab", params: { tabId: require_(rest, 2, "Usage: close-tab --tab <tabId>") } };
      return { id: "r1", action: "close-tab", params: {} };

    case "sessions":
      return { id: "r1", action: "sessions", params: {} };
    case "info":
      return { id: "r1", action: "info", params: {} };
    case "install":
      return { id: "r1", action: "install", params: { with_deps: rest.includes("--with-deps") } };
    case "cookies": {
      if (rest.length > 1 && rest[1] === "import")
        return { id: "r1", action: "cookies", params: { op: "import", path: require_(rest, 2, "Usage: camoufox-cli cookies import file.json") } };
      if (rest.length > 1 && rest[1] === "export")
        return { id: "r1", action: "cookies", params: { op: "export", path: require_(rest, 2, "Usage: camoufox-cli cookies export file.json") } };
      return { id: "r1", action: "cookies", params: { op: "list" } };
    }
    case "identity": {
      if (rest.length > 1 && rest[1] === "export")
        return { id: "r1", action: "identity", params: { op: "export", path: require_(rest, 2, "Usage: camoufox-cli identity export file.json") } };
      return { id: "r1", action: "identity", params: { op: "show" } };
    }
    case "upload": {
      const target = require_(rest, 1, "Usage: camoufox-cli upload @ref|selector <file> [more files...]");
      const paths = rest.slice(2);
      if (paths.length === 0) {
        throw new Error("Usage: upload @ref|selector <file> [more files...]");
      }
      const params: Record<string, unknown> = { paths };
      if (target.startsWith("@")) params.ref = target;
      else params.selector = target;
      return { id: "r1", action: "upload", params };
    }

    default:
      throw new Error(`Unknown command: ${action}`);
  }
}
