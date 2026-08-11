import React from 'react';
import { Brain, FileText, Search, Sparkles, CheckCircle, Zap } from 'lucide-react';
import './ProgressPanel.css';

const ProgressPanel = ({ progress }) => {
  const steps = [
    { id: 1, icon: Brain, label: '分析需求', threshold: 10 },
    { id: 2, icon: FileText, label: '生成 Ideas', threshold: 30 },
    { id: 3, icon: Search, label: '解析结果', threshold: 60 },
    { id: 4, icon: Sparkles, label: '优化完善', threshold: 80 },
    { id: 5, icon: CheckCircle, label: '完成', threshold: 100 },
  ];

  return (
    <div className="progress-panel">
      <div className="progress-header">
        <div className="progress-title">
          <Zap size={24} className="title-icon" />
          <h3>AI Agent 正在工作</h3>
        </div>
        <span className="progress-percent">{progress.percent}%</span>
      </div>

      <div className="progress-bar-container">
        <div 
          className="progress-bar" 
          style={{ width: `${progress.percent}%` }}
        />
      </div>

      <div className="progress-steps">
        {steps.map((step) => {
          const isActive = progress.percent >= step.threshold;
          const isCompleted = progress.percent > step.threshold;
          const Icon = step.icon;

          return (
            <div
              key={step.id}
              className={`progress-step ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}`}
            >
              <div className="step-icon">
                <Icon size={20} />
              </div>
              <div className="step-info">
                <div className="step-label">{step.label}</div>
                {isActive && !isCompleted && (
                  <div className="step-status">进行中...</div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="progress-message">
        {progress.message || '正在处理...'}
      </div>

      {/* Live Preview */}
      {(progress.thinking_preview || progress.content_preview) && (
        <div className="progress-preview">
          <div className="preview-header">
            <Brain size={16} />
            <span>实时输出</span>
          </div>
          <div className="preview-content">
            {progress.thinking_preview && (
              <div className="preview-section">
                <div className="preview-label">🧠 AI 思考</div>
                <div className="preview-text">{progress.thinking_preview}</div>
              </div>
            )}
            {progress.content_preview && (
              <div className="preview-section">
                <div className="preview-label">💬 AI 生成</div>
                <div className="preview-text">{progress.content_preview}</div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default ProgressPanel;
