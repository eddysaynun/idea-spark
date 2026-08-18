import { useEffect, useState } from 'react';
import { ArrowRight, Square, WandSparkles } from 'lucide-react';

import { useApp } from '../context/app-context';
import { clampGenerationCount } from '../utils/quota';
import './GenerateForm.css';

const categories = [
  ['general', '通用产品'],
  ['ai-agent', 'AI Agent'],
  ['dev-tools', '开发者工具'],
  ['privacy', '隐私安全'],
  ['productivity', '效率工具'],
];

const examples = ['独立开发者验证需求', '本地优先的团队知识工具', 'AI 辅助售后工作流'];

const GenerateForm = () => {
  const { availableModels, config, isGenerating, generateIdeas, cancelGeneration, user } = useApp();
  const [direction, setDirection] = useState('');
  const remainingIdeas = user
    ? Math.max(0, user.quota.idea.limit - user.quota.idea.used - user.quota.idea.reserved)
    : 5;
  const [count, setCount] = useState(Math.min(5, remainingIdeas));
  const [category, setCategory] = useState('general');
  const [model, setModel] = useState('');

  useEffect(() => {
    setCount((current) => clampGenerationCount(current, remainingIdeas));
  }, [remainingIdeas]);

  const selectedModel = model || availableModels[0] || config.model || '';

  const submit = (event) => {
    event.preventDefault();
    if (direction.trim().length >= 2 && selectedModel && count >= 1) {
      generateIdeas(direction.trim(), count, category, selectedModel);
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
        <span>描述用户、场景和约束，结果会更具体</span>
        <span>{direction.length}/500</span>
      </div>

      <div className="example-list" aria-label="输入示例">
        {examples.map((example) => (
          <button key={example} type="button" onClick={() => setDirection(example)} disabled={isGenerating}>
            {example}
          </button>
        ))}
      </div>

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

      {!user ? (
        <a className="generate-action" href="/login">登录并领取免费额度 <ArrowRight size={18} /></a>
      ) : isGenerating ? (
        <button type="button" className="generate-action stop" onClick={cancelGeneration}>
          <Square size={16} fill="currentColor" /> 停止生成
        </button>
      ) : (
        remainingIdeas < 1 ? <a className="generate-action" href="/account">Idea 额度已用完，申请增加额度 <ArrowRight size={18} /></a> :
          <button type="submit" className="generate-action" disabled={direction.trim().length < 2 || !selectedModel || count < 1}>
            <WandSparkles size={18} /> 生成 {count} 个候选 <ArrowRight size={18} />
          </button>
      )}
    </form>
  );
};

export default GenerateForm;
