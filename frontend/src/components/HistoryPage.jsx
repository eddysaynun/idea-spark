import React from 'react';
import { useApp } from '../context/AppContext';
import { Clock } from 'lucide-react';
import './HistoryPage.css';

const HistoryPage = () => {
  const { sessions, loadSession } = useApp();

  if (sessions.length === 0) {
    return (
      <div className="history-page empty-state">
        <h2 className="page-title">暂无历史记录</h2>
        <p className="page-subtitle">生成的 Ideas 会保存在这里</p>
      </div>
    );
  }

  return (
    <div className="history-page">
      <div className="page-header">
        <h1 className="page-title">历史记录</h1>
        <p className="page-subtitle">查看你之前生成的 Ideas</p>
      </div>

      <div className="history-list">
        {sessions.map((session) => (
          <div
            key={session.id}
            className="history-card"
            onClick={() => loadSession(session.id)}
          >
            <div className="history-info">
              <h3>{session.direction}</h3>
              <p>{session.count} 个 Ideas • {session.category}</p>
            </div>
            <div className="history-meta">
              <span className="history-date">
                <Clock size={14} />
                {new Date(session.created_at).toLocaleString('zh-CN')}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default HistoryPage;
