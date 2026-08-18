import { useEffect, useState } from 'react';
import { ArrowRight, ChevronDown, Square, WandSparkles } from 'lucide-react';

import { useApp } from '../context/app-context';
import { buildExplorationBrief } from '../utils/generate-workbench';
import { clampGenerationCount } from '../utils/quota';
import './GenerateForm.css';

const categories = [
  ['general', '通用产品'],
  ['ai-agent', 'AI Agent'],
  ['dev-tools', '开发者工具'],
  ['privacy', '隐私安全'],
  ['productivity', '效率工具'],
];

const templates = [
  {
    label: '验证付费需求',
    direction: '帮助独立开发者在开发前验证真实付费需求',
    audience: '准备启动新产品的独立开发者',
    scenario: '投入开发前的两周验证期',
    constraints: '低预算、单人可执行、不依赖大规模投放',
  },
  {
    label: '团队知识工具',
    direction: '探索本地优先的团队知识管理产品机会',
    audience: '重视数据控制的 10–50 人团队',
    scenario: '会议、文档和项目知识分散时',
    constraints: '中国大陆可用、迁移成本低、默认保护隐私',
  },
  {
    label: 'AI 售后工作流',
    direction: '减少电商售后团队处理重复问题的时间',
    audience: '每天处理大量咨询的中小电商团队',
    scenario: '退款、物流和商品问题集中出现时',
    constraints: '人工可接管、回答可追溯、两周内可上线 MVP',
  },
];

const GenerateForm = () => {
  const { availableModels, isGenerating, generateIdeas, cancelGeneration, user } = useApp();
  const [direction, setDirection] = useState('');
  const remainingIdeas = user
    ? Math.max(0, user.quota.idea.limit - user.quota.idea.used - user.quota.idea.reserved)
    : 5;
  const [count, setCount] = useState(Math.min(5, remainingIdeas));
  const [category, setCategory] = useState('general');
  const [model, setModel] = useState('');
  const [audience, setAudience] = useState('');
  const [scenario, setScenario] = useState('');
  const [constraints, setConstraints] = useState('');

  useEffect(() => {
    setCount((current) => clampGenerationCount(current, remainingIdeas));
  }, [remainingIdeas]);

  const selectedModel = model || availableModels[0] || '';
  const brief = buildExplorationBrief({ direction, audience, scenario, constraints });
  const briefTooLong = brief.length > 500;

  const applyTemplate = (template) => {
    setDirection(template.direction);
    setAudience(template.audience);
    setScenario(template.scenario);
    setConstraints(template.constraints);
  };

  const submit = (event) => {
    event.preventDefault();
    if (brief.length >= 2 && !briefTooLong && selectedModel && count >= 1) {
      generateIdeas(brief, count, category, selectedModel);
    }
  };

  return (
    <form className="generate-form" onSubmit={submit}>
      <label htmlFor="direction">你想探索什么问题？</label>
      <textarea
        id="direction"
        value={direction}
        onChange={(event) => setDirection(event.target.value)}
        placeholder="例如：帮助独立开发者更快验证真实付费需求"
        rows={5}
        maxLength={500}
        disabled={isGenerating}
      />
      <div className="field-meta">
        <span>先写清问题，再按需补充探索边界</span>
        <span className={briefTooLong ? 'over-limit' : ''}>{brief.length}/500</span>
      </div>

      <div className="template-list" aria-label="探索 Brief 模板">
        <span>快速开始</span>
        {templates.map((template) => (
          <button key={template.label} type="button" onClick={() => applyTemplate(template)} disabled={isGenerating}>
            {template.label}
          </button>
        ))}
      </div>

      <details className="brief-boundaries">
        <summary><span>补充探索边界</span><small>可选，但能减少空泛结果</small><ChevronDown size={15} /></summary>
        <div className="boundary-fields">
          <label>
            目标用户
            <input value={audience} onChange={(event) => setAudience(event.target.value)} placeholder="谁最需要它？" maxLength={120} disabled={isGenerating} />
          </label>
          <label>
            使用场景
            <input value={scenario} onChange={(event) => setScenario(event.target.value)} placeholder="问题在什么时候发生？" maxLength={120} disabled={isGenerating} />
          </label>
          <label>
            关键约束
            <input value={constraints} onChange={(event) => setConstraints(event.target.value)} placeholder="预算、团队、地区或时间限制" maxLength={120} disabled={isGenerating} />
          </label>
        </div>
      </details>

      {briefTooLong && <p className="brief-warning" role="alert">完整 Brief 超过 500 字，请精简主问题或探索边界。</p>}

      <div className="form-split">
        <label>
          分类
          <select value={category} onChange={(event) => setCategory(event.target.value)} disabled={isGenerating}>
            {categories.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label>
          生成数量
          <input
            type="number"
            min={1}
            max={remainingIdeas}
            value={count}
            onChange={(event) => setCount(clampGenerationCount(event.target.value, remainingIdeas))}
            disabled={isGenerating}
          />
        </label>
      </div>

      <label className="model-field">
        本次使用模型
        <select value={selectedModel} onChange={(event) => setModel(event.target.value)} disabled={isGenerating || !selectedModel}>
          {availableModels.length ? availableModels.map((name) => (
            <option key={name} value={name}>{name}</option>
          )) : <option value={selectedModel}>{selectedModel || '请先在模型设置中完成配置'}</option>}
        </select>
      </label>

      <div className="generation-receipt" aria-label="本次生成摘要">
        <div><span>本次产出</span><strong>{count || 0} 个候选</strong></div>
        <div><span>预计消耗</span><strong>{count || 0} Idea 额度</strong></div>
        <div><span>完成后剩余</span><strong>{Math.max(0, remainingIdeas - count)}</strong></div>
        <div><span>评审模型</span><strong title={selectedModel}>{selectedModel || '等待配置'}</strong></div>
      </div>

      {!user ? (
        <a className="generate-action" href="/login">登录并领取免费额度 <ArrowRight size={18} /></a>
      ) : isGenerating ? (
        <button type="button" className="generate-action stop" onClick={cancelGeneration}>
          <Square size={16} fill="currentColor" /> 停止生成
        </button>
      ) : (
        remainingIdeas < 1 ? <a className="generate-action" href="/account">Idea 额度已用完，申请增加额度 <ArrowRight size={18} /></a> :
          <button type="submit" className="generate-action" disabled={brief.length < 2 || briefTooLong || !selectedModel || count < 1}>
            <WandSparkles size={18} /> 生成 {count} 个候选 <ArrowRight size={18} />
          </button>
      )}
    </form>
  );
};

export default GenerateForm;
