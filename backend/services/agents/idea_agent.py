"""Idea 结构化输出解析与详细方案 Agent。"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List

logger = logging.getLogger(__name__)


class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    GENERATING = "generating"
    REFINING = "refining"
    DONE = "done"
    ERROR = "error"


@dataclass
class IdeaItem:
    name: str
    tagline: str
    pain_point: str
    solution: str
    target_user: str
    market_size: str
    competitors: str
    pricing: str
    revenue: str
    tech_stack: str
    advantage: str
    score: float
    tags: List[str]
    evidence: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    confidence: str = "medium"


class IdeaOutputParser:
    """只接受可验证的 JSON 数组，不生成备用业务数据。"""

    required_fields = {
        "name", "tagline", "pain_point", "solution", "target_user", "market_size",
        "competitors", "pricing", "revenue", "tech_stack", "advantage", "score", "tags",
    }

    def _parse_ideas_response(self, response: str, expected_count: int) -> List[Dict]:
        text = response.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if fenced:
            text = fenced.group(1).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("[")
            if start < 0:
                raise ValueError("模型输出不是有效的 Ideas JSON，请重试或更换模型") from None
            try:
                data, _ = json.JSONDecoder().raw_decode(text[start:])
            except json.JSONDecodeError as exc:
                logger.debug("Unparseable model response: %s", text[:2000])
                raise ValueError("模型输出不是有效的 Ideas JSON，请重试或更换模型") from exc

        if not isinstance(data, list):
            raise ValueError("模型输出必须是 JSON 数组")
        if len(data) != expected_count:
            raise ValueError(f"模型返回 {len(data)} 项，预期 {expected_count} 项")
        if not all(isinstance(item, dict) for item in data):
            raise ValueError("模型输出数组只能包含对象")
        return data

    def _validate_and_enrich(self, ideas_data: List[Dict], expected_count: int) -> List[IdeaItem]:
        if len(ideas_data) != expected_count:
            raise ValueError(f"模型返回 {len(ideas_data)} 个有效 Idea，预期 {expected_count} 个")

        ideas = []
        for index, item in enumerate(ideas_data, 1):
            missing = self.required_fields - item.keys()
            if missing:
                raise ValueError(f"第 {index} 个 Idea 缺少字段: {', '.join(sorted(missing))}")

            score = float(item["score"])
            confidence = item.get("confidence", "medium")
            if not 0 <= score <= 10:
                raise ValueError(f"第 {index} 个 Idea 的 score 必须在 0-10")
            if confidence not in {"low", "medium", "high"}:
                raise ValueError(f"第 {index} 个 Idea 的 confidence 无效")

            list_fields = {name: item.get(name, []) for name in ("tags", "evidence", "assumptions", "risks")}
            if not all(isinstance(value, list) and all(isinstance(entry, str) for entry in value) for value in list_fields.values()):
                raise ValueError(f"第 {index} 个 Idea 的列表字段格式无效")

            ideas.append(IdeaItem(
                name=str(item["name"]).strip(),
                tagline=str(item["tagline"]).strip(),
                pain_point=str(item["pain_point"]).strip(),
                solution=str(item["solution"]).strip(),
                target_user=str(item["target_user"]).strip(),
                market_size=str(item["market_size"]).strip(),
                competitors=str(item["competitors"]).strip(),
                pricing=str(item["pricing"]).strip(),
                revenue=str(item["revenue"]).strip(),
                tech_stack=str(item["tech_stack"]).strip(),
                advantage=str(item["advantage"]).strip(),
                score=score,
                tags=list_fields["tags"],
                evidence=list_fields["evidence"],
                assumptions=list_fields["assumptions"],
                risks=list_fields["risks"],
                confidence=confidence,
            ))
        return ideas


class DetailGenerationAgent:
    def __init__(self, model_client, model=None):
        self.model_client = model_client
        self.model = model
        self.state = AgentState.IDLE

    async def generate_detail(self, idea: IdeaItem, callback=None) -> str:
        try:
            await self._update_progress(AgentState.THINKING, "分析机会", 15, "正在分析核心要素…", callback)
            await self._update_progress(AgentState.GENERATING, "生成方案", 40, "正在生成落地方案…", callback)
            plan = await self.model_client.generate(self._build_detail_prompt(idea), self.model)
            await self._update_progress(AgentState.REFINING, "检查方案", 75, "正在检查假设与风险…", callback)
            plan = self._format_plan(plan)
            if len(plan) < 200:
                raise ValueError("详细方案内容过短")
            await self._update_progress(AgentState.DONE, "完成", 100, "详细方案生成完成", callback)
            return plan
        except Exception as exc:
            logger.exception("Detail generation failed")
            await self._update_progress(AgentState.ERROR, "失败", 0, "详细方案生成失败", callback)
            raise RuntimeError("详细方案生成失败，请重试") from exc

    @staticmethod
    def _build_detail_prompt(idea: IdeaItem) -> str:
        return f"""你是产品与技术负责人。为以下机会生成一份可执行的 Markdown 落地方案。

项目：{idea.name}
概念：{idea.tagline}
痛点：{idea.pain_point}
方案：{idea.solution}
目标用户：{idea.target_user}
证据信号：{json.dumps(idea.evidence, ensure_ascii=False)}
关键假设：{json.dumps(idea.assumptions, ensure_ascii=False)}
主要风险：{json.dumps(idea.risks, ensure_ascii=False)}

必须包含：
1. MVP 功能与明确非目标
2. 技术架构、核心数据模型与接口
3. 6 周开发计划和每周可验收产物
4. 成本模型与容量假设
5. 定价实验和获客路径
6. 风险缓解方案
7. PMF 验证：访谈问题、实验、成功/停止指标

约束：所有市场数字标为估算并写明验证方法；不要虚构引用；方案适合个人或小团队执行。
"""

    @staticmethod
    def _format_plan(plan: str) -> str:
        plan = re.sub(r"```markdown\n?", "", plan, flags=re.IGNORECASE)
        plan = re.sub(r"```\n?$", "", plan.strip())
        return plan.strip()

    async def _update_progress(self, state: AgentState, step: str, progress: int, message: str, callback=None):
        self.state = state
        if callback:
            await callback({
                "state": state.value,
                "step": step,
                "progress": progress,
                "message": message,
                "timestamp": datetime.now().isoformat(),
            })
