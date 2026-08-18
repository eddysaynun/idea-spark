import assert from 'node:assert/strict';
import test from 'node:test';

import { clampGenerationCount } from './quota.js';

test('keeps generation count inside the latest remaining quota', () => {
  assert.equal(clampGenerationCount(5, 2), 2);
  assert.equal(clampGenerationCount(2, 0), 0);
  assert.equal(clampGenerationCount(0, 5), 1);
});
