import { useEffect, useState } from 'react';
import { Apple, ArrowLeft, LoaderCircle, Mail } from 'lucide-react';

import { authAPI } from '../api';
import { useApp } from '../context/app-context';
import './LoginPage.css';

const messageFrom = (error) => error?.message || error?.response?.data?.detail || '登录没有完成，请重试';

export default function LoginPage({ onComplete }) {
  const { refreshUser } = useApp();
  const [config, setConfig] = useState(null);
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [supabase, setSupabase] = useState(null);

  useEffect(() => {
    authAPI.providers().then(setConfig).catch((reason) => setError(messageFrom(reason)));
  }, []);

  useEffect(() => {
    const settings = config?.supabase;
    if (!settings?.configured) return;
    let active = true;
    import('@supabase/supabase-js').then(({ createClient }) => {
      if (active) setSupabase(createClient(settings.url, settings.anon_key, {
        auth: { flowType: 'pkce', persistSession: true, detectSessionInUrl: true },
      }));
    }).catch((reason) => active && setError(messageFrom(reason)));
    return () => { active = false; };
  }, [config]);

  useEffect(() => {
    if (!supabase || window.location.pathname !== '/auth/callback') return;
    let active = true;
    setBusy(true);
    supabase.auth.getSession().then(async ({ data, error: sessionError }) => {
      if (sessionError) throw sessionError;
      if (!data.session) throw new Error('登录链接无效或已过期，请重新登录');
      await authAPI.exchange(data.session.access_token);
      await supabase.auth.signOut({ scope: 'local' });
      await refreshUser();
      if (active) {
        window.history.replaceState({}, '', '/');
        onComplete();
      }
    }).catch((reason) => active && setError(messageFrom(reason))).finally(() => active && setBusy(false));
    return () => { active = false; };
  }, [onComplete, refreshUser, supabase]);

  const submitEmail = async (event) => {
    event.preventDefault();
    if (!supabase) return setError('邮箱登录尚未开放');
    setBusy(true); setError(''); setNotice('');
    try {
      if (mode === 'register') {
        const { data, error: signUpError } = await supabase.auth.signUp({
          email, password,
          options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
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
      await supabase.auth.signOut({ scope: 'local' });
      await refreshUser();
      onComplete();
    } catch (reason) {
      setError(messageFrom(reason));
    } finally {
      setBusy(false);
    }
  };

  const oauth = async (provider) => {
    if (!supabase) return;
    setBusy(true); setError('');
    const { error: oauthError } = await supabase.auth.signInWithOAuth({
      provider,
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
    if (oauthError) { setError(messageFrom(oauthError)); setBusy(false); }
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
            <label>邮箱<input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required placeholder="you@example.com" /></label>
            <label>密码<input type="password" minLength="8" autoComplete={mode === 'register' ? 'new-password' : 'current-password'} value={password} onChange={(e) => setPassword(e.target.value)} required placeholder="至少 8 位" /></label>
            <button className="login-primary" disabled={busy}>{busy ? <LoaderCircle className="spin" size={18} /> : <Mail size={18} />}{mode === 'register' ? '创建账号' : '使用邮箱登录'}</button>
          </form>}
          {(config?.github || enabled.google || enabled.apple) && <div className="login-divider"><span>或者</span></div>}
          <div className="login-providers">
            {enabled.github && <button onClick={() => oauth('github')} disabled={busy}><span className="github-mark">GH</span> GitHub</button>}
            {config?.github && <a href={authAPI.loginUrl('/')}><span className="github-mark">GH</span> GitHub</a>}
            {enabled.google && <button onClick={() => oauth('google')} disabled={busy}><span className="google-g">G</span> Google</button>}
            {enabled.apple && <button onClick={() => oauth('apple')} disabled={busy}><Apple size={18} /> Apple</button>}
          </div>
          {!config?.supabase?.configured && <p className="login-setup">邮箱、Google 和 Apple 登录正在配置中；GitHub 登录已经可用。</p>}
          {notice && <p className="login-notice" role="status">{notice}</p>}
          {error && <p className="login-error" role="alert">{error}</p>}
          <p className="login-terms">注册即表示你同意仅将账号用于保存自己的生成记录。邮箱需验证后才能领取免费额度。</p>
        </div>
      </div>
    </section>
  );
}
