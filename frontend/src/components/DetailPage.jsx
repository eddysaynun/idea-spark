import { useEffect, useState } from 'react';
import { ArrowLeft, CheckCircle2, LoaderCircle, ShieldAlert } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

import { useApp } from '../context/app-context';
import './DetailPage.css';

const DetailPage = ({ onBack }) => {
  const { currentSession, currentIdeaIndex, generateDetail, user } = useApp();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const idea = currentSession?.ideas?.[currentIdeaIndex];
  const cachedPlan = currentSession?.detailed_plans?.[currentIdeaIndex] || '';
  const [plan, setPlan] = useState(cachedPlan);
  const remainingDetails = user
    ? Math.max(0, user.quota.detail.limit - user.quota.detail.used - user.quota.detail.reserved)
    : 0;

  useEffect(() => setPlan(cachedPlan), [cachedPlan]);

  const createPlan = async () => {
    setLoading(true);
    setError('');
    try {
      const result = await generateDetail();
      if (!result) throw new Error('模型没有返回详细方案');
      setPlan(result);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  if (!idea) return <div className="page-empty"><h2>没有选中的机会</h2><button className="text-button" onClick={onBack}>返回工作台</button></div>;

  return (
    <div className="detail-page">
      <button className="back-button" onClick={onBack}><ArrowLeft size={17} /> 返回候选列表</button>
      <header className="detail-hero">
        <div>
          <p className="eyebrow"><span /> OPPORTUNITY BRIEF</p>
          <h1>{idea.name}</h1>
          <p>{idea.tagline}</p>
        </div>
        <div className="score-card"><span>综合评分</span><strong>{Number(idea.score).toFixed(1)}</strong><small>/ 10</small></div>
      </header>

      <div className="detail-grid">
        <section className="brief-main">
          <BriefBlock title="真实痛点" content={idea.pain_point} />
          <BriefBlock title="解决方案" content={idea.solution} />
          <div className="brief-pair"><BriefBlock title="目标用户" content={idea.target_user} /><BriefBlock title="收费假设" content={idea.pricing} /></div>
          <div className="brief-pair"><BriefBlock title="市场空间" content={idea.market_size} /><BriefBlock title="收入假设" content={idea.revenue} /></div>
          <BriefBlock title="技术与差异化" content={`${idea.tech_stack}。${idea.advantage}`} />
        </section>
        <aside className="evidence-panel">
          <SignalList icon={CheckCircle2} title="证据信号 / 验证路径" items={idea.evidence} />
          <SignalList icon={ShieldAlert} title="关键假设" items={idea.assumptions} />
          <SignalList icon={ShieldAlert} title="主要风险" items={idea.risks} danger />
          <p className="trust-note">以上为模型分析，不等同于已验证市场事实。建议访谈目标用户并核验竞品与市场数据。</p>
        </aside>
      </div>

      <section className="plan-section">
        <div><p className="panel-index">DEEP DIVE</p><h2>落地方案</h2></div>
        {!plan && <button className="generate-action" onClick={createPlan} disabled={loading || remainingDetails < 1}>{loading ? <LoaderCircle className="spin" size={18} /> : null}{loading ? '正在深化…' : remainingDetails < 1 ? '免费详细方案额度已用完' : `生成详细落地方案（剩余 ${remainingDetails} 次）`}</button>}
        {error && <div className="inline-error" role="alert">{error}</div>}
        {plan && <article className="markdown"><ReactMarkdown>{plan}</ReactMarkdown></article>}
      </section>
    </div>
  );
};

const BriefBlock = ({ title, content }) => <div className="brief-block"><h3>{title}</h3><p>{content || '待补充'}</p></div>;
const SignalList = ({ icon: Icon, title, items = [], danger = false }) => (
  <section className={danger ? 'signal-list danger' : 'signal-list'}><h3><Icon size={16} /> {title}</h3><ul>{items.length ? items.map((item) => <li key={item}>{item}</li>) : <li>暂无，建议优先补充</li>}</ul></section>
);

export default DetailPage;
