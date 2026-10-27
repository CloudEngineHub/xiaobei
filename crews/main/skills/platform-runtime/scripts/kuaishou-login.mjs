import { randomUUID } from 'node:crypto';
import { mkdir, mkdtemp, readFile, stat, writeFile, rm } from 'node:fs/promises';
import { join, resolve, dirname } from 'node:path';
import { stateHome, activeAccount, credential, credentialPath, atomicJson, runBackend, PlatformError } from './backend.mjs';
import { processIdentity, jobLiveness, withLoginLock, writeJob } from './login-job.mjs';
import { runKuaishouLoginWorker } from './kuaishou-login-worker.mjs';

function option(args, flag, fallback) {
  const matches = args.flatMap((arg, index) => arg === flag || arg.startsWith(flag + '=') ? [index] : []);
  if (matches.length > 1) throw new PlatformError('USAGE', '不要重复指定 ' + flag);
  const index = matches[0];
  if (index === undefined) return fallback;
  if (args[index].startsWith(flag + '=')) {
    const value = args[index].slice(flag.length + 1);
    if (!value) throw new PlatformError('USAGE', flag + ' 缺少值');
    args.splice(index, 1); return value;
  }
  const value = args[index + 1];
  if (!value || value.startsWith('-')) throw new PlatformError('USAGE', flag + ' 缺少值');
  args.splice(index, 2); return value;
}
async function adopt(account, home) {
  const saved = await credential('kuaishou', account, home);
  const check = await runBackend('kuaishou', ['auth', 'status', '--account', account], { home });
  if (!check.data?.logged_in || !check.data.user?.id) throw new PlatformError('AUTH_REQUIRED', '新会话未通过在线身份校验，旧会话保留', 2);
  if (saved.user?.id !== check.data.user.id) throw new PlatformError('ACCOUNT_MISMATCH', '登录结果与在线用户不一致');
  let old;
  try { old = await credential('kuaishou', account); } catch (error) { if (error.code !== 'AUTH_REQUIRED') throw error; }
  if (old?.user?.id && old.user.id !== saved.user.id) throw new PlatformError('ACCOUNT_MISMATCH', '当前 alias 属于其他账号，请用新 alias 登录');
  await atomicJson(credentialPath('kuaishou', account), saved);
  const current = join(stateHome, 'auth/kuaishou/web/_current');
  try { await writeFile(current, account + '\n', { flag: 'wx', mode: 0o600 }); } catch (error) { if (error.code !== 'EEXIST') throw error; }
  await rm(home, { force: true, recursive: true });
  return { ok: true, platform: 'kuaishou', account, user: saved.user };
}
async function performLogin(action, input) {
  const args = [...input];
  const account = await activeAccount('kuaishou', option(args, '--account', option(args, '-a', undefined)));
  const method = option(args, '--method', 'qrcode');
  const phone = option(args, '--phone'), code = option(args, '--code');
  if (args.length) throw new PlatformError('USAGE', '存在未知登录参数');
  const root = join(stateHome, 'pending', 'kuaishou', account);
  await mkdir(root, { recursive: true, mode: 0o700 });
  if (method === 'sms') {
    const home = join(root, 'sms');
    if (action === 'login' && (!phone || code)) throw new PlatformError('USAGE', '短信 login 必须传 --phone；确认验证码使用 login-confirm --code');
    if (action === 'login-confirm' && (!code || phone)) throw new PlatformError('USAGE', '短信 login-confirm 必须传 --code，不重复请求短信');
    if (action === 'login-confirm' && !(await stat(home).catch(() => null))) throw new PlatformError('LOGIN_NOT_STARTED', '先用 login --method sms --phone 请求验证码');
    if (action === 'login') await rm(home, { recursive: true, force: true });
    const result = await runBackend('kuaishou', ['auth', 'login', '--method', 'sms', '--account', account, ...(phone ? ['--phone', phone] : ['--code', code])], { home });
    return action === 'login' ? result : adopt(account, home);
  }
  if (method !== 'qrcode') throw new PlatformError('USAGE', '快手登录使用 qrcode 或 sms');
  if (phone || code) throw new PlatformError('USAGE', '扫码登录不接受手机号或验证码');
  const pointer = join(root, 'current.json');
  let previous;
  try { previous = JSON.parse(await readFile(pointer, 'utf8')); } catch (error) { if (error.code !== 'ENOENT') throw error; }
  if (previous && (typeof previous.home !== 'string' || dirname(resolve(previous.home)) !== resolve(root)))
    throw new PlatformError('LOGIN_STATE_INVALID', '登录任务目录与当前账号不一致，保留状态供核查');
  let result, job;
  if (previous) {
    try { result = JSON.parse(await readFile(join(previous.home, 'result.json'), 'utf8')); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
    try { job = JSON.parse(await readFile(join(previous.home, 'job.json'), 'utf8')); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  const liveness = previous ? jobLiveness(previous, job) : null;
  if (action === 'login-confirm') {
    if (!previous) throw new PlatformError('LOGIN_NOT_STARTED', '先运行 kuaishou-hunter login');
    if (!result) {
      if (liveness !== 'alive') {
        if (liveness === 'worker_lost' && job) writeJob(join(previous.home, 'job.json'),
          { ...job, state: 'worker_lost', exit_reason: 'owner_lost', observed_at: Date.now() });
        throw new PlatformError(liveness === 'worker_lost' ? 'LOGIN_WORKER_LOST' : 'LOGIN_WORKER_UNRESPONSIVE',
          '扫码任务无有效执行进程或心跳；先核对原生后台任务，勿继续使用旧二维码', 2);
      }
      if (['expired', 'cancelled', 'failed'].includes(job.state)) throw new PlatformError(job.exit_reason ||
        (job.state === 'expired' ? 'LOGIN_QR_EXPIRED' : job.state === 'cancelled' ? 'LOGIN_CANCELLED' : 'LOGIN_FAILED'),
        '扫码任务已停止，等待原后台进程结束后重新 login', 2);
      const qrPath = join(previous.home, 'cache/kuaishou/qrcode.png');
      const qrExists = ['awaiting_scan', 'awaiting_phone_confirmation'].includes(job.state) && !!(await stat(qrPath).catch(() => null));
      return { ok: true, platform: 'kuaishou', account, job_id: previous.job_id,
        state: job.state, awaiting_scan: qrExists && job.state === 'awaiting_scan',
        awaiting_qr: job.state === 'starting', ...(qrExists ? { qr_path: qrPath } : {}),
        heartbeat_at: job.heartbeat_at, deadline_at: job.deadline_at, qr_expires_at: job.qr_expires_at };
    }
    if (!result.ok) throw new PlatformError(result.error || 'LOGIN_FAILED', '快手扫码任务已结束；重新 login 可创建新任务', 2);
    const imported = await adopt(account, previous.home);
    await rm(pointer, { force: true });
    return imported;
  }
  if (result?.ok) throw new PlatformError('LOGIN_CONFIRM_REQUIRED', '扫码任务已完成；使用 login-confirm 验证并保存会话，不重新扫码');
  if (previous && !result && liveness === 'worker_lost' && job?.backend_pid && processIdentity(job.backend_pid) !== null)
    throw new PlatformError('LOGIN_BACKEND_STILL_RUNNING', '登录 owner 已丢失，原平台进程尚未退出；等待其退出后再 login', 2);
  if (previous && !result && liveness !== 'worker_lost') throw new PlatformError('BUSY',
    liveness === 'alive' ? '该账号已有受管扫码任务；使用 login-confirm 查看状态' : '原登录进程仍存活但心跳异常；先结束其原生后台任务');
  if (previous) await rm(previous.home, { force: true, recursive: true });
  const home = await mkdtemp(join(root, 'qr-'));
  const pending = { home, account, started_at: Date.now(), pid: process.pid,
    process_identity: processIdentity(process.pid), job_id: randomUUID() };
  writeJob(join(home, 'job.json'), { job_id: pending.job_id, state: 'starting', heartbeat_at: Date.now() });
  await atomicJson(pointer, pending);
  return { run_job: pending };
}
export async function kuaishouLogin(action, args) {
  const root = join(stateHome, 'locks');
  await mkdir(root, { recursive: true, mode: 0o700 });
  const copy = [...args];
  const account = await activeAccount('kuaishou', option(copy, '--account', option(copy, '-a', undefined)));
  const result = await withLoginLock(join(root, `login-kuaishou-${account}.lock`), () => performLogin(action, args));
  if (!result.run_job) return result;
  const finished = await runKuaishouLoginWorker(result.run_job);
  if (!finished.ok) throw new PlatformError(finished.error || 'LOGIN_FAILED', '扫码任务已结束；检查原因后重新发起登录', 2);
  return { ok: true, platform: 'kuaishou', account, job_id: result.run_job.job_id,
    state: 'succeeded', awaiting_confirmation: true, message: '使用 login-confirm 校验并保存会话' };
}
