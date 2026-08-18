import { useState } from 'react';
import { AlertTriangle, KeyRound, LoaderCircle, RefreshCw, RotateCcw, Search, ShieldCheck } from 'lucide-react';

import { adminAPI } from '../api';
import { canRefundOrder } from '../utils/payment';
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
  const [rechargeRecords, setRechargeRecords] = useState([]);
  const [paymentOrders, setPaymentOrders] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [paymentBusy, setPaymentBusy] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const search = async (event) => {
    event?.preventDefault();
    if (!token) return;
    setBusy(true); setError(''); setMessage('');
    try {
      const [data, ordersData, metricsData] = await Promise.all([
        adminAPI.users(token, query.trim()),
        adminAPI.paymentOrders(token),
        adminAPI.metrics(token),
      ]);
      setUsers(data.users);
      setPaymentOrders(ordersData.orders);
      setMetrics(metricsData.metrics);
      if (selected) setSelected(data.users.find((user) => user.id === selected.id) || null);
    } catch (reason) { setError(errorText(reason)); setUsers([]); }
    finally { setBusy(false); }
  };

  const choose = async (user) => {
    setSelected(user); setMessage(''); setError(''); setEvents([]); setRechargeRecords([]);
    try {
      const [auditData, rechargeData] = await Promise.all([
        adminAPI.audit(token, user.id),
        adminAPI.rechargeHistory(token, user.id),
      ]);
      setEvents(auditData.events);
      setRechargeRecords(rechargeData.records);
    }
    catch (reason) { setError(errorText(reason)); }
  };

  const updated = async (user, success = '', failure = '') => {
    if (failure) { setError(failure); setMessage(''); return; }
    setSelected(user); setUsers((current) => current.map((item) => item.id === user.id ? user : item));
    setMessage(success); setError('');
    const [auditData, rechargeData] = await Promise.all([
      adminAPI.audit(token, user.id),
      adminAPI.rechargeHistory(token, user.id),
    ]);
    setEvents(auditData.events);
    setRechargeRecords(rechargeData.records);
  };

  const paymentAction = async (order, action) => {
    if (action === 'refund' && !window.confirm(`确认全额退回订单 ${order.id}？未使用额度将同时扣回。`)) return;
    setPaymentBusy(`${action}-${order.id}`); setError(''); setMessage('');
    try {
      const data = action === 'query'
        ? await adminAPI.queryPayment(token, order.id)
        : await adminAPI.refundPayment(token, order.id);
      setPaymentOrders((await adminAPI.paymentOrders(token)).orders);
      setMessage(action === 'query' ? `查单完成：${data.status}` : `退款处理完成：${data.status}`);
    } catch (reason) { setError(errorText(reason)); }
    finally { setPaymentBusy(''); }
  };

  return <section className="admin-page">
    <header className="admin-title"><span><ShieldCheck size={18} /> COMMERCIAL CONTROL</span><h1>用户与额度管理</h1><p>所有修改由服务端校验并写入审计记录。管理员令牌不会保存在浏览器中。</p></header>
    <div className="admin-token"><KeyRound size={18} /><label>管理员令牌<input type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)} placeholder="IDEA_SPARK_ADMIN_TOKEN" /></label></div>
    <form className="admin-search" onSubmit={search}><Search size={17} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="按邮箱、GitHub 用户名、显示名或用户 ID 搜索" /><button disabled={!token || busy}>{busy ? <LoaderCircle className="spin" size={16} /> : '查询'}</button></form>
    {message && <p className="admin-message" role="status">{message}</p>}
    {error && <p className="admin-error" role="alert">{error}</p>}
    {metrics && <section className="admin-metrics" aria-label={`最近 ${metrics.window_days} 天运营快照`}>
      <div className="admin-metrics-head"><span>最近 {metrics.window_days} 天</span><strong>运营快照</strong></div>
      <dl>
        <div><dt>新增用户</dt><dd>{metrics.users.new}</dd><small>{metrics.users.active} 个活跃账户</small></div>
        <div><dt>完成生成</dt><dd>{metrics.generation.complete}</dd><small>{metrics.generation.failed} 次失败</small></div>
        <div><dt>详细方案</dt><dd>{metrics.generation.details}</dd><small>已落库方案</small></div>
        <div><dt>无价值反馈</dt><dd>{metrics.generation.no_value}</dd><small>用户明确反馈</small></div>
        <div><dt>实收金额</dt><dd>¥{(metrics.payments.revenue_fen / 100).toFixed(2)}</dd><small>{metrics.payments.paid} 笔支付 · {metrics.payments.refunded} 笔退款</small></div>
        <div className={metrics.quota.stuck_reservations ? 'metric-alert' : ''}><dt>异常预占</dt><dd>{metrics.quota.stuck_reservations}</dd><small>超过 30 分钟</small></div>
      </dl>
    </section>}
    {paymentOrders.length > 0 && <section className="payment-admin"><div className="payment-admin-head"><span>支付订单审计</span><strong>{paymentOrders.length}</strong></div>{paymentOrders.map((item) => <article key={item.id}><div><strong>{item.display_name}</strong><span>{item.login}</span></div><p>{item.package_name} · ¥{(item.amount_fen / 100).toFixed(2)}</p><small>{item.channel === 'wechat' ? '微信支付' : '支付宝'} · {item.status}{item.refund_state === 'pending' ? ' · 退款待对账' : ''}</small><code>{item.id}</code><div className="payment-actions"><button onClick={() => paymentAction(item, 'query')} disabled={!!paymentBusy}>{paymentBusy === `query-${item.id}` ? <LoaderCircle className="spin" size={13} /> : <RefreshCw size={13} />} 查单</button>{canRefundOrder(item) && <button className="refund" onClick={() => paymentAction(item, 'refund')} disabled={!!paymentBusy}>{paymentBusy === `refund-${item.id}` ? <LoaderCircle className="spin" size={13} /> : <RotateCcw size={13} />} 全额退款</button>}</div></article>)}</section>}
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
          <section className="recharge-list"><h3>充值记录</h3>{rechargeRecords.length === 0 ? <p>暂无充值记录。</p> : rechargeRecords.map((record, index) => <article key={`${record.created_at}-${index}`}><div><strong>{record.package_name}</strong><span>{record.status === 'paid' ? '已支付' : record.status === 'fulfilled' ? '已完成' : record.status}</span></div><p>+{record.idea_amount} Idea · +{record.detail_amount} 详细方案</p><small>{new Date(record.created_at).toLocaleString('zh-CN')}{record.paid_at ? ` · 支付时间：${new Date(record.paid_at).toLocaleString('zh-CN')}` : ''}</small><code>¥{(record.amount_fen / 100).toFixed(2)}</code></article>)}</section>
        </>}
      </div>
    </div>
  </section>;
}
