import { resolveTimerTimeoutMs } from "openclaw/plugin-sdk/number-runtime";
import { raceWithTimeout } from "openclaw/plugin-sdk/time-runtime";

/** Match bundled Feishu: timed-out turns keep running but cannot block a chat forever. */
export function createAwadaSequentialQueue(
  options: {
    taskTimeoutMs?: number;
    onTaskTimeout?: (key: string, timeoutMs: number) => void;
  } = {},
) {
  const queues = new Map<string, Promise<void>>();
  const timeoutMs = options.taskTimeoutMs ?? 5 * 60 * 1000;
  return (key: string, task: () => Promise<void>): Promise<void> => {
    const wrapped = async () => {
      if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) return task();
      const resolved = resolveTimerTimeoutMs(timeoutMs, 5 * 60 * 1000);
      await raceWithTimeout(task, resolved, () => {
        try {
          options.onTaskTimeout?.(key, resolved);
        } catch {}
      });
    };
    const next = (queues.get(key) ?? Promise.resolve()).then(wrapped, wrapped);
    queues.set(key, next);
    const cleanup = () => {
      if (queues.get(key) === next) queues.delete(key);
    };
    next.then(cleanup, cleanup);
    return next;
  };
}
