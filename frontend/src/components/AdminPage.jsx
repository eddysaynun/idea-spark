import { useState } from 'react';
import { AlertTriangle, KeyRound, LoaderCircle, Search, ShieldCheck } from 'lucide-react';

import { adminAPI } from '../api';
import './AdminPage.css';

const errorText = (error) => error?.response?.data?.detail || error?.message || '操作失败，请重试';

const Quota = ({ label, resource, user, token, onUpdated }) => {
  const [delta, setDelta] = useState('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const limit = user[`${resource}_limit`];
  const used = user[`${resource}_used`];
  const reserved = user[`${resource}_reserved`];

  const adjust = async () => {
    const amount = Number.parseInt(delta, 10);
    if (!amount || reason.trim().length < 3) return;
    setBusy(true);
    try {
      const data = await adminAPI.adjustQuota(token, user.id, resource, amount, reason.trim());
      onUpdated(data.user, `${label}额度已调整 ${amount > 0 ? '+' : ''}${amount}`);
      setDelta(''); setReason('');
    } catch (error) { onUpdated(null, '', errorText(error)); }
    finally { setBusy(false); }
  };

  const repair = async () => {
    if (!reserved || reason.trim().length < 3) return;
    if (!window.confirm(`确认把该用户的 ${reserved} 个${label}预占清零？仅应在确认任务已经中断时操作。`)) return;
    setBusy(true);
    try {
      const data = await adminAPI.repairQuota(token, user.id, resource, reason.trim());
      onUpdated(data.user, `${label}异常预占已清理`);
      setReason('');
    } catch (error) { onUpdated(null, '', errorText(error)); }
    finally { setBusy(false); }
  };

  return <section className="quota-admin">
    <div className="quota-admin-head"><strong>{label}</strong><span>{Math.max(0, limit - used - reserved)} 可用</span></div>
    <dl><div><dt>上限</dt><dd>{limit}</dd></div><div><dt>已用</dt><dd>{used}</dd></div><div><dt>预占</dt><dd className={reserved ? 'warn' : ''}>{reserved}</dd></div></dl>
    <label>调整数量<input type="number" value={delta} onChange={(e) => setDelta(e.target.value)} placeholder="例如 50 或 -10" /></label>
    <label>操作原因<input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder="必填，至少 3 个字符" /></label>
    <div className="quota-actions">
      <button onClick={adjust} disabled={busy || !Number.parseInt(delta, 10) || reason.trim().length < 3}>调整额度</button>
      {reserved > 0 && <button className="repair" onClick={repair} disabled={busy || reason.trim().length < 3}><AlertTriangle size={15} /> 清理预占</button>}
    </div>
  </section>;
};

export default function AdminPage() {
  const [token, setToken] = useState('');
  const [query, setQuery] = useState('');
  const [users, setUsers] = useState([]);
  const [selected, setSelected] = useState(null);
  const [events, setEvents] = useState([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const search = async (event) => {
    event?.preventDefault();
    if (!token) return;
    setBusy(true); setError(''); setMessage('');
    try {
      const data = await adminAPI.users(token, query.trim());
      setUsers(data.users);
      if (selected) setSelected(data.users.find((user) => user.id === selected.id) || null);
    } catch (reason) { setError(errorText(reason)); setUsers([]); }
    finally { setBusy(false); }
  };

  const choose = async (user) => {
    setSelected(user); setMessage(''); setError(''); setEvents([]);
    try { setEvents((await adminAPI.audit(token, user.id)).events); }
    catch (reason) { setError(errorText(reason)); }
  };

  const updated = async (user, success = '', failure = '') => {
    if (failure) { setError(failure); setMessage(''); return; }
    setSelected(user); setUsers((current) => current.map((item) => item.id === user.id ? user : item));
    setMessage(success); setError('');
    setEvents((await adminAPI.audit(token, user.id)).events);
  };

  return <section className="admin-page">
    <header className="admin-title"><span><ShieldCheck size={18} /> COMMERCIAL CONTROL</span><h1>用户与额度管理</h1><p>所有修改由服务端校验并写入审计记录。管理员令牌不会保存在浏览器中。</p></header>
    <div className="admin-token"><KeyRound size={18} /><label>管理员令牌<input type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)} placeholder="IDEA_SPARK_ADMIN_TOKEN" /></label></div>
    <form className="admin-search" onSubmit={search}><Search size={17} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="按邮箱、GitHub 用户名、显示名或用户 ID 搜索" /><button disabled={!token || busy}>{busy ? <LoaderCircle className="spin" size={16} /> : '查询'}</button></form>
    {message && <p className="admin-message" role="status">{message}</p>}
    {error && <p className="admin-error" role="alert">{error}</p>}
    <div className="admin-workspace">
      <aside className="user-results">
        <div className="user-results-head"><span>用户</span><strong>{users.length}</strong></div>
        {users.length === 0 ? <p>输入管理员令牌后查询用户。</p> : users.map((user) => <button key={user.id} className={selected?.id === user.id ? 'active' : ''} onClick={() => choose(user)}><strong>{user.display_name}</strong><span>{user.login}</span><small>{user.provider}</small></button>)}
      </aside>
      <div className="admin-detail">
        {!selected ? <div className="admin-empty"><ShieldCheck size={28} /><p>选择用户后查看和修复权益。</p></div> : <>
          <div className="selected-user"><div><span>{selected.provider}</span><h2>{selected.display_name}</h2><p>{selected.login}</p></div><code>{selected.id}</code></div>
          <div className="quota-grid"><Quota label="Idea" resource="idea" user={selected} token={token} onUpdated={updated} /><Quota label="详细方案" resource="detail" user={selected} token={token} onUpdated={updated} /></div>
          <section className="audit-list"><h3>管理员操作记录</h3>{events.length === 0 ? <p>暂无人工调整记录。</p> : events.map((event, index) => <article key={`${event.created_at}-${index}`}><span>{new Date(event.created_at).toLocaleString('zh-CN')}</span><strong>{event.resource === 'idea' ? 'Idea' : '详细方案'} · {event.action === 'adjust_limit' ? `调整 ${event.delta > 0 ? '+' : ''}${event.delta}` : '清理预占'}</strong><p>{event.reason}</p><small>上限 {event.limit_before} → {event.limit_after} · 预占 {event.reserved_before} → {event.reserved_after}</small></article>)}</section>
        </>}
      </div>
    </div>
  </section>;
}
