import { useState } from 'react';
import { ArrowRight, Square, WandSparkles } from 'lucide-react';

import { useApp } from '../context/app-context';
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
  const { availableModels, config, isGenerating, generateIdeas, cancelGeneration } = useApp();
  const [direction, setDirection] = useState('');
  const [count, setCount] = useState(5);
  const [category, setCategory] = useState('general');
  const [model, setModel] = useState('');

  const selectedModel = model || availableModels[0] || config.model || '';

  const submit = (event) => {
    event.preventDefault();
    if (direction.trim().length >= 2 && selectedModel) {
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
          定稿数量
          <select value={count} onChange={(event) => setCount(Number(event.target.value))} disabled={isGenerating}>
            {[3, 5, 8, 12].map((value) => <option key={value} value={value}>{value} 个</option>)}
          </select>
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

      {isGenerating ? (
        <button type="button" className="generate-action stop" onClick={cancelGeneration}>
          <Square size={16} fill="currentColor" /> 停止生成
        </button>
      ) : (
        <button type="submit" className="generate-action" disabled={direction.trim().length < 2 || !selectedModel}>
          <WandSparkles size={18} /> 开始机会探索 <ArrowRight size={18} />
        </button>
      )}
    </form>
  );
};

export default GenerateForm;
