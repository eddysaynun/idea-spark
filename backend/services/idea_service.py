"""
Ideas 生成服务
负责编排 Ideas 生成的完整流程
"""

import logging
from typing import List, Dict, Any
from datetime import datetime
import uuid

from services.agents.idea_agent import IdeaGenerationAgent, IdeaItem
from services.models.model_client import ModelClient

logger = logging.getLogger(__name__)


class IdeaService:
    """Ideas 生成服务"""
    
    def __init__(self, model_client: ModelClient):
        self.model_client = model_client
    
    # 会话存储（内存，可扩展到 Redis）
    sessions: Dict[str, Dict[str, Any]] = {}
    
    async def generate_ideas(
        self,
        direction: str,
        count: int,
        category: str,
        callback=None
    ) -> List['IdeaItem']:
        """
        生成 Ideas
        
        Args:
            direction: 项目方向
            count: 生成数量
            category: 分类
            callback: 进度回调
            
        Returns:
            Ideas 列表
        """
        # 创建会话
        session_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        IdeaService.sessions[session_id] = {
            "id": session_id,
            "direction": direction,
            "category": category,
            "count": count,
            "ideas": [],
            "created_at": created_at,
            "updated_at": created_at
        }
        
        # 进度回调
        async def progress_callback(progress_data: Dict[str, Any]):
            logger.info(f"📊 Progress: {progress_data['step']} ({progress_data['progress']}%)")
            if callback:
                callback(progress_data)  # 不再 await，因为 callback 可能不是 async
        
        try:
            # 创建 Agent 并生成 Ideas
            agent = IdeaGenerationAgent(self.model_client)
            ideas: List['IdeaItem'] = await agent.generate_ideas(
                direction=direction,
                count=count,
                category=category,
                callback=progress_callback
            )
            
            # 转换为字典
            ideas_dict = [
                {
                    "name": idea.name,
                    "tagline": idea.tagline,
                    "pain_point": idea.pain_point,
                    "solution": idea.solution,
                    "target_user": idea.target_user,
                    "market_size": idea.market_size,
                    "competitors": idea.competitors,
                    "pricing": idea.pricing,
                    "revenue": idea.revenue,
                    "tech_stack": idea.tech_stack,
                    "advantage": idea.advantage,
                    "score": idea.score,
                    "tags": idea.tags
                }
                for idea in ideas
            ]
            
            # 更新会话
            IdeaService.sessions[session_id].update({
                "ideas": ideas_dict,
                "updated_at": datetime.now().isoformat()
            })
            
            logger.info(f"✅ Generated {len(ideas)} ideas for session {session_id}")
            
            return ideas
            
        except Exception as e:
            logger.error(f"❌ Failed to generate ideas: {e}")
            raise
    
    async def generate_ideas_stream(
        self,
        direction: str,
        count: int,
        category: str,
        callback=None
    ) -> List['IdeaItem']:
        """
        流式生成 Ideas（参考 ModelChatPanel 实现）
        
        流式发送：
        - reasoning: AI 思考过程
        - text: AI 生成内容（原始 JSON）
        - idea: 解析后的 Idea 对象
        
        Args:
            direction: 项目方向
            count: 生成数量
            category: 分类
            callback: 流式回调（发送 SSE 事件）
            
        Returns:
            Ideas 列表
        """
        # 创建会话
        session_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        IdeaService.sessions[session_id] = {
            "id": session_id,
            "direction": direction,
            "category": category,
            "count": count,
            "ideas": [],
            "created_at": created_at,
            "updated_at": created_at
        }
        
        try:
            # 创建 Agent 并流式生成 Ideas
            agent = IdeaGenerationAgent(self.model_client)
            ideas: List['IdeaItem'] = await agent.generate_ideas_stream(
                direction=direction,
                count=count,
                category=category,
                callback=callback
            )
            
            # 转换为字典
            ideas_dict = [
                {
                    "name": idea.name,
                    "tagline": idea.tagline,
                    "pain_point": idea.pain_point,
                    "solution": idea.solution,
                    "target_user": idea.target_user,
                    "market_size": idea.market_size,
                    "competitors": idea.competitors,
                    "pricing": idea.pricing,
                    "revenue": idea.revenue,
                    "tech_stack": idea.tech_stack,
                    "advantage": idea.advantage,
                    "score": idea.score,
                    "tags": idea.tags
                }
                for idea in ideas
            ]
            
            # 更新会话
            IdeaService.sessions[session_id].update({
                "ideas": ideas_dict,
                "updated_at": datetime.now().isoformat()
            })
            
            logger.info(f"✅ Generated {len(ideas)} ideas for session {session_id}")
            
            return ideas
            
        except Exception as e:
            logger.error(f"❌ Failed to generate ideas: {e}")
            raise
        """获取会话详情"""
        session = IdeaService.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        return session
    
    @staticmethod
    def list_sessions() -> List[Dict[str, Any]]:
        """获取所有会话列表"""
        return list(IdeaService.sessions.values())
    
    @staticmethod
    def delete_session(session_id: str) -> bool:
        """删除会话"""
        if session_id in IdeaService.sessions:
            del IdeaService.sessions[session_id]
            logger.info(f"🗑️ Deleted session: {session_id}")
            return True
        return False
