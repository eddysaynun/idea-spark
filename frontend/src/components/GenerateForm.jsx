import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import { Sparkles, ArrowRight } from 'lucide-react';
import './GenerateForm.css';

const GenerateForm = () => {
  const { isGenerating, generateIdeas } = useApp();
  const [direction, setDirection] = useState('');
  const [count, setCount] = useState(5);
  const [category, setCategory] = useState('general');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!direction.trim()) {
      alert('请输入项目方向');
      return;
    }
    await generateIdeas(direction, count, category);
  };

  const categories = [
    { value: 'general', label: '通用 ToC', icon: '🎯' },
    { value: 'ai-agent', label: 'AI Agent 工具', icon: '🤖' },
    { value: 'dev-tools', label: '开发者工具', icon: '🛠️' },
    { value: 'privacy', label: '隐私安全', icon: '🔒' },
    { value: 'productivity', label: '效率工具', icon: '⚡' },
  ];

  return (
    <form className="generate-form" onSubmit={handleSubmit}>
      <div className="form-row">
        <div className="form-group form-group-large">
          <label className="form-label">项目方向</label>
          <input
            type="text"
            className="form-input"
            value={direction}
            onChange={(e) => setDirection(e.target.value)}
            placeholder="例如：AI Agent 工具、开发者工具、隐私安全..."
            disabled={isGenerating}
          />
        </div>

        <div className="form-group">
          <label className="form-label">生成数量</label>
          <input
            type="number"
            className="form-input"
            min="1"
            max="50"
            value={count}
            onChange={(e) => setCount(Math.max(1, Math.min(50, Number(e.target.value))))}
            placeholder="1-50"
            disabled={isGenerating}
          />
        </div>
      </div>

      <div className="form-group">
        <label className="form-label">分类选择</label>
        <div className="category-grid">
          {categories.map((cat) => (
            <button
              key={cat.value}
              type="button"
              className={`category-btn ${category === cat.value ? 'active' : ''}`}
              onClick={() => setCategory(cat.value)}
              disabled={isGenerating}
            >
              <span className="category-icon">{cat.icon}</span>
              <span className="category-label">{cat.label}</span>
            </button>
          ))}
        </div>
      </div>

      <button
        type="submit"
        className="btn btn-primary btn-generate"
        disabled={isGenerating || !direction.trim()}
      >
        {isGenerating ? (
          <>
            <span className="spinner"></span>
            生成中...
          </>
        ) : (
          <>
            <Sparkles size={20} />
            生成 Ideas
            <ArrowRight size={20} />
          </>
        )}
      </button>
    </form>
  );
};

export default GenerateForm;
