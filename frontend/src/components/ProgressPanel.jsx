import { Check, Circle, LoaderCircle } from 'lucide-react';

import './ProgressPanel.css';

const stages = [
  { label: '机会探索', threshold: 10 },
  { label: '批判评估', threshold: 48 },
  { label: '结构化定稿', threshold: 76 },
];

const ProgressPanel = ({ progress }) => (
  <div className="pipeline" aria-live="polite">
    <div className="pipeline-topline">
      <span>MODEL PIPELINE</span>
      <strong>{progress.percent}%</strong>
    </div>
    <div className="pipeline-track"><span style={{ width: `${progress.percent}%` }} /></div>
    <ol>
      {stages.map((stage) => {
        const done = progress.percent > stage.threshold;
        const active = progress.percent >= stage.threshold && !done;
        return (
          <li key={stage.label} className={active ? 'active' : done ? 'done' : ''}>
            {done ? <Check size={14} /> : active ? <LoaderCircle size={14} /> : <Circle size={12} />}
            <span>{stage.label}</span>
          </li>
        );
      })}
    </ol>
    <p>{progress.message}</p>
  </div>
);

export default ProgressPanel;
