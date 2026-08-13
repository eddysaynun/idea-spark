import { useEffect, useState } from 'react';
import { CheckCircle2, CreditCard, Lightbulb, LoaderCircle, ScrollText, X } from 'lucide-react';
import QRCode from 'qrcode';

import { billingAPI } from '../api';
import { useApp } from '../context/app-context';
import './AccountPage.css';

const quotaData = (quota) => ({ ...quota, remaining: Math.max(0, quota.limit - quota.used - quota.reserved) });

export default function AccountPage() {
  const { user, refreshUser } = useApp();
  const [packages, setPackages] = useState([]);
  const [orders, setOrders] = useState([]);
  const [channels, setChannels] = useState({});
  const [paymentMode, setPaymentMode] = useState('manual_review');
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [checkout, setCheckout] = useState(null);
  const [qrDataUrl, setQrDataUrl] = useState('');

  useEffect(() => {
    Promise.all([billingAPI.packages(), billingAPI.orders()]).then(([packageData, orderData]) => {
      setPackages(packageData.packages);
      setOrders(orderData.orders);
      setChannels(packageData.channels || {});
      setPaymentMode(packageData.payment_mode);
    }).catch((reason) => setError(reason?.response?.data?.detail || '账户信息加载失败'));
    refreshUser();
  }, [refreshUser]);

  useEffect(() => {
    if (!checkout?.pay_url) { setQrDataUrl(''); return undefined; }
    QRCode.toDataURL(checkout.pay_url, { width: 288, margin: 1, errorCorrectionLevel: 'M' })
      .then(setQrDataUrl).catch(() => setError('支付二维码生成失败，请关闭后重试'));
    if (checkout.status !== 'pending') return undefined;
    const timer = window.setInterval(async () => {
      try {
        const data = await billingAPI.order(checkout.id);
        setCheckout(data.order);
        setOrders((current) => current.map((item) => item.id === data.order.id ? data.order : item));
        if (data.order.status === 'paid') {
          window.clearInterval(timer);
          setMessage('支付宝到账成功，额度已自动发放。');
          await refreshUser();
        }
      } catch { /* 网络波动时保留二维码并继续轮询 */ }
    }, 3000);
    return () => window.clearInterval(timer);
  }, [checkout?.id, checkout?.pay_url, checkout?.status, refreshUser]);

  if (!user) return <section className="account-page"><p>请先登录后查看账户。</p></section>;
  const idea = quotaData(user.quota.idea);
  const detail = quotaData(user.quota.detail);

  const startPayment = async (packageId, channel) => {
    setBusy(`${packageId}-${channel}`); setMessage(''); setError('');
    try {
      const data = await billingAPI.createOrder(packageId, channel);
      setOrders((current) => [data.order, ...current]);
      setCheckout(data.order);
    } catch (reason) { setError(reason?.response?.data?.detail || '支付订单创建失败'); }
    finally { setBusy(''); }
  };

  return <section className="account-page">
    <header className="account-title"><span>ACCOUNT & CREDITS</span><h1>{user.display_name} 的账户</h1><p>{user.login}</p></header>
    <div className="credit-overview"><CreditCard size={23} /><div><strong>{idea.remaining + detail.remaining}</strong><span>当前可用权益</span></div><p>额度由服务端账本记录，生成失败会自动退回预占。</p></div>
    <div className="quota-cards"><QuotaCard icon={Lightbulb} title="Idea 候选" quota={idea} /><QuotaCard icon={ScrollText} title="详细方案" quota={detail} /></div>
    <section className="package-section">
      <div className="package-heading"><div><span>TOP UP</span><h2>增加创作额度</h2></div><p>{paymentMode === 'online' ? '支付宝扫码支付。服务端验签确认到账后，额度自动发放。' : '支付宝自动支付正在配置中，配置完成前不会创建订单或扣款。'}</p></div>
      <div className="package-grid">{packages.map((item) => <article key={item.id}>
        <span>{item.name}</span><strong>+{item.idea_amount} Idea</strong><p>包含 {item.detail_amount} 份详细方案</p><b>¥{(item.amount_fen / 100).toFixed(0)}</b>
        <div className="pay-actions">{Object.entries(channels).map(([channel, state]) => <button key={channel} className="alipay-button" onClick={() => startPayment(item.id, channel)} disabled={!state.configured || busy === `${item.id}-${channel}`} title={state.configured ? `使用${state.name}` : `${state.name}自动支付配置中`}>{busy === `${item.id}-${channel}` ? <LoaderCircle className="spin" size={16} /> : <AlipayMark />}{state.configured ? state.name : `${state.name}配置中`}</button>)}</div>
      </article>)}</div>
      {message && <p className="account-message"><CheckCircle2 size={16} />{message}</p>}
      {error && <p className="account-error" role="alert">{error}</p>}
    </section>
    {orders.length > 0 && <section className="request-history"><h2>支付订单</h2>{orders.map((item) => <div key={item.id}><span>{new Date(item.created_at).toLocaleString('zh-CN')}</span><strong>{item.package_name} · ¥{(item.amount_fen / 100).toFixed(2)} · 支付宝</strong><em className={item.status}>{item.status === 'paid' ? '已到账' : item.status === 'pending' ? '待支付' : item.status === 'expired' ? '已过期' : item.status}</em></div>)}</section>}
    {checkout && <Checkout order={checkout} qrDataUrl={qrDataUrl} onClose={() => setCheckout(null)} />}
  </section>;
}

const Checkout = ({ order, qrDataUrl, onClose }) => <div className="checkout-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><section className="checkout-dialog" role="dialog" aria-modal="true" aria-labelledby="checkout-title"><button className="checkout-close" onClick={onClose} aria-label="关闭支付窗口"><X size={18} /></button>{order.status === 'paid' ? <div className="checkout-success"><CheckCircle2 size={42} /><h2 id="checkout-title">支付成功</h2><p>额度已经自动到账，可以继续生成 Idea。</p><button onClick={onClose}>完成</button></div> : <><div className="checkout-brand"><AlipayMark /><span>支付宝安全支付</span></div><h2 id="checkout-title">扫码支付 ¥{(order.amount_fen / 100).toFixed(2)}</h2><p>{order.package_name} · {order.idea_amount} Idea + {order.detail_amount} 份详细方案</p><div className="checkout-qr">{qrDataUrl ? <img src={qrDataUrl} alt="支付宝动态付款二维码" /> : <LoaderCircle className="spin" size={28} />}</div><a className="checkout-open" href={`alipays://platformapi/startapp?appId=20000067&url=${encodeURIComponent(order.pay_url)}`}>在支付宝中打开</a><small>二维码 15 分钟内有效。支付结果由服务端验签确认，请勿重复付款。</small><span className="checkout-wait"><i /> 正在等待支付宝到账…</span></>}</section></div>;

const AlipayMark = () => <svg className="alipay-mark" viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="16" fill="#1677ff" /><path fill="white" d="M23.8 19.7c-1.7-.6-3.9-1.4-6.4-2.1.6-1.1 1.1-2.4 1.4-3.8h-3.4v-1.2h4.1v-1.4h-4.1V9.1h-2v2.1H9.5v1.4h3.9v1.2h-3.2v1.4h6.2c-.3.7-.6 1.3-1 1.9-4.1-1-6.8-.7-8 .8-1.8 2.2.3 5.1 3.9 5.1 2.4 0 4.6-1.3 6.2-3.4 2.4 1.1 7.1 3 7.1 3l.8-2s-.6-.3-1.6-.7Zm-12.7 1.4c-2.8 0-3.6-2-2.5-3 1-.9 2.9-.8 5.9 0-1 1.8-2.2 3-3.4 3Z" /></svg>;

const QuotaCard = ({ icon: Icon, title, quota }) => <article className="quota-card"><div className="quota-card-title"><Icon size={19} /><span>{title}</span><strong>{quota.remaining}</strong></div><div className="quota-bar"><i style={{ width: `${quota.limit ? Math.min(100, ((quota.used + quota.reserved) / quota.limit) * 100) : 0}%` }} /></div><dl><div><dt>总额</dt><dd>{quota.limit}</dd></div><div><dt>已用</dt><dd>{quota.used}</dd></div><div><dt>处理中</dt><dd>{quota.reserved}</dd></div><div><dt>剩余</dt><dd>{quota.remaining}</dd></div></dl></article>;
