const ALIPAY_GATEWAY = 'https://openapi.alipay.com/gateway.do';
const TEXT_ENCODER = new TextEncoder();

export function constantTimeEqual(left, right) {
  const a = TEXT_ENCODER.encode(left);
  const b = TEXT_ENCODER.encode(right);
  const length = Math.max(a.length, b.length);
  let difference = a.length ^ b.length;
  for (let index = 0; index < length; index += 1) difference |= (a[index] || 0) ^ (b[index] || 0);
  return difference === 0;
}

export function canonicalize(entries, { excludeSignType = false } = {}) {
  return [...entries]
    .filter(([key, value]) => key !== 'sign' && (!excludeSignType || key !== 'sign_type') && value !== '')
    .sort(([left], [right]) => (left < right ? -1 : left > right ? 1 : 0))
    .map(([key, value]) => `${key}=${value}`)
    .join('&');
}

function pemBytes(pem) {
  const base64 = pem.replace(/-----BEGIN [^-]+-----|-----END [^-]+-----|\s/g, '');
  return Uint8Array.from(atob(base64), (character) => character.charCodeAt(0));
}

async function privateKey(pem) {
  return crypto.subtle.importKey(
    'pkcs8', pemBytes(pem), { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['sign'],
  );
}

async function publicKey(pem) {
  return crypto.subtle.importKey(
    'spki', pemBytes(pem), { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['verify'],
  );
}

export async function signParameters(parameters, privateKeyPem, options = {}) {
  const signature = await crypto.subtle.sign(
    'RSASSA-PKCS1-v1_5', await privateKey(privateKeyPem), TEXT_ENCODER.encode(canonicalize(parameters.entries(), options)),
  );
  return btoa(String.fromCharCode(...new Uint8Array(signature)));
}

export async function verifyParameters(parameters, signature, publicKeyPem) {
  const bytes = Uint8Array.from(atob(signature), (character) => character.charCodeAt(0));
  return crypto.subtle.verify(
    'RSASSA-PKCS1-v1_5', await publicKey(publicKeyPem), bytes,
    TEXT_ENCODER.encode(canonicalize(parameters.entries(), { excludeSignType: true })),
  );
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
  });
}

function configured(env) {
  return Boolean(
    env.PAYMENT_GATEWAY_TOKEN && env.ALIPAY_APP_ID && env.ALIPAY_PRIVATE_KEY
    && env.ALIPAY_PUBLIC_KEY && env.ALIPAY_SELLER_ID,
  );
}

function cents(amount) {
  if (!/^\d+(?:\.\d{1,2})?$/.test(amount)) throw new Error('invalid amount');
  const [whole, decimal = ''] = amount.split('.');
  return Number(whole) * 100 + Number(decimal.padEnd(2, '0'));
}

export function alipayTimestamp(date = new Date()) {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
  }).formatToParts(date).filter((part) => part.type !== 'literal').map((part) => [part.type, part.value]));
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second}`;
}

async function createCheckout(payload, env) {
  const scene = payload.scene === 'mobile' ? 'mobile' : payload.scene === 'desktop' ? 'desktop' : '';
  let notifyUrl;
  let returnUrl;
  try {
    notifyUrl = new URL(payload.notify_url);
    returnUrl = new URL(payload.return_url);
  } catch {
    return json({ error: 'invalid callback url' }, 400);
  }
  if (!/^[a-zA-Z0-9-]{1,64}$/.test(payload.order_id || '')
      || !Number.isInteger(payload.amount_fen) || payload.amount_fen <= 0 || !scene
      || notifyUrl.protocol !== 'https:' || returnUrl.protocol !== 'https:') {
    return json({ error: 'invalid order' }, 400);
  }
  const providerOrderId = `IS${payload.order_id.replaceAll('-', '')}`;
  const mobile = scene === 'mobile';
  const parameters = new URLSearchParams({
    app_id: env.ALIPAY_APP_ID,
    method: mobile ? 'alipay.trade.wap.pay' : 'alipay.trade.page.pay',
    format: 'JSON',
    charset: 'utf-8',
    sign_type: 'RSA2',
    timestamp: alipayTimestamp(),
    version: '1.0',
    notify_url: notifyUrl.toString(),
    return_url: returnUrl.toString(),
    biz_content: JSON.stringify({
      out_trade_no: providerOrderId,
      total_amount: (payload.amount_fen / 100).toFixed(2),
      subject: String(payload.subject || 'Idea Spark 创作额度').slice(0, 256),
      product_code: mobile ? 'QUICK_WAP_WAY' : 'FAST_INSTANT_TRADE_PAY',
      timeout_express: '15m',
    }),
  });
  parameters.set('sign', await signParameters(parameters, env.ALIPAY_PRIVATE_KEY));
  return json({ provider_order_id: providerOrderId, pay_url: `${ALIPAY_GATEWAY}?${parameters}` });
}

async function verifyNotification(payload, env) {
  const parameters = new URLSearchParams(payload.body || '');
  const signature = parameters.get('sign') || '';
  if (!signature || !(await verifyParameters(parameters, signature, env.ALIPAY_PUBLIC_KEY))) {
    return json({ error: 'invalid signature' }, 400);
  }
  if (parameters.get('app_id') !== env.ALIPAY_APP_ID) return json({ error: 'app id mismatch' }, 400);
  if (env.ALIPAY_SELLER_ID && parameters.get('seller_id') !== env.ALIPAY_SELLER_ID) {
    return json({ error: 'seller id mismatch' }, 400);
  }
  const status = parameters.get('trade_status') || '';
  if (!['TRADE_SUCCESS', 'TRADE_FINISHED'].includes(status)) return json({ error: 'trade not paid' }, 400);
  const bodyBytes = TEXT_ENCODER.encode(payload.body || '');
  const digest = await crypto.subtle.digest('SHA-256', bodyBytes);
  return json({
    event_key: `${parameters.get('trade_no')}:${status}`,
    event_type: status,
    provider_order_id: parameters.get('out_trade_no'),
    provider_trade_id: parameters.get('trade_no'),
    amount_fen: cents(parameters.get('total_amount') || ''),
    payload_digest: [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join(''),
  });
}

async function alipayApi(method, bizContent, responseKey, env) {
  const parameters = new URLSearchParams({
    app_id: env.ALIPAY_APP_ID,
    method,
    format: 'JSON',
    charset: 'utf-8',
    sign_type: 'RSA2',
    timestamp: alipayTimestamp(),
    version: '1.0',
    biz_content: JSON.stringify(bizContent),
  });
  parameters.set('sign', await signParameters(parameters, env.ALIPAY_PRIVATE_KEY));
  const response = await fetch(ALIPAY_GATEWAY, {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded;charset=utf-8' },
    body: parameters.toString(),
  });
  if (!response.ok) throw new Error('alipay unavailable');
  const result = (await response.json())[responseKey];
  if (!result || result.code !== '10000') throw new Error(`alipay rejected request (${result?.sub_code || result?.code || 'invalid'})`);
  return result;
}

async function queryTrade(payload, env) {
  if (!/^[a-zA-Z0-9-]{1,64}$/.test(payload.provider_order_id || '')) {
    return json({ error: 'invalid provider order id' }, 400);
  }
  try {
    const result = await alipayApi(
      'alipay.trade.query',
      { out_trade_no: payload.provider_order_id },
      'alipay_trade_query_response',
      env,
    );
    const statuses = {
      WAIT_BUYER_PAY: 'pending', TRADE_SUCCESS: 'paid', TRADE_FINISHED: 'paid', TRADE_CLOSED: 'closed',
    };
    return json({
      provider_order_id: result.out_trade_no,
      provider_trade_id: result.trade_no || '',
      status: statuses[result.trade_status] || 'unknown',
      amount_fen: cents(result.total_amount || ''),
    });
  } catch (error) {
    return json({ error: String(error.message || error) }, 502);
  }
}

async function refundTrade(payload, env) {
  if (!/^[a-zA-Z0-9-]{1,64}$/.test(payload.provider_order_id || '')
      || !/^[a-zA-Z0-9-]{1,64}$/.test(payload.refund_request_id || '')
      || !Number.isInteger(payload.amount_fen) || payload.amount_fen <= 0) {
    return json({ error: 'invalid refund' }, 400);
  }
  try {
    const result = await alipayApi(
      'alipay.trade.refund',
      {
        out_trade_no: payload.provider_order_id,
        refund_amount: (payload.amount_fen / 100).toFixed(2),
        out_request_no: payload.refund_request_id,
      },
      'alipay_trade_refund_response',
      env,
    );
    const amountFen = cents(result.refund_fee || '');
    if (result.out_trade_no !== payload.provider_order_id || amountFen !== payload.amount_fen) {
      return json({ error: 'refund response mismatch' }, 502);
    }
    return json({
      provider_order_id: result.out_trade_no,
      provider_trade_id: result.trade_no || '',
      refund_request_id: payload.refund_request_id,
      amount_fen: amountFen,
    });
  } catch (error) {
    return json({ error: String(error.message || error) }, 502);
  }
}

export default {
  async fetch(request, env) {
    if (!configured(env)) return json({ error: 'gateway not configured' }, 503);
    const expected = `Bearer ${env.PAYMENT_GATEWAY_TOKEN}`;
    if (!constantTimeEqual(request.headers.get('authorization') || '', expected)) return json({ error: 'unauthorized' }, 401);
    if (request.method !== 'POST') return json({ error: 'method not allowed' }, 405);
    let payload;
    try { payload = await request.json(); } catch { return json({ error: 'invalid json' }, 400); }
    const path = new URL(request.url).pathname;
    if (path === '/checkout') return createCheckout(payload, env);
    if (path === '/verify') return verifyNotification(payload, env);
    if (path === '/query') return queryTrade(payload, env);
    if (path === '/refund') return refundTrade(payload, env);
    return json({ error: 'not found' }, 404);
  },
};
