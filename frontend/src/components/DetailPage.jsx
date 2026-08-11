import React from 'react';
import { useApp } from '../context/AppContext';
import { ArrowLeft } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import './DetailPage.css';

const DetailPage = () => {
  const { currentSession, currentIdeaIndex, loadSession, generateDetail } = useApp();
  const [isGenerating, setIsGenerating] = React.useState(false);
  const [detailedPlan, setDetailedPlan] = React.useState('');

  React.useEffect(() => {
    if (currentSession) {
      setDetailedPlan(currentSession.detailedPlan || '');
    }
  }, [currentSession]);

  const handleGenerateDetail = async () => {
    if (!currentSession || currentIdeaIndex === null) return;

    setIsGenerating(true);
    try {
      const plan = await generateDetail(currentSession.id, currentIdeaIndex);
      setDetailedPlan(plan);
    } catch (error) {
      console.error('Failed to generate detail:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  if (!currentSession || currentIdeaIndex === null) {
    return (
      <div className="detail-page empty-state">
        <h2 className="page-title">暂无详情</h2>
        <p className="page-subtitle">请先在生成页面选择 Idea 查看详情</p>
      </div>
    );
  }

  const idea = currentSession.ideas[currentIdeaIndex];

  return (
    <div className="detail-page">
      <div className="detail-header">
        <button className="btn btn-secondary" onClick={() => window.history.back()}>
          <ArrowLeft size={18} />
          返回
        </button>
        <h1 className="page-title">{idea.name}</h1>
        <p className="page-subtitle">{idea.tagline}</p>
      </div>

      <div className="detail-meta">
        <div className="meta-item">
          <strong>评分</strong>
          <span className="score">{idea.score}</span>
        </div>
        <div className="meta-tags">
          {idea.tags.map((tag, i) => (
            <span key={i} className="tag">{tag}</span>
          ))}
        </div>
      </div>

      {!detailedPlan && (
        <button
          className="btn btn-primary btn-large"
          onClick={handleGenerateDetail}
          disabled={isGenerating}
        >
          {isGenerating ? '生成中...' : '生成详细方案'}
        </button>
      )}

      {detailedPlan && (
        <div className="detail-content">
          <ReactMarkdown>{detailedPlan}</ReactMarkdown>
        </div>
      )}
    </div>
  );
};

export default DetailPage;
