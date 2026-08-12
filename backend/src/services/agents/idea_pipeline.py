"""面向中型推理模型的三阶段 Idea 生成流水线。"""

import json
from typing import Any, AsyncGenerator, Dict

from services.agents.idea_agent import IdeaOutputParser


class IdeaPipeline:
    """探索候选、批判评分，再输出严格结构化结果。"""

    def __init__(self, model_client, model=None):
        self.model_client = model_client
        self.model = model
        self.parser = IdeaOutputParser()

    async def run_events(
        self, direction: str, count: int, category: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        candidate_count = min(count * 2, 24)
        yield self._progress("机会探索", 10, f"正在从多个切入角度探索 {candidate_count} 个候选…")

        explorer_content = ""
        reasoning_preview = ""
        content_preview = ""
        async for chunk in self.model_client.generate_stream(
            self._explorer_prompt(direction, candidate_count, category),
            self.model,
            thinking=False,
        ):
            if chunk["type"] == "thinking":
                reasoning_preview += chunk["data"]
                if len(reasoning_preview) >= 160:
                    yield {"type": "reasoning", "data": reasoning_preview}
                    reasoning_preview = ""
            elif chunk["type"] == "content":
                explorer_content += chunk["data"]
                content_preview += chunk["data"]
                if len(content_preview) >= 160:
                    yield {"type": "text", "data": content_preview}
                    content_preview = ""
            elif chunk["type"] == "error":
                raise RuntimeError(chunk["data"])

        if reasoning_preview:
            yield {"type": "reasoning", "data": reasoning_preview}
        if content_preview:
            yield {"type": "text", "data": content_preview}

        try:
            candidates = self.parser._parse_ideas_response(explorer_content, candidate_count)
        except ValueError as exc:
            yield self._progress("修复探索结果", 36, "模型输出结构不完整，正在进行一次受控修复…")
            repaired = await self.model_client.generate(
                self._repair_prompt("机会探索", candidate_count, explorer_content, str(exc)), self.model
            )
            candidates = self.parser._parse_ideas_response(repaired, candidate_count)
        yield self._progress("批判评估", 48, "正在检查痛点强度、差异化、可执行性与证据缺口…")
        critiques = await self._generate_json(
            "批判评估",
            self._critic_prompt(direction, candidates),
            len(candidates),
            thinking=True,
        )

        yield self._progress("结构化定稿", 76, f"正在去重并定稿最有潜力的 {count} 个机会…")
        final_data = await self._generate_json(
            "结构化定稿", self._editor_prompt(direction, count, candidates, critiques), count
        )
        try:
            ideas = self.parser._validate_and_enrich(final_data, count)
        except ValueError as exc:
            repaired = await self.model_client.generate(
                self._repair_prompt(
                    "结构化定稿字段契约",
                    count,
                    json.dumps(final_data, ensure_ascii=False),
                    str(exc),
                ),
                self.model,
                thinking=False,
            )
            ideas = self.parser._validate_and_enrich(
                self.parser._parse_ideas_response(repaired, count), count
            )

        for index, idea in enumerate(ideas, 1):
            yield {"type": "idea", "data": vars(idea), "index": index}
        yield self._progress("完成", 100, f"已生成 {len(ideas)} 个经过评估的机会")

    @staticmethod
    def _progress(step: str, progress: int, message: str) -> Dict[str, Any]:
        return {"type": "progress", "data": {"step": step, "progress": progress, "message": message}}

    async def _generate_json(
        self,
        stage: str,
        prompt: str,
        expected_count: int,
        *,
        thinking: bool = False,
    ) -> list:
        content = await self.model_client.generate(
            prompt,
            self.model,
            thinking=thinking,
            max_tokens=32768 if thinking else None,
        )
        try:
            return self.parser._parse_ideas_response(content, expected_count)
        except ValueError as exc:
            repaired = await self.model_client.generate(
                self._repair_prompt(stage, expected_count, content, str(exc)),
                self.model,
                thinking=False,
            )
            return self.parser._parse_ideas_response(repaired, expected_count)

    @staticmethod
    def _repair_prompt(stage: str, expected_count: int, output: str, error: str) -> str:
        return f"""修复以下「{stage}」输出。错误：{error}
只输出恰好 {expected_count} 项的合法 JSON 数组，不添加 Markdown 或说明；保留原有语义，不编造新的外部事实。
tags、evidence、assumptions、risks 必须是字符串数组，不能是字符串；score 必须是 0-10 数字；confidence 只能是 low、medium、high。
待修复输出：
{output[:12000]}
"""

    @staticmethod
    def _explorer_prompt(direction: str, count: int, category: str) -> str:
        return f"""你是机会探索者。围绕「{direction}」在分类「{category}」中提出 {count} 个差异明显的产品候选。

覆盖不同用户、场景、付费触发点和交付形态，避免只给同一概念换名字。市场数字如果没有外部来源，只能写成待验证假设。

只输出 JSON 数组。每项字段：name, tagline, pain_point, solution, target_user, market_size, competitors, pricing, revenue, tech_stack, advantage, score, tags, evidence, assumptions, risks, confidence。
- evidence：支持该机会的可观察信号或待调研线索，不得虚构引用
- assumptions：尚未验证的关键假设
- risks：最可能导致失败的因素
- confidence：low/medium/high
- score：0-10
"""

    @staticmethod
    def _critic_prompt(direction: str, candidates: list) -> str:
        return f"""你是严格的产品投资评审。目标方向：{direction}。

逐项深入推理并评估候选，不美化、不补造事实。内部完成比较后，只输出 JSON 数组，每项包含 candidate_index、pain_score、differentiation_score、feasibility_score、monetization_score、evidence_score（均 0-10）、fatal_flaw、missing_evidence、recommendation（keep/rework/drop）。

候选：
{json.dumps(candidates, ensure_ascii=False)}
"""

    @staticmethod
    def _editor_prompt(direction: str, count: int, candidates: list, critiques: list) -> str:
        return f"""你是产品主编。围绕「{direction}」，依据评审去重并选择 {count} 个最成熟且彼此差异明显的机会。

只输出恰好 {count} 项的 JSON 数组。每项必须包含：name, tagline, pain_point, solution, target_user, market_size, competitors, pricing, revenue, tech_stack, advantage, score, tags, evidence, assumptions, risks, confidence。
要求：
1. evidence 只写可观察信号或明确的验证路径，不得把推测伪装为事实；
2. assumptions 和 risks 各至少 2 条；
3. 定价、收入和市场规模标明估算依据或待验证条件；
4. score 综合评审而来，confidence 只能是 low/medium/high；
5. 不使用 Markdown，不输出解释文字。

候选：{json.dumps(candidates, ensure_ascii=False)}
评审：{json.dumps(critiques, ensure_ascii=False)}
"""
