import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import { Sparkles, FileText, History, Settings } from 'lucide-react';
import GenerateForm from './GenerateForm';
import ProgressPanel from './ProgressPanel';
import IdeasGrid from './IdeasGrid';
import HistorySection from './HistorySection';
import ConfigPanel from './ConfigPanel';
import './AgentView.css';

const AgentView = () => {
  const [activeTab, setActiveTab] = useState('generate');
  const { ideas, currentSession, isGenerating } = useApp();

  const tabs = [
    { id: 'generate', label: '生成', icon: Sparkles },
    { id: 'detail', label: '详情', icon: FileText, disabled: ideas.length === 0 },
    { id: 'history', label: '历史', icon: History },
    { id: 'settings', label: '设置', icon: Settings },
  ];

  return (
    <div className="agent-view">
      <div className="page-head-bar">
        <div>
          <div className="eyebrow">IDEA GENERATOR</div>
          <h2>Idea Generator</h2>
          <div className="muted">
            输入方向，生成可变现的项目 Ideas，点击下钻查看详细方案
          </div>
        </div>
      </div>

      <div className="editor-tabs">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              className={`tab-button ${activeTab === tab.id ? 'active' : ''} ${tab.disabled ? 'disabled' : ''}`}
              onClick={() => !tab.disabled && setActiveTab(tab.id)}
              disabled={tab.disabled}
            >
              <Icon size={18} style={{ marginRight: 8 }} />
              {tab.label}
            </button>
          );
        })}
      </div>

      <div className="tab-content">
        {activeTab === 'generate' && (
          <div className="generate-panel animate-fade-in">
            <GenerateForm />
            <ProgressPanel />
            {ideas.length > 0 && <IdeasGrid />}
          </div>
        )}

        {activeTab === 'detail' && (
          <div className="detail-panel animate-fade-in">
            <h3>详细方案</h3>
            <p className="panel-description">
              点击 Ideas 卡片查看详细技术方案（功能清单、技术架构、开发路线、成本估算、变现策略、风险评估、PMF 验证）
            </p>
            <IdeasGrid />
          </div>
        )}

        {activeTab === 'history' && (
          <div className="history-panel animate-fade-in">
            <h3>生成历史</h3>
            <p className="panel-description">查看所有历史生成记录</p>
            <HistorySection />
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="settings-panel animate-fade-in">
            <h3>设置</h3>
            <p className="panel-description">配置模型参数和生成选项</p>
            <ConfigPanel />
          </div>
        )}
      </div>
    </div>
  );
};

export default AgentView;
