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

export function extractSignedResponse(text, field) {
  const marker = `"${field}"`;
  const markerIndex = text.indexOf(marker);
  if (markerIndex < 0) return '';
  const start = text.indexOf('{', markerIndex + marker.length);
  if (start < 0) return '';
  let depth = 0;
  let inString = false;
  let escaped = false;
  for (let index = start; index < text.length; index += 1) {
    const character = text[index];
    if (inString) {
      if (escaped) escaped = false;
      else if (character === '\\') escaped = true;
      else if (character === '"') inString = false;
      continue;
    }
    if (character === '"') inString = true;
    else if (character === '{') depth += 1;
    else if (character === '}' && --depth === 0) return text.slice(start, index + 1);
  }
  return '';
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
  if (!payload.order_id || !Number.isInteger(payload.amount_fen) || payload.amount_fen <= 0) {
    return json({ error: 'invalid order' }, 400);
  }
  const providerOrderId = `IS${payload.order_id.replaceAll('-', '')}`;
  const parameters = new URLSearchParams({
    app_id: env.ALIPAY_APP_ID,
    method: 'alipay.trade.precreate',
    format: 'JSON',
    charset: 'utf-8',
    sign_type: 'RSA2',
    timestamp: alipayTimestamp(),
    version: '1.0',
    notify_url: payload.notify_url,
    biz_content: JSON.stringify({
      out_trade_no: providerOrderId,
      total_amount: (payload.amount_fen / 100).toFixed(2),
      subject: String(payload.subject || 'Idea Spark 创作额度').slice(0, 256),
      timeout_express: '15m',
    }),
  });
  parameters.set('sign', await signParameters(parameters, env.ALIPAY_PRIVATE_KEY));
  const response = await fetch(ALIPAY_GATEWAY, {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded;charset=utf-8' },
    body: parameters,
  });
  const responseText = await response.text();
  let result;
  try { result = JSON.parse(responseText); } catch { return json({ error: 'invalid alipay response' }, 502); }
  const trade = result.alipay_trade_precreate_response;
  const responseSignature = result.sign || '';
  const signedPayload = extractSignedResponse(responseText, 'alipay_trade_precreate_response');
  const signatureValid = signedPayload && responseSignature && await crypto.subtle.verify(
    'RSASSA-PKCS1-v1_5', await publicKey(env.ALIPAY_PUBLIC_KEY),
    Uint8Array.from(atob(responseSignature), (character) => character.charCodeAt(0)), TEXT_ENCODER.encode(signedPayload),
  );
  if (!signatureValid) {
    console.error(JSON.stringify({ event: 'alipay_response_signature_invalid' }));
    return json({ error: 'invalid alipay response signature' }, 502);
  }
  if (!response.ok || trade?.code !== '10000' || !trade.qr_code) {
    console.error(JSON.stringify({ event: 'alipay_precreate_failed', code: trade?.code, sub_code: trade?.sub_code }));
    return json({ error: 'alipay precreate failed' }, 502);
  }
  return json({ provider_order_id: providerOrderId, pay_url: trade.qr_code });
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
    return json({ error: 'not found' }, 404);
  },
};
