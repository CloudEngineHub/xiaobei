import { join } from 'node:path';
import { writeJob } from './login-job.mjs';

// Observe only QR state, never persist QR tokens or raw response bodies.
export function qrObserver(home, parseJson, ErrorType) {
  let issued = false;
  const pathOf = input => {
    const url = new URL(input.url);
    return ['id.kuaishou.com', 'passport.kuaishou.com'].includes(url.hostname) ? url.pathname : '';
  };
  return {
    policy(input) {
      if (pathOf(input) === '/rest/c/infra/ks/qr/start') {
        if (issued) throw new ErrorType('AUTH_EXPIRED', '二维码已过期，需用户重新发起登录');
        issued = true;
      }
      return input;
    },
    async response(input, response) {
      const path = pathOf(input);
      if (!/^\/rest\/c\/infra\/ks\/qr\/(start|scanResult|acceptResult)$/.test(path)) return;
      let body;
      try { body = await parseJson(response.clone()); } catch { return; }
      const state = body?.result === 707 ? 'expired' : [711, 712].includes(body?.result) ? 'cancelled' :
        body?.result === 1 ? path.endsWith('/start') ? 'issued' : path.endsWith('/scanResult') ? 'scanned' : 'accepted' : null;
      if (state) writeJob(join(home, 'qr-state.json'), { state, observed_at: Date.now(), qr_expires_at: null });
      if (state === 'expired' || state === 'cancelled') throw new ErrorType('AUTH_EXPIRED', '二维码已过期或用户已取消登录');
    },
  };
}
