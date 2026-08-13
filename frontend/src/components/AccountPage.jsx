import { useEffect, useState } from 'react';
import { ArrowUpRight, CheckCircle2, Clock3, CreditCard, Lightbulb, ScrollText } from 'lucide-react';

import { billingAPI } from '../api';
import { useApp } from '../context/app-context';
import './AccountPage.css';

const quotaData = (quota) => ({
  ...quota,
  remaining: Math.max(0, quota.limit - quota.used - quota.reserved),
});

export default function AccountPage() {
  const { user, refreshUser } = useApp();
  const [packages, setPackages] = useState([]);
  const [requests, setRequests] = useState([]);
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([billingAPI.packages(), billingAPI.requests()]).then(([packageData, requestData]) => {
      setPackages(packageData.packages);
      setRequests(requestData.requests);
    }).catch((reason) => setError(reason?.response?.data?.detail || '账户信息加载失败'));
    refreshUser();
  }, [refreshUser]);

  if (!user) return <section className="account-page"><p>请先登录后查看账户。</p></section>;
  const idea = quotaData(user.quota.idea);
  const detail = quotaData(user.quota.detail);
  const pending = new Set(requests.filter((item) => item.status === 'pending').map((item) => item.package_id));

  const requestPackage = async (packageId) => {
    setBusy(packageId); setMessage(''); setError('');
    try {
      const data = await billingAPI.requestPackage(packageId);
      setRequests((current) => current.some((item) => item.id === data.request.id) ? current : [data.request, ...current]);
      setMessage('购买申请已提交。管理员确认付款方式后会为你的账户增加额度。');
    } catch (reason) { setError(reason?.response?.data?.detail || '购买申请提交失败'); }
    finally { setBusy(''); }
  };

  return <section className="account-page">
    <header className="account-title"><span>ACCOUNT & CREDITS</span><h1>{user.display_name} 的账户</h1><p>{user.login}</p></header>
    <div className="credit-overview">
      <CreditCard size={23} />
      <div><strong>{idea.remaining + detail.remaining}</strong><span>当前可用权益</span></div>
      <p>额度由服务端账本记录，生成失败会自动退回预占。</p>
    </div>
    <div className="quota-cards">
      <QuotaCard icon={Lightbulb} title="Idea 候选" quota={idea} />
      <QuotaCard icon={ScrollText} title="详细方案" quota={detail} />
    </div>
    <section className="package-section">
      <div className="package-heading"><div><span>TOP UP</span><h2>增加创作额度</h2></div><p>在线支付尚未开放。提交后由管理员联系确认付款方式，不会自动扣款。</p></div>
      <div className="package-grid">{packages.map((item) => <article key={item.id}>
        <span>{item.name}</span><strong>+{item.idea_amount} Idea</strong><p>包含 {item.detail_amount} 份详细方案</p>
        <button onClick={() => requestPackage(item.id)} disabled={busy === item.id || pending.has(item.id)}>{pending.has(item.id) ? <><Clock3 size={16} /> 等待处理</> : <>申请购买 <ArrowUpRight size={16} /></>}</button>
      </article>)}</div>
      {message && <p className="account-message"><CheckCircle2 size={16} />{message}</p>}
      {error && <p className="account-error" role="alert">{error}</p>}
    </section>
    {requests.length > 0 && <section className="request-history"><h2>购买申请</h2>{requests.map((item) => <div key={item.id}><span>{new Date(item.created_at).toLocaleString('zh-CN')}</span><strong>{item.package_id} · {item.idea_amount} Idea / {item.detail_amount} 方案</strong><em className={item.status}>{item.status === 'pending' ? '待处理' : item.status === 'fulfilled' ? '已完成' : '已取消'}</em></div>)}</section>}
  </section>;
}

const QuotaCard = ({ icon: Icon, title, quota }) => <article className="quota-card">
  <div className="quota-card-title"><Icon size={19} /><span>{title}</span><strong>{quota.remaining}</strong></div>
  <div className="quota-bar"><i style={{ width: `${quota.limit ? Math.min(100, ((quota.used + quota.reserved) / quota.limit) * 100) : 0}%` }} /></div>
  <dl><div><dt>总额</dt><dd>{quota.limit}</dd></div><div><dt>已用</dt><dd>{quota.used}</dd></div><div><dt>处理中</dt><dd>{quota.reserved}</dd></div><div><dt>剩余</dt><dd>{quota.remaining}</dd></div></dl>
</article>;
