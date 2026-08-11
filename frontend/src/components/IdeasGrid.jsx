import React from 'react';
import { useApp } from '../context/AppContext';
import { Star, Zap, TrendingUp } from 'lucide-react';
import './IdeasGrid.css';

const IdeasGrid = ({ ideas }) => {
  const { currentSession, getDetail } = useApp();

  const handleCardClick = async (index) => {
    if (!currentSession) return;
    const data = await getDetail(currentSession, index);
    if (data?.success) {
      console.log('Detail:', data);
    }
  };

  if (!ideas || ideas.length === 0) return null;

  return (
    <div className="ideas-grid">
      {ideas.map((idea, index) => (
        <div
          key={index}
          className="idea-card card-idea"
          onClick={() => handleCardClick(index)}
        >
          <div className="idea-rank">#{index + 1}</div>
          
          <div className="idea-header">
            <h3 className="idea-name">{idea.name || `项目 ${index + 1}`}</h3>
            <div className="idea-score">
              <Star size={16} fill="currentColor" />
              <span>{idea.score || '8.5'}</span>
            </div>
          </div>

          <p className="idea-tagline">{idea.tagline || '点击查看详细描述'}</p>

          <div className="idea-pain-point">
            <TrendingUp size={16} />
            <span>{idea.pain_point || idea.solution || 'N/A'}</span>
          </div>

          <div className="idea-tags">
            {(idea.tags || ['可变现', '痛点驱动']).slice(0, 4).map((tag, i) => (
              <span key={i} className="tag">
                {tag}
              </span>
            ))}
          </div>

          <div className="idea-footer">
            <Zap size={16} />
            点击查看详情
          </div>
        </div>
      ))}
    </div>
  );
};

export default IdeasGrid;
