import { ArrowUpRight, Clock3, Trash2 } from 'lucide-react';

import { useApp } from '../context/app-context';
import './HistoryPage.css';

const HistoryPage = ({ onOpenSession }) => {
  const { sessions, deleteSession, currentSession, importLocalSession, user } = useApp();

  return (
    <div className="content-page history-page">
      <div className="content-heading">
        <p className="eyebrow"><span /> EXPLORATION ARCHIVE</p>
        <h1>历史探索</h1>
        <p>重新打开一次探索，继续比较机会或生成详细方案。</p>
      </div>
      {user && currentSession?.ideas?.length > 0 && !sessions.some((item) => item.id === currentSession.id) && (
        <div className="local-import"><div><strong>发现浏览器中的旧探索</strong><span>确认后导入到你的私有账户历史。</span></div><button onClick={importLocalSession}>导入旧探索</button></div>
      )}

      {sessions.length === 0 ? (
        <div className="page-empty"><Clock3 size={28} /><h2>还没有历史记录</h2><p>完成第一次机会探索后，会话会出现在这里。</p></div>
      ) : (
        <div className="history-list">
          {sessions.map((session) => (
            <article key={session.id}>
              <button className="history-open" onClick={() => onOpenSession(session.id)}>
                <span className="history-date">{new Date(session.created_at).toLocaleString('zh-CN')}</span>
                <strong>{session.direction}</strong>
                <span>{session.count} 个机会 · {session.model || session.category}</span>
                <ArrowUpRight size={18} />
              </button>
              <button className="history-delete" onClick={() => deleteSession(session.id)} aria-label={`删除 ${session.direction}`} title="删除记录">
                <Trash2 size={16} />
              </button>
            </article>
          ))}
        </div>
      )}
    </div>
  );
};

export default HistoryPage;
