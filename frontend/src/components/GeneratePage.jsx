import React from 'react';
import { useApp } from '../context/AppContext';
import { Sparkles, Zap, Lightbulb } from 'lucide-react';
import GenerateForm from './GenerateForm';
import IdeasGrid from './IdeasGrid';
import ProgressPanel from './ProgressPanel';
import './GeneratePage.css';

const GeneratePage = () => {
  const { isGenerating, progress, ideas } = useApp();

  return (
    <div className="generate-page">
      {/* Hero Section */}
      <div className="page-header">
        <div className="hero-icon">
          <Sparkles size={48} />
        </div>
        <h1 className="page-title">生成变现 Ideas</h1>
        <p className="page-subtitle">
          输入你的方向，AI 将为你生成可落地的项目创意
        </p>
      </div>

      {/* Generate Form */}
      <div className="generate-section">
        <GenerateForm />
      </div>

      {/* Progress Panel */}
      {isGenerating && (
        <div className="progress-section">
          <ProgressPanel progress={progress} />
        </div>
      )}

      {/* Ideas Grid */}
      {ideas.length > 0 && !isGenerating && (
        <div className="ideas-section">
          <div className="section-header">
            <Lightbulb size={24} className="section-icon" />
            <h2 className="section-title">生成的 Ideas ({ideas.length})</h2>
            <div className="section-badge">
              <Zap size={16} />
              点击查看详情
            </div>
          </div>
          <IdeasGrid ideas={ideas} />
        </div>
      )}

      {/* Empty State */}
      {!isGenerating && ideas.length === 0 && (
        <div className="empty-state">
          <div className="empty-icon">
            <Lightbulb size={64} />
          </div>
          <h3 className="empty-title">还没有生成 Ideas</h3>
          <p className="empty-description">
            在上方表单中输入方向，点击"生成 Ideas"开始创作
          </p>
        </div>
      )}
    </div>
  );
};

export default GeneratePage;
