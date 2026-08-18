import { useEffect, useState } from 'react';
import { CheckCircle2, CreditCard, Download, Lightbulb, LoaderCircle, ScrollText, Trash2 } from 'lucide-react';

import { accountAPI, billingAPI } from '../api';
import { useApp } from '../context/app-context';
import './AccountPage.css';

const quotaData = (quota) => ({ ...quota, remaining: Math.max(0, quota.limit - quota.used - quota.reserved) });

export default function AccountPage() {
  const { user, refreshUser, logout } = useApp();
  const [packages, setPackages] = useState([]);
  const [orders, setOrders] = useState([]);
  const [channels, setChannels] = useState({});
  const [paymentMode, setPaymentMode] = useState('unavailable');
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [returnOrderId, setReturnOrderId] = useState('');
  const [deletionConfirmation, setDeletionConfirmation] = useState('');

  useEffect(() => {
    Promise.all([billingAPI.packages(), billingAPI.orders()]).then(([packageData, orderData]) => {
      setPackages(packageData.packages);
      setOrders(orderData.orders);
      setChannels(packageData.channels || {});
      setPaymentMode(packageData.payment_mode);
      const parameters = new URLSearchParams(window.location.search);
      if (parameters.get('payment') === 'return' && parameters.get('order_id')) {
        setReturnOrderId(parameters.get('order_id'));
        setMessage('支付已完成，正在确认支付宝到账…');
      }
    }).catch((reason) => setError(reason?.response?.data?.detail || '账户信息加载失败'));
    refreshUser();
  }, [refreshUser]);

  useEffect(() => {
    if (!returnOrderId) return undefined;
    let attempts = 0;
    const checkOrder = async () => {
      attempts += 1;
      try {
        const data = await billingAPI.order(returnOrderId);
        setOrders((current) => current.map((item) => item.id === data.order.id ? data.order : item));
        if (data.order.status === 'paid') {
          window.clearInterval(timer);
          setMessage('支付宝到账成功，额度已自动发放。');
          setReturnOrderId('');
          window.history.replaceState({}, '', '/account');
          await refreshUser();
        } else if (!['pending', 'created'].includes(data.order.status)) {
          window.clearInterval(timer);
          setReturnOrderId('');
          setError('该支付订单未完成，请重新选择额度包。');
        } else if (attempts >= 20) {
          window.clearInterval(timer);
          setMessage('支付宝仍在确认到账，稍后刷新本页即可查看结果。');
        }
      } catch { /* 网络波动时继续有限轮询 */ }
    };
    const timer = window.setInterval(checkOrder, 3000);
    checkOrder();
    return () => window.clearInterval(timer);
  }, [returnOrderId, refreshUser]);

  if (!user) return <section className="account-page"><p>请先登录后查看账户。</p></section>;
  const idea = quotaData(user.quota.idea);
  const detail = quotaData(user.quota.detail);

  const startPayment = async (packageId, channel) => {
    setBusy(`${packageId}-${channel}`); setMessage(''); setError('');
    try {
      const data = await billingAPI.createOrder(packageId, channel);
      setOrders((current) => [data.order, ...current]);
      window.location.assign(data.order.pay_url);
    } catch (reason) { setError(reason?.response?.data?.detail || '支付订单创建失败'); }
    finally { setBusy(''); }
  };

  const requestDeletion = async () => {
    if (deletionConfirmation !== '注销我的账号') return;
    setBusy('deletion'); setError('');
    try {
      const data = await accountAPI.requestDeletion(deletionConfirmation);
      await logout();
      window.location.replace(`/login?deletion_due_at=${encodeURIComponent(data.deletion_due_at)}`);
    } catch (reason) {
      setError(reason?.response?.data?.detail || '注销申请失败');
      setBusy('');
    }
  };

  return <section className="account-page">
    <header className="account-title"><span>ACCOUNT & CREDITS</span><h1>{user.display_name} 的账户</h1><p>{user.login}</p></header>
    <div className="credit-overview"><CreditCard size={23} /><div><strong>{idea.remaining + detail.remaining}</strong><span>当前可用权益</span></div><p>额度由服务端账本记录，生成失败会自动退回预占。</p></div>
    <div className="quota-cards"><QuotaCard icon={Lightbulb} title="Idea 候选" quota={idea} /><QuotaCard icon={ScrollText} title="详细方案" quota={detail} /></div>
    <section className="package-section">
      <div className="package-heading"><div><span>TOP UP</span><h2>增加创作额度</h2></div><p>{paymentMode === 'online' ? '前往支付宝安全收银台。服务端验签确认到账后，额度自动发放。' : '支付宝自动支付正在配置中，配置完成前不会创建订单或扣款。'}</p></div>
      <div className="package-grid">{packages.map((item) => <article key={item.id}>
        <span>{item.name}</span><strong>+{item.idea_amount} Idea</strong><p>包含 {item.detail_amount} 份详细方案</p><b>¥{(item.amount_fen / 100).toFixed(0)}</b>
        <div className="pay-actions">{Object.entries(channels).map(([channel, state]) => <button key={channel} className="alipay-button" onClick={() => startPayment(item.id, channel)} disabled={!state.configured || busy === `${item.id}-${channel}`} title={state.configured ? `使用${state.name}` : `${state.name}自动支付配置中`}>{busy === `${item.id}-${channel}` ? <LoaderCircle className="spin" size={16} /> : <AlipayMark />}{state.configured ? state.name : `${state.name}配置中`}</button>)}</div>
      </article>)}</div>
      {message && <p className="account-message"><CheckCircle2 size={16} />{message}</p>}
      {error && <p className="account-error" role="alert">{error}</p>}
    </section>
    {orders.length > 0 && <section className="request-history"><h2>支付订单</h2>{orders.map((item) => <div key={item.id}><span>{new Date(item.created_at).toLocaleString('zh-CN')}</span><strong>{item.package_name} · ¥{(item.amount_fen / 100).toFixed(2)} · 支付宝</strong><em className={item.status}>{item.status === 'paid' ? '已到账' : item.status === 'pending' ? '待支付' : item.status === 'expired' ? '已过期' : item.status}</em></div>)}</section>}
    <section className="account-data"><div><h2>数据与账号</h2><p>你可以随时导出账户数据。注销申请有 7 天冷静期，期满后生成内容永久删除。</p></div><button onClick={() => window.location.assign('/api/account/export')}><Download size={16} /> 导出数据</button></section>
    <section className="account-danger"><div><h2>注销账号</h2><p>提交后立即退出，7 天内重新验证身份可恢复。请输入“注销我的账号”确认。</p></div><input value={deletionConfirmation} onChange={(event) => setDeletionConfirmation(event.target.value)} placeholder="注销我的账号" /><button onClick={requestDeletion} disabled={busy === 'deletion' || deletionConfirmation !== '注销我的账号'}>{busy === 'deletion' ? <LoaderCircle className="spin" size={16} /> : <Trash2 size={16} />} 提交注销</button></section>
  </section>;
}

const AlipayMark = () => <svg className="alipay-mark" viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="16" fill="#1677ff" /><path fill="white" d="M23.8 19.7c-1.7-.6-3.9-1.4-6.4-2.1.6-1.1 1.1-2.4 1.4-3.8h-3.4v-1.2h4.1v-1.4h-4.1V9.1h-2v2.1H9.5v1.4h3.9v1.2h-3.2v1.4h6.2c-.3.7-.6 1.3-1 1.9-4.1-1-6.8-.7-8 .8-1.8 2.2.3 5.1 3.9 5.1 2.4 0 4.6-1.3 6.2-3.4 2.4 1.1 7.1 3 7.1 3l.8-2s-.6-.3-1.6-.7Zm-12.7 1.4c-2.8 0-3.6-2-2.5-3 1-.9 2.9-.8 5.9 0-1 1.8-2.2 3-3.4 3Z" /></svg>;

const QuotaCard = ({ icon: Icon, title, quota }) => <article className="quota-card"><div className="quota-card-title"><Icon size={19} /><span>{title}</span><strong>{quota.remaining}</strong></div><div className="quota-bar"><i style={{ width: `${quota.limit ? Math.min(100, ((quota.used + quota.reserved) / quota.limit) * 100) : 0}%` }} /></div><dl><div><dt>总额</dt><dd>{quota.limit}</dd></div><div><dt>已用</dt><dd>{quota.used}</dd></div><div><dt>处理中</dt><dd>{quota.reserved}</dd></div><div><dt>剩余</dt><dd>{quota.remaining}</dd></div></dl></article>;
