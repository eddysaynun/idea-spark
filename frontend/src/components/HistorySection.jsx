import React from 'react';
import { useApp } from '../context/AppContext';
import { History } from 'lucide-react';
import './HistorySection.css';

const HistorySection = () => {
  const { sessions, loadSession } = useApp();

  if (sessions.length === 0) return null;

  return (
    <div className="history-section">
      <h2>
        <History size={28} style={{ marginRight: 12 }} />
        历史记录
      </h2>
      <div className="history-list">
        {sessions.map((session) => (
          <div
            key={session.id}
            className="history-item"
            onClick={() => loadSession(session.id)}
          >
            <div className="history-info">
              <h4>{session.direction || '未指定方向'}</h4>
              <p>
                {session.category} · {session.count} 个 Ideas
              </p>
            </div>
            <div className="history-date">
              {new Date(session.created_at).toLocaleString('zh-CN')}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default HistorySection;
