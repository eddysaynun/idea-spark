import assert from 'node:assert/strict';
import test from 'node:test';

import { pageFromPath, pathForPage } from './routes.js';

test('maps public SPA paths to pages', () => {
  assert.equal(pageFromPath('/'), 'generate');
  assert.equal(pageFromPath('/history'), 'history');
  assert.equal(pageFromPath('/account'), 'account');
  assert.equal(pageFromPath('/auth/callback'), 'login');
  assert.equal(pageFromPath('/unknown'), 'generate');
});

test('maps page changes to stable URLs', () => {
  assert.equal(pathForPage('generate'), '/');
  assert.equal(pathForPage('detail'), '/detail');
  assert.equal(pathForPage('history'), '/history');
});
