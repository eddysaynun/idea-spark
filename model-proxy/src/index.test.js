import assert from 'node:assert/strict';
import test from 'node:test';

import worker from './index.js';

test('rejects requests without proxy authorization', async () => {
  const response = await worker.fetch(
    new Request('https://proxy.test/v1/models'),
    { PROXY_API_KEY: 'secret' },
  );
  assert.equal(response.status, 401);
});

test('does not expose arbitrary upstream paths', async () => {
  const response = await worker.fetch(
    new Request('https://proxy.test/admin', {
      headers: { authorization: 'Bearer secret' },
    }),
    { PROXY_API_KEY: 'secret' },
  );
  assert.equal(response.status, 404);
});

test('rejects methods that do not match the upstream operation', async () => {
  const response = await worker.fetch(
    new Request('https://proxy.test/v1/models', {
      method: 'POST',
      headers: { authorization: 'Bearer secret' },
    }),
    { PROXY_API_KEY: 'secret' },
  );
  assert.equal(response.status, 405);
});

test('rejects oversized model payloads before forwarding', async () => {
  const response = await worker.fetch(
    new Request('https://proxy.test/v1/chat/completions', {
      method: 'POST',
      headers: { authorization: 'Bearer secret', 'content-length': '1000001' },
      body: '{}',
    }),
    { PROXY_API_KEY: 'secret' },
  );
  assert.equal(response.status, 413);
});
