import assert from 'node:assert/strict';
import { generateKeyPairSync } from 'node:crypto';
import test from 'node:test';

import worker, { alipayTimestamp, canonicalize, signParameters, verifyParameters } from './index.js';

const { privateKey, publicKey } = generateKeyPairSync('rsa', {
  modulusLength: 2048,
  publicKeyEncoding: { type: 'spki', format: 'pem' },
  privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
});

test('request signing includes sign_type while notification verification excludes it', () => {
  const parameters = new URLSearchParams({ z: 'last', sign: 'secret', sign_type: 'RSA2', a: 'first', blank: '' });
  assert.equal(canonicalize(parameters.entries()), 'a=first&sign_type=RSA2&z=last');
  assert.equal(canonicalize(parameters.entries(), { excludeSignType: true }), 'a=first&z=last');
});

test('Alipay timestamp is always formatted in Asia Shanghai time', () => {
  assert.equal(alipayTimestamp(new Date('2026-08-13T09:00:00Z')), '2026-08-13 17:00:00');
});

test('RSA2 signatures verify and reject a changed amount', async () => {
  const parameters = new URLSearchParams({ app_id: 'app', out_trade_no: 'order', total_amount: '29.00' });
  const signature = await signParameters(parameters, privateKey);
  assert.equal(await verifyParameters(parameters, signature, publicKey), true);
  parameters.set('total_amount', '0.01');
  assert.equal(await verifyParameters(parameters, signature, publicKey), false);
});

test('gateway fails closed without secrets', async () => {
  const response = await worker.fetch(new Request('https://internal/checkout', { method: 'POST', body: '{}' }), {});
  assert.equal(response.status, 503);
});

test('gateway rejects invalid notification signature', async () => {
  const response = await worker.fetch(new Request('https://internal/verify', {
    method: 'POST',
    headers: { authorization: 'Bearer internal', 'content-type': 'application/json' },
    body: JSON.stringify({ body: 'app_id=app&trade_status=TRADE_SUCCESS&sign=invalid' }),
  }), {
    PAYMENT_GATEWAY_TOKEN: 'internal', ALIPAY_APP_ID: 'app', ALIPAY_SELLER_ID: 'seller', ALIPAY_PRIVATE_KEY: privateKey, ALIPAY_PUBLIC_KEY: publicKey,
  });
  assert.equal(response.status, 400);
});

test('checkout rejects non-HTTPS callbacks and unknown payment scenes', async () => {
  const response = await worker.fetch(new Request('https://internal/checkout', {
    method: 'POST',
    headers: { authorization: 'Bearer internal', 'content-type': 'application/json' },
    body: JSON.stringify({
      order_id: 'order', amount_fen: 2900, scene: 'tablet',
      notify_url: 'http://idea.example/webhook', return_url: 'https://idea.example/account',
    }),
  }), {
    PAYMENT_GATEWAY_TOKEN: 'internal', ALIPAY_APP_ID: 'app', ALIPAY_SELLER_ID: 'seller', ALIPAY_PRIVATE_KEY: privateKey, ALIPAY_PUBLIC_KEY: publicKey,
  });
  assert.equal(response.status, 400);
});

for (const [scene, method, productCode] of [
  ['desktop', 'alipay.trade.page.pay', 'FAST_INSTANT_TRADE_PAY'],
  ['mobile', 'alipay.trade.wap.pay', 'QUICK_WAP_WAY'],
]) test(`checkout creates a signed ${scene} website payment URL`, async () => {
  const response = await worker.fetch(new Request('https://internal/checkout', {
    method: 'POST',
    headers: { authorization: 'Bearer internal', 'content-type': 'application/json' },
    body: JSON.stringify({
      order_id: 'order-id', amount_fen: 2900, subject: 'Starter', scene,
      notify_url: 'https://idea.example/webhook', return_url: 'https://idea.example/account?payment=return',
    }),
  }), {
    PAYMENT_GATEWAY_TOKEN: 'internal', ALIPAY_APP_ID: 'app', ALIPAY_SELLER_ID: 'seller',
    ALIPAY_PRIVATE_KEY: privateKey, ALIPAY_PUBLIC_KEY: publicKey,
  });
  assert.equal(response.status, 200);
  const result = await response.json();
  const paymentUrl = new URL(result.pay_url);
  const parameters = paymentUrl.searchParams;
  assert.equal(result.provider_order_id, 'ISorderid');
  assert.equal(paymentUrl.origin + paymentUrl.pathname, 'https://openapi.alipay.com/gateway.do');
  assert.equal(parameters.get('method'), method);
  assert.equal(parameters.get('return_url'), 'https://idea.example/account?payment=return');
  assert.deepEqual(JSON.parse(parameters.get('biz_content')), {
    out_trade_no: 'ISorderid', total_amount: '29.00', subject: 'Starter',
    product_code: productCode, timeout_express: '15m',
  });
  const signature = parameters.get('sign');
  parameters.delete('sign');
  const signatureValid = await crypto.subtle.verify(
    'RSASSA-PKCS1-v1_5',
    await crypto.subtle.importKey('spki', Buffer.from(publicKey.replace(/-----[^-]+-----|\s/g, ''), 'base64'), { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['verify']),
    Buffer.from(signature, 'base64'), new TextEncoder().encode(canonicalize(parameters.entries())),
  );
  assert.equal(signatureValid, true);
});

test('verified notification returns server fulfillment fields', async () => {
  const notification = new URLSearchParams({
    app_id: 'app', seller_id: 'seller', out_trade_no: 'ISorder', trade_no: '20260813001',
    trade_status: 'TRADE_SUCCESS', total_amount: '29.00', sign_type: 'RSA2',
  });
  notification.set('sign', await signParameters(notification, privateKey, { excludeSignType: true }));
  const response = await worker.fetch(new Request('https://internal/verify', {
    method: 'POST',
    headers: { authorization: 'Bearer internal', 'content-type': 'application/json' },
    body: JSON.stringify({ body: notification.toString() }),
  }), {
    PAYMENT_GATEWAY_TOKEN: 'internal', ALIPAY_APP_ID: 'app', ALIPAY_SELLER_ID: 'seller',
    ALIPAY_PRIVATE_KEY: privateKey, ALIPAY_PUBLIC_KEY: publicKey,
  });
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), {
    event_key: '20260813001:TRADE_SUCCESS', event_type: 'TRADE_SUCCESS', provider_order_id: 'ISorder',
    provider_trade_id: '20260813001', amount_fen: 2900,
    payload_digest: await crypto.subtle.digest('SHA-256', new TextEncoder().encode(notification.toString()))
      .then((digest) => [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('')),
  });
});
