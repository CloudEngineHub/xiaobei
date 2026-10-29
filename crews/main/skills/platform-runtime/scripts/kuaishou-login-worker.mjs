import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { runBackend } from './backend.mjs';
import { writeJob, processIdentity } from './login-job.mjs';

// The invoking CLI remains owned by OpenClaw exec background; no detachment.
export async function runKuaishouLoginWorker(pointer, { timeout = 600000, heartbeatMs = 500 } = {}) {
  const { account, home, job_id } = pointer;
  const controller = new AbortController();
  const jobPath = join(home, 'job.json');
  const qrPath = join(home, 'cache/kuaishou/qrcode.png');
  const job = { job_id, account, pid: process.pid, state: 'starting', heartbeat_at: Date.now(),
    deadline_at: pointer.started_at + timeout, qr_expires_at: null, exit_reason: null };
  let abortReason;
  let announced = false;
  const abort = reason => { abortReason ||= reason; controller.abort(); };
  const terminated = () => abort('SIGTERM');
  const interrupted = () => abort('SIGINT');
  process.once('SIGTERM', terminated); process.once('SIGINT', interrupted);
  const heartbeat = () => {
    let qr;
    try { qr = JSON.parse(readFileSync(join(home, 'qr-state.json'), 'utf8')); } catch { /* QR not issued yet */ }
    job.heartbeat_at = Date.now();
    if (qr?.state === 'expired' || qr?.state === 'cancelled') {
      job.state = qr.state;
      abort(qr.state === 'expired' ? 'LOGIN_QR_EXPIRED' : 'LOGIN_CANCELLED');
      writeJob(jobPath, job);
      return;
    }
    if (existsSync(qrPath)) {
      job.state = qr?.state === 'accepted' ? 'completing' : qr?.state === 'scanned' ? 'awaiting_phone_confirmation' : 'awaiting_scan';
      if (!announced && job.state !== 'completing') {
        announced = true;
        process.stderr.write(JSON.stringify({ ok: true, platform: 'kuaishou', account, job_id,
          state: job.state, qr_path: qrPath, qr_expires_at: null,
          message: '扫码任务由当前 exec 后台进程持有；交用户扫码后调用 login-confirm' }) + '\n');
      }
    }
    writeJob(jobPath, job);
  };
  heartbeat();
  const timer = setInterval(heartbeat, heartbeatMs);
  let result;
  try {
    result = await runBackend('kuaishou', ['auth', 'login', '--method', 'qrcode', '--account', account],
      { home, timeout, signal: controller.signal, loginJob: job_id,
        onSpawn: pid => { job.backend_pid = pid; job.backend_identity = processIdentity(pid); writeJob(jobPath, job); } });
    job.state = 'succeeded';
    job.exit_reason = 'completed';
  } catch (error) {
    job.state = abortReason === 'LOGIN_QR_EXPIRED' || error.code === 'TIMEOUT' ? 'expired' :
      ['SIGTERM', 'SIGINT', 'LOGIN_CANCELLED'].includes(abortReason) ? 'cancelled' : 'failed';
    job.exit_reason = abortReason || error.code || 'ERROR';
    result = { ok: false, error: job.exit_reason };
  } finally {
    clearInterval(timer);
    process.removeListener('SIGTERM', terminated); process.removeListener('SIGINT', interrupted);
  }
  job.heartbeat_at = Date.now();
  writeJob(jobPath, job);
  // Final write: confirmation may adopt and remove home immediately afterwards.
  writeJob(join(home, 'result.json'), result);
  return result;
}
