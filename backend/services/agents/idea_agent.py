"""
Idea Generator Agent Framework
提供智能 Ideas 生成和详细方案设计的 Agent 系统
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import json
import asyncio
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """Agent 状态枚举"""
    IDLE = "idle"
    THINKING = "thinking"
    GENERATING = "generating"
    REFINING = "refining"
    COMPLETING = "completing"
    DONE = "done"
    ERROR = "error"


@dataclass
class IdeaItem:
    """单个 Idea 数据结构"""
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


@dataclass
class GenerationProgress:
    """生成进度数据"""
    state: AgentState
    step: str
    progress: int  # 0-100
    message: str
    timestamp: str
    metadata: Dict[str, Any] = None


class IdeaGenerationAgent:
    """
    Ideas 生成 Agent
    负责生成高质量、痛点驱动的 Ideas
    """
    
    def __init__(self, model_client):
        self.model_client = model_client
        self.state = AgentState.IDLE
        self.progress_history: List[GenerationProgress] = []
    
    async def generate_ideas_stream(
        self,
        direction: str,
        count: int,
        category: str,
        callback=None
    ) -> List['IdeaItem']:
        """
        流式生成 Ideas（参考 ModelChatPanel）
        
        流式发送事件：
        - reasoning: AI 思考过程
        - text: AI 生成内容（原始 JSON）
        """
        try:
            # Step 1: 分析需求
            if callback:
                callback({'type': 'progress', 'data': {'step': '分析需求', 'progress': 10, 'message': '正在分析项目方向...'}})
            
            # Step 2: 生成 Ideas
            if callback:
                callback({'type': 'progress', 'data': {'step': '生成 Ideas', 'progress': 30, 'message': '正在调用 AI 模型生成 Ideas...'}})
            
            prompt = self._build_ideas_prompt(direction, count, category)
            
            # 使用流式 API - 实时发送 reasoning 和 text
            full_thinking = ""
            full_content = ""
            
            logger.info("🔄 Starting stream generation...")
            
            async for chunk in self.model_client.generate_stream(prompt):
                if chunk["type"] == "thinking":
                    full_thinking += chunk["data"]
                    # 实时发送 reasoning
                    if callback:
                        callback({'type': 'reasoning', 'data': chunk["data"]})
                elif chunk["type"] == "content":
                    full_content += chunk["data"]
                    # 实时发送 text
                    if callback:
                        callback({'type': 'text', 'data': chunk["data"]})
                elif chunk["type"] == "error":
                    logger.error(f"Stream error: {chunk['data']}")
                    raise RuntimeError(f"Stream error: {chunk['data']}")
            
            logger.info(f"✅ Stream completed: thinking={len(full_thinking)} chars, content={len(full_content)} chars")
            
            # Step 3: 解析结果
            if callback:
                callback({'type': 'progress', 'data': {'step': '解析结果', 'progress': 60, 'message': f'正在解析 AI 输出... ({len(full_content)} chars)'}})
            
            ideas_data = self._parse_ideas_response(full_content, count)
            
            # Step 4: 验证和补充
            if callback:
                callback({'type': 'progress', 'data': {'step': '优化完善', 'progress': 80, 'message': '正在优化 Ideas 质量...'}})
            
            ideas = self._validate_and_enrich(ideas_data, count)
            
            # Step 5: 完成
            if callback:
                callback({'type': 'progress', 'data': {'step': '完成', 'progress': 100, 'message': f'成功生成 {len(ideas)} 个 Ideas!'}})
            
            return ideas
            
        except Exception as e:
            logger.error(f"Idea generation failed: {e}")
            if callback:
                callback({'type': 'error', 'data': {'message': str(e)}})
            raise
    
    def _build_ideas_prompt(self, direction: str, count: int, category: str) -> str:
        """构建 Ideas 生成 Prompt"""
        category_map = {
            "general": "极客气质、技术驱动、低成本、高毛利的 ToC 产品",
            "ai-agent": "AI Agent 辅助工具，解决开发者真实痛点",
            "dev-tools": "开发者工具，CLI/API优先，开源友好",
            "privacy": "隐私安全工具，加密、数据保护",
            "productivity": "效率工具，自动化、工作流优化"
        }
        
        return f"""你是一位专业的产品顾问，专注于挖掘真实痛点并生成可变现的项目 Ideas。

任务：生成 {count} 个高质量、可变现的项目 Ideas
定位：{category_map.get(category, category_map["general"])}
方向：{direction or "不限，自由发挥"}

核心要求：
1. 痛点驱动 - 每个项目必须解决真实、具体、高频的痛点
2. 市场验证 - 有竞品或类似成功案例，数据要具体
3. 技术可行 - 个人开发者或小团队可执行，6-12 周内可完成 MVP
4. 变现清晰 - 明确的定价策略和收入预测，毛利率 > 70%
5. 极客气质 - 开源友好、CLI/API优先、隐私保护

**输出格式要求（严格遵守）**:
1. 只输出一个 JSON 数组，不要任何其他文本
2. 不要使用 Markdown 代码块标记（不要 ```json）
3. 确保 JSON 格式完整、可解析
4. 字符串中的特殊字符必须正确转义

JSON 格式示例:
[
  {{
    "name": "项目名称",
    "tagline": "一句话描述",
    "pain_point": "痛点描述",
    "solution": "解决方案",
    "target_user": "目标用户",
    "market_size": "市场规模",
    "competitors": "竞品",
    "pricing": "定价",
    "revenue": "收入预测",
    "tech_stack": "技术栈",
    "advantage": "优势",
    "score": 9.0,
    "tags": ["标签 1", "标签 2"]
  }}
]

开始生成 {count} 个 Ideas（只输出 JSON 数组）:"""
    
    def _parse_ideas_response(self, response: str, expected_count: int) -> List[Dict]:
        """解析模型返回的 Ideas"""
        import re
        
        # 调试：记录响应开头
        logger.info(f"Response preview: {response[:500]}...")
        
        # 清理响应
        response = response.strip()
        
        # 策略 1: 查找 ```json 代码块
        match = re.search(r'```json\s*([\s\S]*?)\s*```', response, re.DOTALL)
        if match:
            json_str = match.group(1)
            logger.info(f"🔧 Found JSON in markdown block, length: {len(json_str)}")
            try:
                # 清理尾部逗号
                json_str = re.sub(r',\s*([\]\}])', r'\1', json_str)
                # 修复转义引号
                json_str = json_str.replace('\\"', '"')
                data = json.loads(json_str)
                if isinstance(data, list):
                    logger.info(f"✅ Markdown JSON parse successful, got {len(data)} items")
                    return data
            except json.JSONDecodeError as e:
                logger.warning(f"Markdown JSON parse failed: {e}")
        
        # 策略 2: 查找第一个 [ 开始的位置
        if not response.startswith('['):
            start_idx = response.find('[')
            if start_idx > 0:
                logger.info(f"🔧 Skipping {start_idx} chars before JSON array")
                response = response[start_idx:]
        
        # 策略 3: 尝试直接解析
        try:
            data = json.loads(response)
            if isinstance(data, list):
                logger.info(f"✅ Direct JSON parse successful, got {len(data)} items")
                return data
        except json.JSONDecodeError as e:
            logger.warning(f"Direct parse failed: {e}")
        
        # 策略 3.5: 处理双重转义的引号（SSE 传输导致）
        try:
            # 修复双重转义的引号：\" -> "
            fixed_response = response.replace('\\"', '"')
            data = json.loads(fixed_response)
            if isinstance(data, list):
                logger.info(f"✅ Fixed double-escaped JSON, got {len(data)} items")
                return data
        except json.JSONDecodeError as e:
            logger.warning(f"Fixed JSON parse failed: {e}")
        
        # 策略 3.6: 处理不完整的 JSON（模型生成被截断）
        try:
            # 查找最后一个完整的对象
            fixed_response = response.replace('\\"', '"')
            
            # 尝试找到最后一个完整的 }
            last_brace = fixed_response.rfind('}')
            if last_brace > 0 and last_brace < len(fixed_response) - 1:
                # 尝试截断到最后一个完整的对象
                truncated = fixed_response[:last_brace + 1] + ']'
                data = json.loads(truncated)
                if isinstance(data, list) and len(data) > 0:
                    logger.warning(f"⚠️ Used truncated JSON, got {len(data)} items (may be incomplete)")
                    return data
        except json.JSONDecodeError as e:
            logger.warning(f"Truncated JSON parse failed: {e}")
        
        # 策略 4: 提取数组部分
        match = re.search(r'\[([\\s\\S]*?)\\]\s*$', response)
        if match:
            json_str = '[' + match.group(1) + ']'
            json_str = re.sub(r',\s*([\\]\\}])', r'\\1', json_str)
            
            # 自动修复常见错误
            json_str = re.sub(r'\\}\s*\\{', r'}, {', json_str)
            json_str = re.sub(r'\\]\s*\\[', r'], [', json_str)
            json_str = re.sub(r"'([^']*)'", r'"\1"', json_str)
            json_str = json_str.replace('\\\\"', '"')
            
            try:
                data = json.loads(json_str)
                if isinstance(data, list):
                    logger.info(f"✅ Array extract parse successful, got {len(data)} items")
                    return data
            except json.JSONDecodeError as e:
                logger.warning(f"Array extract parse failed: {e}")
                logger.debug(f"Failed JSON: {json_str[:500]}")
        
        # 策略 5: 使用 json5 或更宽松的解析
        try:
            # 尝试使用 json5 库（如果可用）
            import json5
            json_str = response.strip()
            logger.info(f"🔧 Attempting JSON5 parse: {json_str}")
            if not json_str.startswith('['):
                start_idx = json_str.find('[')
                if start_idx > 0:
                    json_str = json_str[start_idx:]
            data = json5.loads(json_str)
            if isinstance(data, list):
                logger.info(f"✅ JSON5 parse successful, got {len(data)} items")
                return data
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"JSON5 parse failed: {e}")
        
        # Fallback
        logger.warning("❌ All parse strategies failed, using fallback")
        logger.debug(f"Full response: {response[:2000]}...")
        logger.info("🔄 Using fallback ideas")
        return self._generate_fallback_ideas(expected_count)
    
    def _validate_and_enrich(
        self,
        ideas_data: List[Dict],
        expected_count: int
    ) -> List[IdeaItem]:
        """验证和补充 Ideas 数据"""
        ideas = []
        
        for item in ideas_data:
            try:
                idea = IdeaItem(
                    name=item.get("name", f"Idea {len(ideas)+1}"),
                    tagline=item.get("tagline", "点击查看详细描述"),
                    pain_point=item.get("pain_point", "痛点描述"),
                    solution=item.get("solution", "解决方案"),
                    target_user=item.get("target_user", "开发者/极客"),
                    market_size=item.get("market_size", "100 万 + 用户"),
                    competitors=item.get("competitors", "竞品 A, 竞品 B"),
                    pricing=item.get("pricing", "$5-15/月"),
                    revenue=item.get("revenue", "$3000-10000/月"),
                    tech_stack=item.get("tech_stack", "Rust/Go/React"),
                    advantage=item.get("advantage", "开源、CLI、隐私优先"),
                    score=float(item.get("score", 8.5)),
                    tags=item.get("tags", ["可变现", "痛点驱动"])
                )
                ideas.append(idea)
            except Exception as e:
                logger.warning(f"Failed to parse idea item: {e}")
        
        # 如果数量不足，补充 fallback
        while len(ideas) < expected_count:
            ideas.append(IdeaItem(
                name=f"Backup Idea {len(ideas)+1}",
                tagline="备用 Ideas",
                pain_point="常见痛点",
                solution="智能解决方案",
                target_user="广大用户",
                market_size="百万级市场",
                competitors="多个竞品",
                pricing="$9/月",
                revenue="$5000/月",
                tech_stack="现代技术栈",
                advantage="差异化竞争",
                score=8.0,
                tags=["备用"]
            ))
        
        return ideas[:expected_count]
    
    def _generate_fallback_ideas(self, count: int) -> List[Dict]:
        """生成 Fallback Ideas"""
        templates = [
            {
                "name": "TabKeeper",
                "tagline": "智能标签页管理器",
                "pain_point": "浏览器 50+ 标签页，内存爆炸，找不到需要的",
                "solution": "智能分组 + 自动休眠 + 全文搜索 + 跨设备同步",
                "target_user": "重度浏览器用户、开发者",
                "market_size": "1 亿 + 浏览器用户",
                "competitors": "OneTab (免费), Workona ($7/月)",
                "pricing": "免费 + $4/月同步",
                "revenue": "2 万用户 × 8% × $4 = $6,400/月",
                "tech_stack": "Chrome/FF扩展 + Node.js",
                "advantage": "本地优先、加密同步、快捷键",
                "score": 9.2,
                "tags": ["效率", "浏览器", "同步"]
            },
            {
                "name": "PassVault",
                "tagline": "无密码身份验证器",
                "pain_point": "2FA 换手机麻烦，密码管理器还是用密码",
                "solution": "FIDO2 硬件密钥 + 生物识别 + 云同步 + 一键登录",
                "target_user": "安全敏感用户、开发者",
                "market_size": "5 亿 + 互联网用户",
                "competitors": "1Password ($30/年), YubiKey ($50)",
                "pricing": "$10/月或$99 一次性",
                "revenue": "1 万用户 × 10% × $10 = $10,000/月",
                "tech_stack": "FIDO2 + Swift/Flutter",
                "advantage": "无密码、FIDO2、开源协议",
                "score": 9.5,
                "tags": ["安全", "认证", "硬件"]
            }
        ]
        
        result = []
        for i in range(count):
            if i < len(templates):
                result.append(templates[i])
            else:
                result.append({
                    "name": f"Idea {i+1}",
                    "tagline": "优质 Ideas",
                    "pain_point": "真实痛点",
                    "solution": "智能方案",
                    "target_user": "目标用户",
                    "market_size": "百万市场",
                    "competitors": "有竞品",
                    "pricing": "$9/月",
                    "revenue": "$5000/月",
                    "tech_stack": "现代栈",
                    "advantage": "差异化",
                    "score": 8.5,
                    "tags": ["通用"]
                })
        
        return result
    
    async def _update_progress(
        self,
        state: AgentState,
        step: str,
        progress: int,
        message: str,
        callback=None,
        metadata: Dict = None
    ):
        """更新进度"""
        self.state = state
        progress_data = {
            "state": state.value,
            "step": step,
            "progress": progress,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        # 如果 metadata 有 thinking_preview 或 content_preview，直接放到顶层
        if metadata:
            if "thinking_preview" in metadata:
                progress_data["thinking_preview"] = metadata["thinking_preview"]
            if "content_preview" in metadata:
                progress_data["content_preview"] = metadata["content_preview"]
        
        self.progress_history.append(progress_data)
        
        if callback:
            await callback(progress_data)


class DetailGenerationAgent:
    """
    详细方案生成 Agent
    负责为单个 Idea 生成详细技术方案
    """
    
    def __init__(self, model_client):
        self.model_client = model_client
        self.state = AgentState.IDLE
    
    async def generate_detail(
        self,
        idea: IdeaItem,
        callback=None
    ) -> str:
        """
        生成详细方案
        
        Args:
            idea: Idea 对象
            callback: 进度回调
            
        Returns:
            Markdown 格式的详细方案
        """
        try:
            # Step 1: 分析 Idea
            await self._update_progress(
                AgentState.THINKING,
                "分析 Idea",
                15,
                "正在分析项目核心要素...",
                callback
            )
            
            # Step 2: 构建 Prompt
            prompt = self._build_detail_prompt(idea)
            
            # Step 3: 生成方案
            await self._update_progress(
                AgentState.GENERATING,
                "生成方案",
                40,
                "正在生成详细技术方案...",
                callback
            )
            
            plan = await self.model_client.generate(prompt)
            
            # Step 4: 格式化和优化
            await self._update_progress(
                AgentState.REFINING,
                "优化格式",
                70,
                "正在优化方案格式...",
                callback
            )
            
            plan = self._format_plan(plan)
            
            # Step 5: 完成
            await self._update_progress(
                AgentState.DONE,
                "完成",
                100,
                "详细方案生成完成!",
                callback
            )
            
            return plan
            
        except Exception as e:
            logger.error(f"Detail generation failed: {e}")
            await self._update_progress(
                AgentState.ERROR,
                "失败",
                0,
                f"生成失败：{str(e)}",
                callback
            )
            return self._generate_fallback_detail(idea)
    
    def _build_detail_prompt(self, idea: IdeaItem) -> str:
        """构建详细方案 Prompt"""
        return f"""针对这个变现项目，提供详细的技术方案和落地计划:

**项目名称**: {idea.name}
**核心概念**: {idea.tagline}
**痛点**: {idea.pain_point}
**解决方案**: {idea.solution}

请输出以下详细内容（使用 Markdown 格式）:

## 1. 功能清单 (MVP)
列出 5-8 个核心功能，按优先级排序

## 2. 技术架构
- 推荐技术栈（前端/后端/数据库/基础设施）
- 系统架构设计
- 关键技术选型理由

## 3. 开发路线图
- Phase 1 (4 周): 核心功能
- Phase 2 (4 周): 用户反馈迭代
- Phase 3 (4 周): 商业化功能

## 4. 成本估算
- 开发成本
- 运维成本（服务器/域名/第三方服务）
- 获客成本

## 5. 变现策略
- 定价方案（免费版/专业版/企业版）
- 获客渠道
- 收入预测（6 个月/12 个月）

## 6. 风险评估
- 技术风险及应对
- 市场风险及应对
- 竞争风险及应对

## 7. PMF 验证
- MVP 验证方案
- 测试渠道
- 关键指标

要求:
- 具体可执行，不要泛泛而谈
- 包含代码示例或技术细节
- 考虑个人开发者可执行
- 极客气质：开源、CLI/API、隐私"""
    
    def _format_plan(self, plan: str) -> str:
        """格式化方案"""
        # 移除 Markdown 代码块标记
        import re
        plan = re.sub(r'```markdown\n?', '', plan, flags=re.IGNORECASE)
        plan = re.sub(r'```\n?', '', plan, flags=re.IGNORECASE)
        return plan.strip()
    
    def _generate_fallback_detail(self, idea: IdeaItem) -> str:
        """生成 Fallback 方案"""
        return f"""# {idea.name} - 详细方案

## 1. 功能清单
- 核心功能 A
- 核心功能 B
- 核心功能 C
- 用户认证
- 数据同步

## 2. 技术架构
**前端**: React + TypeScript
**后端**: Node.js / Go
**数据库**: PostgreSQL + Redis

## 3. 开发路线
**Phase 1**: MVP 核心功能 (4 周)
**Phase 2**: 用户反馈迭代 (4 周)
**Phase 3**: 商业化功能 (4 周)

## 4. 成本
- 运维：$50/月
- 第三方：$20/月

## 5. 变现
- 定价：$9/月
- 收入：1000 用户 × 5% × $9 = $450/月

## 6. 风险
- 技术：中等
- 市场：有验证

## 7. PMF
- 构建 MVP
- 发布 Product Hunt
- 收集反馈"""
    
    async def _update_progress(
        self,
        state: AgentState,
        step: str,
        progress: int,
        message: str,
        callback=None
    ):
        """更新进度"""
        self.state = state
        if callback:
            await callback({
                "state": state.value,
                "step": step,
                "progress": progress,
                "message": message,
                "timestamp": datetime.now().isoformat()
            })
