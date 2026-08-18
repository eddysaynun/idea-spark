import assert from 'node:assert/strict';
import test from 'node:test';

import { pendingDeletionFrom } from './account.js';

test('extracts only the stable pending-deletion API contract', () => {
  assert.deepEqual(pendingDeletionFrom({ response: { data: { detail: {
    code: 'account_deletion_pending', deletion_due_at: '2026-08-25T08:00:00Z',
  } } } }), { code: 'account_deletion_pending', deletion_due_at: '2026-08-25T08:00:00Z' });
  assert.equal(pendingDeletionFrom({ response: { data: { detail: 'ordinary error' } } }), null);
});
