"""
流式 Ideas 生成路由
参考 ModelChatPanel 的流式实现
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator, List
import json
import logging
import uuid
from datetime import datetime

from services.agents.idea_agent import IdeaGenerationAgent, IdeaItem
from services.models.model_client import ModelClient

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stream"])


@router.get("/generate-stream")
async def generate_ideas_stream(
    request: Request,
    direction: str,
    count: int = 5,
    category: str = "general"
):
    """流式生成 Ideas（使用 SSE）
    
    事件类型：
    - start: 开始生成
    - reasoning: AI 思考过程
    - text: AI 生成内容（JSON）
    - progress: 进度更新
    - idea: 解析后的 Idea 对象
    - complete: 生成完成
    - error: 错误信息
    """
    
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            model_client = request.app.state.model_client
            
            # 生成 session_id
            session_id = str(uuid.uuid4())
            
            # 发送开始事件
            yield f"data: {json.dumps({'type': 'start', 'data': {'direction': direction, 'count': count, 'category': category, 'session_id': session_id}}, ensure_ascii=False)}\n\n"
            
            # 创建 Agent
            agent = IdeaGenerationAgent(model_client)
            
            # Step 1: 分析需求
            yield f"data: {json.dumps({'type': 'progress', 'data': {'step': '分析需求', 'progress': 10, 'message': '正在分析项目方向...'}}, ensure_ascii=False)}\n\n"
            
            # Step 2: 生成 Ideas
            yield f"data: {json.dumps({'type': 'progress', 'data': {'step': '生成 Ideas', 'progress': 30, 'message': '正在调用 AI 模型生成 Ideas...'}}, ensure_ascii=False)}\n\n"
            
            prompt = agent._build_ideas_prompt(direction, count, category)
            
            # 使用流式 API - 实时发送 reasoning 和 text
            full_thinking = ""
            full_content = ""
            
            logger.info("🔄 Starting stream generation...")
            
            async for chunk in model_client.generate_stream(prompt):
                if chunk["type"] == "thinking":
                    full_thinking += chunk["data"]
                    # 实时发送 reasoning
                    yield f"data: {json.dumps({'type': 'reasoning', 'data': chunk['data']}, ensure_ascii=False)}\n\n"
                elif chunk["type"] == "content":
                    full_content += chunk["data"]
                    # 实时发送 text
                    yield f"data: {json.dumps({'type': 'text', 'data': chunk['data']}, ensure_ascii=False)}\n\n"
                elif chunk["type"] == "error":
                    logger.error(f"Stream error: {chunk['data']}")
                    yield f"data: {json.dumps({'type': 'error', 'data': {'message': chunk['data']}}, ensure_ascii=False)}\n\n"
                    return
            
            logger.info(f"✅ Stream completed: thinking={len(full_thinking)} chars, content={len(full_content)} chars")
            
            # Step 3: 解析结果
            yield f"data: {json.dumps({'type': 'progress', 'data': {'step': '解析结果', 'progress': 60, 'message': f'正在解析 AI 输出... ({len(full_content)} chars)'}}, ensure_ascii=False)}\n\n"
            
            ideas_data = agent._parse_ideas_response(full_content, count)
            
            # Step 4: 验证和补充
            yield f"data: {json.dumps({'type': 'progress', 'data': {'step': '优化完善', 'progress': 80, 'message': '正在优化 Ideas 质量...'}}, ensure_ascii=False)}\n\n"
            
            ideas = agent._validate_and_enrich(ideas_data, count)
            
            # Step 5: 发送每个 idea
            for idx, idea in enumerate(ideas, 1):
                idea_dict = {
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
                yield f"data: {json.dumps({'type': 'idea', 'data': idea_dict, 'index': idx}, ensure_ascii=False)}\n\n"
                logger.info(f"✨ Sent idea {idx}: {idea.name}")
            
            # Step 6: 完成
            yield f"data: {json.dumps({'type': 'progress', 'data': {'step': '完成', 'progress': 100, 'message': f'成功生成 {len(ideas)} 个 Ideas!'}}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'complete', 'data': {'total': len(ideas), 'session_id': session_id}}, ensure_ascii=False)}\n\n"
            
            logger.info(f"✅ Stream completed: {len(ideas)} ideas")
            
        except Exception as e:
            logger.error(f"Stream generation failed: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
