import { linkSync, writeFileSync, readFileSync, renameSync, unlinkSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { PlatformError } from './backend.mjs';

export function processIdentity(pid) {
  if (!Number.isSafeInteger(pid) || pid < 1) return null;
  try {
    process.kill(pid, 0);
    if (process.platform === 'linux') {
      const stat = readFileSync(`/proc/${pid}/stat`, 'utf8');
      const fields = stat.slice(stat.lastIndexOf(')') + 2).split(' ');
      return ['Z', 'X'].includes(fields[0]) ? null : fields[19];
    }
    return 'alive';
  } catch (error) { return error.code === 'ESRCH' || error.code === 'ENOENT' ? null : 'unknown'; }
}

export function writeJob(path, value) {
  const temporary = path + '.' + randomUUID() + '.tmp';
  try { writeFileSync(temporary, JSON.stringify(value) + '\n', { mode: 0o600 }); renameSync(temporary, path); }
  finally { try { unlinkSync(temporary); } catch (error) { if (error.code !== 'ENOENT') throw error; } }
}

function ownerLost(owner) {
  const current = processIdentity(owner?.pid);
  return current === null || current !== 'unknown' && owner?.process_identity && current !== owner.process_identity;
}

// QR execution owns a separate job, leaving admission free for confirmation.
export async function withLoginLock(path, callback) {
  const owner = { pid: process.pid, process_identity: processIdentity(process.pid), nonce: randomUUID() };
  const recover = path + '.recover';
  const readOwner = file => { try { return JSON.parse(readFileSync(file, 'utf8')); } catch { return null; } };
  const abandoned = file => {
    const previous = readOwner(file);
    return previous ? ownerLost(previous) : false;
  };
  const create = file => {
    // Publish a complete owner record atomically. An empty, half-written lock
    // must not be mistaken for an abandoned process by another caller.
    const temporary = file + '.' + randomUUID() + '.tmp';
    try {
      writeFileSync(temporary, JSON.stringify(owner), { flag: 'wx', mode: 0o600 });
      linkSync(temporary, file);
    } finally { try { unlinkSync(temporary); } catch (error) { if (error.code !== 'ENOENT') throw error; } }
  };
  try { create(path); }
  catch (error) {
    if (error.code !== 'EEXIST') throw error;
    if (abandoned(recover)) { try { unlinkSync(recover); } catch (error) { if (error.code !== 'ENOENT') throw error; } }
    let guard = false;
    try {
      create(recover); guard = true;
      if (!abandoned(path)) throw new PlatformError('BUSY', '该账号已有登录操作正在执行');
      unlinkSync(path);
      create(path);
    } catch (error) {
      if (error.code === 'EEXIST') throw new PlatformError('BUSY', '该账号登录状态正在恢复');
      throw error;
    } finally {
      if (guard && readOwner(recover)?.nonce === owner.nonce) unlinkSync(recover);
    }
  }
  try { return await callback(); }
  finally { if (readOwner(path)?.nonce === owner.nonce) unlinkSync(path); }
}

export function jobLiveness(pointer, job, now = Date.now()) {
  const identity = processIdentity(pointer.pid);
  if (identity === null || identity !== 'unknown' && pointer.process_identity && identity !== pointer.process_identity) return 'worker_lost';
  if (!pointer.job_id) return 'unmanaged';
  if (identity === 'unknown' || !job || job.job_id !== pointer.job_id || !Number.isFinite(job.heartbeat_at) ||
      now - job.heartbeat_at > 10000 || job.heartbeat_at > now + 10000) return 'worker_unresponsive';
  return 'alive';
}
