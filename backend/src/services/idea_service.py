"""Idea 生成、会话与详情编排。"""

import logging
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List

from services.agents.idea_agent import DetailGenerationAgent, IdeaItem
from services.agents.idea_pipeline import IdeaPipeline
from services.models.model_client import ModelClient

logger = logging.getLogger(__name__)


class IdeaService:
    """在单进程内维护生成会话。"""

    sessions: Dict[str, Dict[str, Any]] = {}

    def __init__(self, model_client: ModelClient):
        self.model_client = model_client

    @classmethod
    def create_session(cls, direction: str, count: int, category: str, model: str = "") -> Dict[str, Any]:
        now = datetime.now().isoformat()
        session = {
            "id": str(uuid.uuid4()),
            "direction": direction,
            "category": category,
            "count": count,
            "model": model,
            "ideas": [],
            "detailed_plans": {},
            "created_at": now,
            "updated_at": now,
        }
        cls.sessions[session["id"]] = session
        return session

    @classmethod
    def complete_session(cls, session_id: str, ideas: List[IdeaItem]) -> Dict[str, Any]:
        session = cls.get_session(session_id)
        session["ideas"] = [asdict(idea) for idea in ideas]
        session["updated_at"] = datetime.now().isoformat()
        return session

    async def generate_ideas(self, direction: str, count: int, category: str, model: str = "") -> Dict[str, Any]:
        selected_model = self.model_client.validate_model(model)
        session = self.create_session(direction, count, category, selected_model)
        try:
            ideas = []
            async for event in IdeaPipeline(self.model_client, selected_model).run_events(direction, count, category):
                if event["type"] == "idea":
                    ideas.append(IdeaItem(**event["data"]))
            return self.complete_session(session["id"], ideas)
        except Exception:
            self.sessions.pop(session["id"], None)
            raise

    async def generate_detail(self, session_id: str, idea_index: int, model: str = "") -> str:
        session = self.get_session(session_id)
        if idea_index >= len(session["ideas"]):
            raise ValueError("Idea index out of range")

        cache_key = str(idea_index)
        if cache_key in session["detailed_plans"]:
            return session["detailed_plans"][cache_key]

        idea = IdeaItem(**session["ideas"][idea_index])
        selected_model = self.model_client.validate_model(model or session.get("model", ""))
        plan = await DetailGenerationAgent(self.model_client, selected_model).generate_detail(idea)
        session["detailed_plans"][cache_key] = plan
        session["updated_at"] = datetime.now().isoformat()
        return plan

    @classmethod
    def get_session(cls, session_id: str) -> Dict[str, Any]:
        session = cls.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        return session

    @classmethod
    def list_sessions(cls) -> List[Dict[str, Any]]:
        return sorted(cls.sessions.values(), key=lambda item: item["updated_at"], reverse=True)

    @classmethod
    def delete_session(cls, session_id: str) -> bool:
        return cls.sessions.pop(session_id, None) is not None
