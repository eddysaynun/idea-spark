import assert from 'node:assert/strict';
import { generateKeyPairSync } from 'node:crypto';
import test from 'node:test';

import worker, { alipayTimestamp, canonicalize, extractSignedResponse, signParameters, verifyParameters } from './index.js';

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

test('checkout rejects an unsigned Alipay response', async (context) => {
  context.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({
    alipay_trade_precreate_response: { code: '10000', qr_code: 'https://qr.alipay.com/fake' },
  })));
  const response = await worker.fetch(new Request('https://internal/checkout', {
    method: 'POST',
    headers: { authorization: 'Bearer internal', 'content-type': 'application/json' },
    body: JSON.stringify({ order_id: 'order', amount_fen: 2900, notify_url: 'https://idea.example/webhook' }),
  }), {
    PAYMENT_GATEWAY_TOKEN: 'internal', ALIPAY_APP_ID: 'app', ALIPAY_SELLER_ID: 'seller', ALIPAY_PRIVATE_KEY: privateKey, ALIPAY_PUBLIC_KEY: publicKey,
  });
  assert.equal(response.status, 502);
});

test('checkout accepts a correctly signed Alipay QR response', async (context) => {
  const tradeText = '{"code":"10000","msg":"Success","qr_code":"https://qr.alipay.com/real","nested":{"value":"brace } in string"}}';
  const signatureBytes = await crypto.subtle.sign(
    'RSASSA-PKCS1-v1_5',
    await crypto.subtle.importKey('pkcs8', Buffer.from(privateKey.replace(/-----[^-]+-----|\s/g, ''), 'base64'), { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['sign']),
    new TextEncoder().encode(tradeText),
  );
  const responseText = `{"alipay_trade_precreate_response":${tradeText},"sign":"${Buffer.from(signatureBytes).toString('base64')}"}`;
  assert.equal(extractSignedResponse(responseText, 'alipay_trade_precreate_response'), tradeText);
  context.mock.method(globalThis, 'fetch', async () => new Response(responseText));
  const response = await worker.fetch(new Request('https://internal/checkout', {
    method: 'POST',
    headers: { authorization: 'Bearer internal', 'content-type': 'application/json' },
    body: JSON.stringify({ order_id: 'order', amount_fen: 2900, subject: 'Starter', notify_url: 'https://idea.example/webhook' }),
  }), {
    PAYMENT_GATEWAY_TOKEN: 'internal', ALIPAY_APP_ID: 'app', ALIPAY_SELLER_ID: 'seller',
    ALIPAY_PRIVATE_KEY: privateKey, ALIPAY_PUBLIC_KEY: publicKey,
  });
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { provider_order_id: 'ISorder', pay_url: 'https://qr.alipay.com/real' });
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
