import assert from 'node:assert/strict';
import test from 'node:test';

import { registrationOptions } from './auth.js';

test('passes the Turnstile token through the native Supabase signup contract', () => {
  assert.deepEqual(registrationOptions('Edward', 'captcha-token', 'https://idea.example/auth/callback'), {
    emailRedirectTo: 'https://idea.example/auth/callback',
    captchaToken: 'captcha-token',
    data: { username: 'Edward' },
  });
});
