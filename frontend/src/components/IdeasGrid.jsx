import { ArrowUpRight, CircleAlert, Gauge, Radar } from 'lucide-react';

import './IdeasGrid.css';

const confidenceLabel = { low: '低置信', medium: '中置信', high: '高置信' };

const IdeasGrid = ({ ideas, onOpenIdea }) => (
  <div className="ideas-list">
    {ideas.map((idea, index) => (
      <button className="idea-row" key={`${idea.name}-${index}`} onClick={() => onOpenIdea(index)}>
        <span className="idea-number">{String(index + 1).padStart(2, '0')}</span>
        <span className="idea-main">
          <span className="idea-title-line">
            <strong>{idea.name}</strong>
            <span className={`confidence ${idea.confidence || 'medium'}`}>{confidenceLabel[idea.confidence] || '待评估'}</span>
          </span>
          <span className="idea-tagline">{idea.tagline}</span>
          <span className="idea-evidence">
            <Radar size={14} /> {idea.evidence?.[0] || '需要补充外部证据信号'}
          </span>
          <span className="idea-tags">
            {(idea.tags || []).slice(0, 3).map((tag) => <span key={tag}>{tag}</span>)}
          </span>
        </span>
        <span className="idea-metrics">
          <span><Gauge size={15} /> {Number(idea.score || 0).toFixed(1)}</span>
          <span><CircleAlert size={15} /> {idea.risks?.length || 0} 风险</span>
        </span>
        <ArrowUpRight className="idea-open" size={18} />
      </button>
    ))}
  </div>
);

export default IdeasGrid;
