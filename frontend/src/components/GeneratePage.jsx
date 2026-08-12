import { ArrowUpRight, Lightbulb, ShieldCheck } from 'lucide-react';

import { useApp } from '../context/app-context';
import GenerateForm from './GenerateForm';
import IdeasGrid from './IdeasGrid';
import ProgressPanel from './ProgressPanel';
import './GeneratePage.css';

const GeneratePage = ({ onOpenIdea }) => {
  const { isGenerating, progress, generationError, ideas, currentSession } = useApp();

  return (
    <div className="generate-page">
      <section className="workbench-intro">
        <div>
          <p className="eyebrow"><span /> OPPORTUNITY WORKBENCH</p>
          <h1>把模糊方向，变成<br /><em>可验证的机会。</em></h1>
        </div>
        <div className="intro-proof">
          <ShieldCheck size={20} />
          <p>先探索，再批判，最后定稿。市场数据默认视为假设，直到你完成外部验证。</p>
        </div>
      </section>

      <section className="workbench-grid">
        <aside className="control-column">
          <div className="panel-heading">
            <span className="panel-index">INPUT</span>
            <h2>定义探索边界</h2>
          </div>
          <GenerateForm />
          {generationError && <div className="inline-error" role="alert">{generationError}</div>}
          {isGenerating && <ProgressPanel progress={progress} />}
        </aside>

        <div className="results-column">
          <div className="panel-heading results-heading">
            <div>
              <span className="panel-index">SIGNALS</span>
              <h2>{ideas.length ? `${ideas.length} 个候选机会` : '等待探索'}</h2>
            </div>
            {currentSession?.id && <span className="session-chip">SESSION {currentSession.id.slice(0, 8)}</span>}
          </div>

          {ideas.length > 0 ? (
            <IdeasGrid ideas={ideas} onOpenIdea={onOpenIdea} />
          ) : (
            <div className="results-empty">
              <div className="spark-orbit"><Lightbulb size={28} /></div>
              <p className="empty-kicker">从一个具体问题开始</p>
              <h3>结果会在这里逐条出现</h3>
              <p>每个机会都会给出证据信号、关键假设、主要风险与置信度，方便你比较，而不是只看漂亮名称。</p>
              <span>填写左侧输入 <ArrowUpRight size={15} /></span>
            </div>
          )}
        </div>
      </section>
    </div>
  );
};

export default GeneratePage;
