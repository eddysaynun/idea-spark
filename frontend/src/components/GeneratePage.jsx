import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowUpRight, Lightbulb, ShieldCheck } from 'lucide-react';

import { useApp } from '../context/app-context';
import { productAPI } from '../api';
import { filterAndSortIdeas, summarizeIdeas } from '../utils/generate-workbench';
import GenerateForm from './GenerateForm';
import IdeasGrid from './IdeasGrid';
import ProgressPanel from './ProgressPanel';
import './GeneratePage.css';

const GeneratePage = ({ onOpenIdea }) => {
  const { isGenerating, progress, generationError, ideas, currentSession } = useApp();
  const [filter, setFilter] = useState('all');
  const [sort, setSort] = useState('original');
  const resultsRef = useRef(null);
  const wasGenerating = useRef(false);
  const visibleIdeas = useMemo(() => filterAndSortIdeas(ideas, filter, sort), [ideas, filter, sort]);
  const summary = useMemo(() => summarizeIdeas(ideas), [ideas]);

  useEffect(() => {
    if (isGenerating) {
      wasGenerating.current = true;
      return;
    }
    if (wasGenerating.current && ideas.length && resultsRef.current && window.matchMedia('(max-width: 960px)').matches) {
      const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      resultsRef.current.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth', block: 'start' });
    }
    wasGenerating.current = false;
  }, [ideas.length, isGenerating]);

  const record = (action, index) => {
    if (currentSession?.id) productAPI.record(currentSession.id, index, action).catch(() => {});
  };

  const openIdea = (index) => {
    record('expand', index);
    onOpenIdea(index);
  };

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

      <ol className="workflow-rail" aria-label="机会生成流程">
        <li><span>BRIEF</span><strong>定义问题</strong><small>用户、场景与约束</small></li>
        <li><span>REVIEW</span><strong>三阶段评审</strong><small>探索、批判与定稿</small></li>
        <li><span>DECIDE</span><strong>比较候选</strong><small>信号、风险与置信度</small></li>
      </ol>

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

        <div className="results-column" ref={resultsRef}>
          <div className="panel-heading results-heading">
            <div>
              <span className="panel-index">SIGNALS</span>
              <h2>{ideas.length ? `${ideas.length} 个候选机会` : '等待探索'}</h2>
            </div>
            {currentSession?.id && <span className="session-chip">SESSION {currentSession.id.slice(0, 8)}</span>}
          </div>

          {ideas.length > 0 ? (
            <>
              <div className="result-insights" aria-label="候选摘要">
                <div><span>高置信候选</span><strong>{summary.highConfidence}</strong></div>
                <div><span>已识别风险</span><strong>{summary.riskCount}</strong></div>
                <div className="recommended-signal"><span>建议优先查看</span><strong title={summary.recommendedName}>{summary.recommendedName}</strong></div>
              </div>
              <div className="result-tools">
                <div className="result-filters" aria-label="筛选候选">
                  {[
                    ['all', '全部'],
                    ['high', '高置信'],
                    ['validate', '待验证'],
                  ].map(([value, label]) => (
                    <button key={value} type="button" className={filter === value ? 'active' : ''} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>
                  ))}
                </div>
                <label>
                  排序
                  <select value={sort} onChange={(event) => setSort(event.target.value)}>
                    <option value="original">生成顺序</option>
                    <option value="score">评分从高到低</option>
                    <option value="confidence">置信度优先</option>
                    <option value="risk">风险较少优先</option>
                  </select>
                </label>
                <span>{visibleIdeas.length}/{ideas.length}</span>
              </div>
              {visibleIdeas.length ? (
                <IdeasGrid
                  ideas={visibleIdeas}
                  onOpenIdea={(visibleIndex) => openIdea(ideas.indexOf(visibleIdeas[visibleIndex]))}
                  onNoValue={(visibleIndex) => record('no_value', ideas.indexOf(visibleIdeas[visibleIndex]))}
                />
              ) : (
                <div className="filtered-empty"><strong>没有符合筛选条件的候选</strong><button type="button" onClick={() => setFilter('all')}>查看全部</button></div>
              )}
            </>
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
