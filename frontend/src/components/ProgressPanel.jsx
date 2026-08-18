import { useEffect, useState } from 'react';
import { Check, Circle, LoaderCircle } from 'lucide-react';

import { formatElapsed } from '../utils/generate-workbench';
import './ProgressPanel.css';

const stages = [
  { label: '机会探索', detail: '扩展不同用户与场景', threshold: 10 },
  { label: '批判评估', detail: '检查差异、风险与证据', threshold: 48 },
  { label: '结构化定稿', detail: '去重并整理可比较结果', threshold: 76 },
];

const ProgressPanel = ({ progress }) => {
  const [elapsed, setElapsed] = useState(0);
  const activeIndex = progress.percent >= 100
    ? stages.length
    : stages.findLastIndex((stage) => progress.percent >= stage.threshold);

  useEffect(() => {
    const started = Date.now();
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="pipeline" aria-live="polite">
      <div className="pipeline-topline">
        <span>MODEL PIPELINE</span>
        <strong>{progress.percent}%</strong>
      </div>
      <div className="pipeline-track"><span style={{ width: `${progress.percent}%` }} /></div>
      <ol>
        {stages.map((stage, index) => {
          const done = index < activeIndex || activeIndex === stages.length;
          const active = index === activeIndex;
          return (
            <li key={stage.label} className={active ? 'active' : done ? 'done' : ''}>
              {done ? <Check size={14} /> : active ? <LoaderCircle size={14} /> : <Circle size={12} />}
              <span><strong>{stage.label}</strong><small>{stage.detail}</small></span>
            </li>
          );
        })}
      </ol>
      <div className="pipeline-status"><p>{progress.message}</p><span>已用 {formatElapsed(elapsed)}</span></div>
    </div>
  );
};

export default ProgressPanel;
