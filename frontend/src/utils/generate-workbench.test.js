import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildExplorationBrief,
  filterAndSortIdeas,
  formatElapsed,
  summarizeIdeas,
} from './generate-workbench.js';

const ideas = [
  { name: '稳健候选', score: 8.6, confidence: 'high', risks: ['渠道'] },
  { name: '高分待验证', score: 9.1, confidence: 'medium', risks: ['成本', '留存', '合规'] },
  { name: '低风险待验证', score: 7.4, confidence: 'low', risks: [] },
];

test('builds one backend-compatible brief from optional exploration boundaries', () => {
  assert.equal(buildExplorationBrief({
    direction: '帮助小团队验证产品方向',
    audience: '中国大陆独立开发者',
    scenario: '上线前两周',
    constraints: '两人团队，预算 5000 元',
  }), [
    '帮助小团队验证产品方向',
    '目标用户：中国大陆独立开发者',
    '使用场景：上线前两周',
    '关键约束：两人团队，预算 5000 元',
  ].join('\n'));

  assert.equal(buildExplorationBrief({ direction: '只保留主问题', audience: '  ' }), '只保留主问题');
});

test('filters confidence groups and sorts candidates without changing the source list', () => {
  assert.deepEqual(
    filterAndSortIdeas(ideas, 'high', 'score').map((idea) => idea.name),
    ['稳健候选'],
  );
  assert.deepEqual(
    filterAndSortIdeas(ideas, 'validate', 'risk').map((idea) => idea.name),
    ['低风险待验证', '高分待验证'],
  );
  assert.deepEqual(ideas.map((idea) => idea.name), ['稳健候选', '高分待验证', '低风险待验证']);
});

test('summarizes result signals and identifies the strongest candidate', () => {
  assert.deepEqual(summarizeIdeas(ideas), {
    highConfidence: 1,
    riskCount: 4,
    recommendedName: '高分待验证',
  });
  assert.deepEqual(summarizeIdeas([]), {
    highConfidence: 0,
    riskCount: 0,
    recommendedName: '',
  });
});

test('formats generation elapsed time for quick scanning', () => {
  assert.equal(formatElapsed(5), '0:05');
  assert.equal(formatElapsed(125), '2:05');
});
