import React from 'react';
import { Sparkles, Zap, TrendingUp, Target } from 'lucide-react';
import './WelcomePage.css';

const WelcomePage = ({ onGetStarted }) => {
  const features = [
    {
      icon: Sparkles,
      title: 'AI 驱动创意',
      description: '基于先进 AI 模型，生成高质量、可变现的项目创意',
      color: 'var(--spark-purple)'
    },
    {
      icon: Zap,
      title: '即时生成',
      description: '实时流式输出，看到 AI 的思考过程和生成内容',
      color: 'var(--spark-orange)'
    },
    {
      icon: TrendingUp,
      title: '痛点导向',
      description: '每个创意都基于真实市场痛点和变现潜力分析',
      color: 'var(--spark-cyan)'
    },
    {
      icon: Target,
      title: '精准定位',
      description: '支持多种分类：AI Agent、开发者工具、隐私安全等',
      color: 'var(--spark-purple)'
    }
  ];

  return (
    <div className="welcome-page">
      <div className="hero-section">
        <div className="hero-badge">
          <Sparkles size={16} />
          <span>AI-Powered Idea Generator</span>
        </div>
        
        <h1 className="hero-title">
          发现下一个
          <span className="highlight">变现项目</span>
        </h1>
        
        <p className="hero-subtitle">
          Idea Spark 使用先进 AI 技术，帮你生成可落地、有市场潜力的项目创意。
          输入方向，立即开始创作之旅。
        </p>

        <div className="hero-actions">
          <button className="btn btn-primary btn-large" onClick={onGetStarted}>
            <Zap size={20} />
            开始生成 Ideas
          </button>
        </div>
      </div>

      <div className="features-section">
        <h2 className="features-title">为什么选择 Idea Spark？</h2>
        
        <div className="features-grid">
          {features.map((feature, index) => (
            <div key={index} className="feature-card">
              <div className="feature-icon" style={{ background: feature.color }}>
                <feature.icon size={24} />
              </div>
              <h3 className="feature-title">{feature.title}</h3>
              <p className="feature-description">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="cta-section">
        <div className="cta-content">
          <h2 className="cta-title">准备好发现下一个爆款项目了吗？</h2>
          <p className="cta-description">
            立即开始，让 AI 帮你挖掘市场机会
          </p>
          <button className="btn btn-primary btn-large" onClick={onGetStarted}>
            <Sparkles size={20} />
            立即开始
          </button>
        </div>
      </div>
    </div>
  );
};

export default WelcomePage;
