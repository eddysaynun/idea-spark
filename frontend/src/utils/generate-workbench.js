export const buildExplorationBrief = ({ direction, audience, scenario, constraints }) => [
  direction?.trim(),
  audience?.trim() && `目标用户：${audience.trim()}`,
  scenario?.trim() && `使用场景：${scenario.trim()}`,
  constraints?.trim() && `关键约束：${constraints.trim()}`,
].filter(Boolean).join('\n');

const confidenceRank = { high: 3, medium: 2, low: 1 };

export const filterAndSortIdeas = (ideas, filter = 'all', sort = 'original') => {
  const filtered = ideas.filter((idea) => (
    filter === 'high' ? idea.confidence === 'high'
      : filter === 'validate' ? idea.confidence !== 'high'
        : true
  ));

  return [...filtered].sort((left, right) => {
    if (sort === 'score') return Number(right.score || 0) - Number(left.score || 0);
    if (sort === 'confidence') return (confidenceRank[right.confidence] || 0) - (confidenceRank[left.confidence] || 0);
    if (sort === 'risk') return (left.risks?.length || 0) - (right.risks?.length || 0);
    return ideas.indexOf(left) - ideas.indexOf(right);
  });
};

export const summarizeIdeas = (ideas) => {
  const recommended = ideas.reduce((best, idea) => (
    !best || Number(idea.score || 0) > Number(best.score || 0) ? idea : best
  ), null);
  return {
    highConfidence: ideas.filter((idea) => idea.confidence === 'high').length,
    riskCount: ideas.reduce((total, idea) => total + (idea.risks?.length || 0), 0),
    recommendedName: recommended?.name || '',
  };
};

export const formatElapsed = (seconds) => {
  const safeSeconds = Math.max(0, Math.floor(Number(seconds) || 0));
  return `${Math.floor(safeSeconds / 60)}:${String(safeSeconds % 60).padStart(2, '0')}`;
};
