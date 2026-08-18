import assert from 'node:assert/strict';
import test from 'node:test';

import { canRefundOrder } from './payment.js';

test('enables refund only for paid orders not already refunded', () => {
  assert.equal(canRefundOrder({ status: 'paid', refund_state: 'none' }), true);
  assert.equal(canRefundOrder({ status: 'paid', refund_state: 'pending' }), true);
  assert.equal(canRefundOrder({ status: 'refunded', refund_state: 'refunded' }), false);
  assert.equal(canRefundOrder({ status: 'pending', refund_state: 'none' }), false);
});
