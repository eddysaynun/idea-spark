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
