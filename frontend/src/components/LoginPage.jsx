import { useEffect, useState } from 'react';
import { Apple, ArrowLeft, LoaderCircle, Mail } from 'lucide-react';

import { authAPI } from '../api';
import { pendingDeletionFrom } from '../utils/account';
import { registrationOptions } from '../utils/auth';
import Turnstile from './Turnstile';
import './LoginPage.css';

const messageFrom = (error) => {
  const detail = error?.response?.data?.detail;
  return error?.message || (typeof detail === 'string' ? detail : '') || '登录没有完成，请重试';
};
const AUTH_STORAGE_KEY = 'idea-spark-managed-auth';

const withTimeout = (promise, milliseconds, message) => Promise.race([
  promise,
  new Promise((_, reject) => window.setTimeout(() => reject(new Error(message)), milliseconds)),
]);

const GitHubIcon = () => (
  <svg className="provider-icon github-icon" viewBox="0 0 24 24" aria-hidden="true">
    <path fill="currentColor" d="M12 .7a11.5 11.5 0 0 0-3.64 22.4c.58.1.79-.25.79-.56v-2.24c-3.22.7-3.9-1.37-3.9-1.37-.52-1.34-1.28-1.7-1.28-1.7-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.57-.29-5.27-1.28-5.27-5.68 0-1.26.45-2.28 1.18-3.09-.12-.29-.51-1.46.11-3.05 0 0 .96-.31 3.16 1.18A10.95 10.95 0 0 1 12 6.1c.98 0 1.95.13 2.87.39 2.2-1.49 3.16-1.18 3.16-1.18.62 1.59.23 2.76.11 3.05.74.81 1.18 1.83 1.18 3.09 0 4.41-2.71 5.38-5.29 5.67.42.36.79 1.07.79 2.16v3.27c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .7Z" />
  </svg>
);

const GoogleIcon = () => (
  <svg className="provider-icon google-icon" viewBox="0 0 24 24" aria-hidden="true">
    <path fill="#4285F4" d="M21.6 12.23c0-.71-.06-1.4-.18-2.07H12v3.91h5.38a4.6 4.6 0 0 1-1.99 3.02v2.54h3.23c1.89-1.74 2.98-4.31 2.98-7.4Z" />
    <path fill="#34A853" d="M12 22c2.7 0 4.96-.89 6.62-2.41l-3.23-2.54c-.9.6-2.04.96-3.39.96-2.6 0-4.81-1.76-5.6-4.12H3.06v2.62A10 10 0 0 0 12 22Z" />
    <path fill="#FBBC05" d="M6.4 13.89A6 6 0 0 1 6.08 12c0-.66.11-1.3.32-1.89V7.49H3.06A10 10 0 0 0 2 12c0 1.62.39 3.15 1.06 4.51l3.34-2.62Z" />
    <path fill="#EA4335" d="M12 5.99c1.47 0 2.79.5 3.82 1.49l2.87-2.87A9.63 9.63 0 0 0 12 2a10 10 0 0 0-8.94 5.49l3.34 2.62C7.19 7.75 9.4 5.99 12 5.99Z" />
  </svg>
);

let managedAuthClientPromise;
let callbackCompletionPromise;

const managedAuthClient = (settings) => {
  if (!managedAuthClientPromise) {
    managedAuthClientPromise = import('@supabase/supabase-js').then(({ createClient }) => createClient(
      settings.url,
      settings.anon_key,
      {
        auth: {
          flowType: 'pkce',
          persistSession: true,
          autoRefreshToken: false,
          detectSessionInUrl: false,
          storageKey: AUTH_STORAGE_KEY,
        },
      },
    ));
  }
  return managedAuthClientPromise;
};

const completeManagedCallback = (supabase, onStage) => {
  if (!callbackCompletionPromise) {
    callbackCompletionPromise = (async () => {
      const params = new URLSearchParams(window.location.search);
      const callbackError = params.get('error_description') || params.get('error');
      if (callbackError) throw new Error(callbackError);
      const code = params.get('code');
      const flowId = params.get('sb_flow_id');
      window.history.replaceState({}, '', '/auth/callback');
      onStage('正在验证 GitHub / Google 登录…');
      const result = code
        ? await withTimeout(
          supabase.auth.exchangeCodeForSession(code, flowId ? { flowId } : undefined),
          20000,
          '登录服务响应超时，请返回登录页重试',
        )
        : await withTimeout(supabase.auth.getSession(), 5000, '没有找到可用的登录会话，请重新登录');
      if (result.error) throw result.error;
      if (!result.data.session) throw new Error('登录链接无效或已过期，请重新登录');
      onStage('正在创建安全工作区会话…');
      await withTimeout(
        authAPI.exchange(result.data.session.access_token),
        20000,
        '工作区登录响应超时，请重试',
      );
      window.localStorage.removeItem(AUTH_STORAGE_KEY);
    })();
  }
  return callbackCompletionPromise;
};

export default function LoginPage({ onComplete }) {
  const [config, setConfig] = useState(null);
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [supabase, setSupabase] = useState(null);
  const [pendingDeletion, setPendingDeletion] = useState(null);
  const [captchaToken, setCaptchaToken] = useState('');
  const [captchaAttempt, setCaptchaAttempt] = useState(0);

  useEffect(() => {
    authAPI.providers().then(setConfig).catch((reason) => setError(messageFrom(reason)));
  }, []);

  useEffect(() => {
    const settings = config?.supabase;
    if (!settings?.configured) return;
    let active = true;
    managedAuthClient(settings).then((client) => {
      if (active) setSupabase(client);
    }).catch((reason) => active && setError(messageFrom(reason)));
    return () => { active = false; };
  }, [config]);

  useEffect(() => {
    if (!supabase || window.location.pathname !== '/auth/callback') return;
    let active = true;
    setBusy(true);
    setError('');
    completeManagedCallback(supabase, (stage) => active && setNotice(stage)).then(() => {
      if (active) window.location.replace('/');
    }).catch((reason) => {
      if (!active) return;
      const pending = pendingDeletionFrom(reason);
      if (pending) {
        setPendingDeletion(pending);
        setNotice(`账号将在 ${new Date(pending.deletion_due_at).toLocaleString('zh-CN')} 永久删除。`);
      } else setError(messageFrom(reason));
    }).finally(() => active && setBusy(false));
    return () => { active = false; };
  }, [supabase]);

  const submitEmail = async (event) => {
    event.preventDefault();
    if (!supabase) return setError('邮箱登录尚未开放');
    setBusy(true); setError(''); setNotice('');
    try {
      if (mode === 'register') {
        const { data, error: signUpError } = await supabase.auth.signUp({
          email, password,
          options: registrationOptions(
            username, captchaToken, `${window.location.origin}/auth/callback`,
          ),
        });
        if (signUpError) throw signUpError;
        if (!data.session) {
          setNotice('验证邮件已发送。请打开邮件完成验证，再返回登录。');
          return;
        }
        await authAPI.exchange(data.session.access_token);
      } else {
        const { data, error: loginError } = await supabase.auth.signInWithPassword({ email, password });
        if (loginError) throw loginError;
        await authAPI.exchange(data.session.access_token);
      }
      window.localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.replace('/');
    } catch (reason) {
      const pending = pendingDeletionFrom(reason);
      if (pending) {
        setPendingDeletion(pending);
        setNotice(`账号将在 ${new Date(pending.deletion_due_at).toLocaleString('zh-CN')} 永久删除。`);
      } else setError(messageFrom(reason));
    } finally {
      if (mode === 'register') {
        setCaptchaToken('');
        setCaptchaAttempt((value) => value + 1);
      }
      setBusy(false);
    }
  };

  const restoreAccount = async () => {
    if (!supabase) return;
    setBusy(true); setError('');
    try {
      const { data, error: sessionError } = await supabase.auth.getSession();
      if (sessionError || !data.session) throw sessionError || new Error('登录凭据已过期，请重新登录');
      await authAPI.restore(data.session.access_token);
      window.localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.replace('/');
    } catch (reason) {
      setError(messageFrom(reason));
    } finally {
      setBusy(false);
    }
  };

  const oauth = async (provider) => {
    if (!supabase) return;
    setBusy(true); setError('');
    try {
      const { error: oauthError } = await withTimeout(supabase.auth.signInWithOAuth({
        provider,
        options: { redirectTo: `${window.location.origin}/auth/callback` },
      }), 15000, '登录服务响应超时，请重试');
      if (oauthError) throw oauthError;
    } catch (reason) {
      setError(messageFrom(reason));
      setBusy(false);
    }
  };

  const enabled = config?.supabase?.providers || {};

  return (
    <section className="login-page">
      <button className="login-back" onClick={onComplete}><ArrowLeft size={16} /> 返回工作台</button>
      <div className="login-layout">
        <div className="login-intro">
          <span className="login-kicker">YOUR PRIVATE WORKSPACE</span>
          <h1>保存每一次<br />灵感演进</h1>
          <p>登录后，你的 Idea、详细方案和免费额度都会安全地绑定到同一个账号。</p>
          <div className="login-entitlement"><strong>5</strong><span>个免费 Idea<br />+ 2 份详细方案</span></div>
        </div>
        <div className="login-card">
          <div className="login-tabs" role="tablist">
            <button className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>登录</button>
            <button className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>邮箱注册</button>
          </div>
          {enabled.email && <form onSubmit={submitEmail}>
            {mode === 'register' && <label>用户名<input type="text" autoComplete="nickname" value={username} onChange={(e) => setUsername(e.target.value)} required minLength="2" maxLength="32" pattern="[\p{L}\p{N}_\- ]+" placeholder="你的公开显示名称" /></label>}
            <label>邮箱<input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required placeholder="you@example.com" /></label>
            <label>密码<input type="password" minLength="8" autoComplete={mode === 'register' ? 'new-password' : 'current-password'} value={password} onChange={(e) => setPassword(e.target.value)} required placeholder="至少 8 位" /></label>
            {mode === 'register' && config?.turnstile_site_key && <Turnstile key={captchaAttempt} siteKey={config.turnstile_site_key} onToken={setCaptchaToken} />}
            <button className="login-primary" disabled={busy || (mode === 'register' && config?.turnstile_site_key && !captchaToken)}>{busy ? <LoaderCircle className="spin" size={18} /> : <Mail size={18} />}{mode === 'register' ? '创建账号' : '使用邮箱登录'}</button>
          </form>}
          {(enabled.github || enabled.google || enabled.apple) && <div className="login-divider"><span>或者</span></div>}
          <div className="login-providers">
            {enabled.github && <button onClick={() => oauth('github')} disabled={busy}><GitHubIcon /> GitHub</button>}
            {enabled.google && <button onClick={() => oauth('google')} disabled={busy}><GoogleIcon /> Google</button>}
            {enabled.apple && <button onClick={() => oauth('apple')} disabled={busy}><Apple size={18} /> Apple</button>}
          </div>
          {!config?.supabase?.configured && <p className="login-setup">登录服务正在配置中，请稍后再试。</p>}
          {notice && <p className="login-notice" role="status">{notice}</p>}
          {pendingDeletion && <button className="login-primary" onClick={restoreAccount} disabled={busy}>恢复账号并继续使用</button>}
          {error && <p className="login-error" role="alert">{error}</p>}
          <p className="login-terms">注册即表示你同意<a href="/terms">服务条款</a>与<a href="/privacy">隐私政策</a>。邮箱需验证后才能领取免费额度。</p>
        </div>
      </div>
    </section>
  );
}
