"""OpenAI-compatible 模型调用接口。"""

import aiohttp
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """模型配置"""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    api_key: str = ""
    temperature: float = 0.7
    max_tokens: int = 16384  # 增加到 16384
    timeout: int = 600  # 增加到 10 分钟


class ModelClient:
    """统一调用用户配置的 OpenAI-compatible 服务。"""
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self._detected_models: List[str] = []
    
    async def __aenter__(self):
        """异步上下文管理器进入"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.timeout)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        if self.session:
            await self.session.close()

    async def close(self):
        """关闭复用的 HTTP session。"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def generate(self, prompt: str, model: Optional[str] = None) -> str:
        """
        生成文本（非流式）
        
        Args:
            prompt: 输入提示
            
        Returns:
            模型生成的文本
        """
        # 确保 session 已初始化
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            )
        
        try:
            return await self._call_compatible(prompt, model)
        except Exception as e:
            logger.error(f"Model generation failed: {e}")
            raise

    async def generate_stream(self, prompt: str, model: Optional[str] = None):
        """
        流式生成文本
        
        Args:
            prompt: 输入提示
            
        Yields:
            流式数据块 (包含 thinking 和 content)
        """
        # 确保 session 已初始化
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            )
        
        try:
            async for chunk in self._call_compatible_stream(prompt, model):
                yield chunk
        except Exception as e:
            logger.error(f"Model stream generation failed: {e}")
            yield {"type": "error", "data": str(e)}
    
    async def _call_compatible(self, prompt: str, model_override: Optional[str] = None) -> str:
        """调用 OpenAI-compatible API（非流式）。"""
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        
        # 自动检测或获取 model
        model = model_override or self.config.model
        if model == "auto":
            model = await self._auto_detect_model()
            logger.info(f"🔄 Auto-detected model: {model}")
        
        headers = {
            "Content-Type": "application/json",
        }
        
        # 如果有 API Key，添加到 headers
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": False  # 非流式
        }
        
        logger.info(f"📡 Calling compatible API: {url} with model: {model}")
        logger.debug(f"📝 Request payload: {json.dumps(payload, ensure_ascii=False)[:500]}")
        
        async with self.session.post(url, headers=headers, json=payload) as response:
            logger.info(f"📡 Response status: {response.status}")
            
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"❌ Compatible API error: {response.status} - {error_text[:500]}")
                raise RuntimeError(f"Compatible API error: {response.status} - {error_text[:200]}")
            
            try:
                text_data = await response.text()
                logger.debug(f"📄 Raw response: {text_data[:500]}")
                
                if not text_data or text_data.strip() == "":
                    logger.error("❌ Empty response from API")
                    raise RuntimeError("Empty response from API")
                
                data = json.loads(text_data)
                logger.info(f"✅ Response received, type: {type(data)}")
                
                if not isinstance(data, dict):
                    logger.error(f"❌ Invalid response format: {type(data)}")
                    raise RuntimeError(f"Invalid response format: {type(data)}")
                
                if "choices" not in data:
                    logger.error(f"❌ No 'choices' in response: {data.keys()}")
                    raise RuntimeError(f"Invalid response structure: missing 'choices'")
                
                if len(data["choices"]) == 0:
                    logger.error("❌ Empty choices array")
                    raise RuntimeError("Empty choices array")
                
                content = data["choices"][0]["message"]["content"]
                logger.info(f"✅ Content extracted, length: {len(content)}")
                return content
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ Failed to parse JSON: {e}")
                logger.error(f"📄 Raw text: {text_data[:1000]}")
                raise RuntimeError(f"Invalid JSON response: {e}")
            except (KeyError, TypeError) as e:
                logger.error(f"❌ Failed to extract content: {e}")
                logger.error(f"📄 Full response: {data if 'data' in locals() else 'N/A'}")
                raise RuntimeError(f"Invalid response structure: {e}")

    async def _call_compatible_stream(self, prompt: str, model_override: Optional[str] = None):
        """调用 OpenAI-compatible API（流式）。"""
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        
        # 自动检测或获取 model
        model = model_override or self.config.model
        if model == "auto":
            model = await self._auto_detect_model()
            logger.info(f"🔄 Auto-detected model: {model}")
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        
        # 如果有 API Key，添加到 headers
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": True  # 流式
        }
        
        logger.info(f"📡 Calling compatible API (stream): {url} with model: {model}")
        
        async with self.session.post(url, headers=headers, json=payload) as response:
            logger.info(f"📡 Response status: {response.status}")
            
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"❌ Compatible API error: {response.status} - {error_text[:500]}")
                raise RuntimeError(f"Compatible API error: {response.status} - {error_text[:200]}")
            
            # 读取流式响应
            full_thinking = ""
            full_content = ""
            
            async for line in response.content:
                line_str = line.decode('utf-8').strip()
                
                if line_str.startswith('data: '):
                    data_str = line_str[6:]
                    
                    if data_str == '[DONE]':
                        break
                    
                    try:
                        data = json.loads(data_str)
                        
                        choice = data.get("choices", [{}])[0]
                        thinking, content = self._extract_stream_parts(choice)
                        if thinking:
                            full_thinking += thinking
                            yield {"type": "thinking", "data": thinking}
                        if content:
                            full_content += content
                            yield {"type": "content", "data": content}
                                
                    except json.JSONDecodeError:
                        continue
            
            # 流式结束后统一打印日志
            logger.info(f"✅ Stream completed: thinking={len(full_thinking)} chars, content={len(full_content)} chars")
            logger.debug(f"📝 Full thinking: {full_thinking[:500]}...")
            logger.debug(f"📝 Full content: {full_content[:500]}...")

    @staticmethod
    def _extract_stream_parts(choice: Dict[str, Any]):
        """兼容 Qwen/vLLM/SGLang 常见 reasoning 与 content 字段位置。"""
        delta = choice.get("delta") or {}
        thinking = (
            delta.get("reasoning_content")
            or delta.get("reasoning")
            or choice.get("reasoning_content")
            or ""
        )
        content = delta.get("content") or choice.get("content") or ""
        return thinking, content
    
    async def _auto_detect_model(self) -> str:
        """自动检测兼容 API 支持的模型（返回第一个）。"""
        models = await self.detect_models()
        if models:
            # 优先选择常见模型
            priority_models = ["gpt-4", "gpt-4-turbo", "claude-3", "qwen", "llama"]
            for priority in priority_models:
                for name in models:
                    if priority in name.lower():
                        logger.info(f"🎯 Selected priority model: {name}")
                        return name
            # 返回第一个
            logger.info(f"🎯 Selected first model: {models[0]}")
            return models[0]
        
        # 如果检测失败，返回默认值
        logger.warning("⚠️  Model detection failed, using default: gpt-4")
        return "gpt-4"
    
    async def detect_models(self) -> List[str]:
        """检测兼容 API 支持的模型列表。"""
        base_url = self.config.base_url.rstrip('/')
        
        # API base 固定为 /v1 格式，只尝试 /models endpoint
        endpoint = f"{base_url}/models"
        
        logger.info(f"🔍 Detecting models from: {endpoint}")
        
        # 确保 session 已初始化
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            )
        
        try:
            async with self.session.get(endpoint) as response:
                logger.info(f"📡 Response status: {response.status}")
                
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to get models: {response.status} - {error_text[:200]}")
                    return []
                
                data = await response.json()
                logger.info(f"📄 Response data type: {type(data)}")
                
                models = []
                
                # 处理不同的响应格式
                if isinstance(data, list):
                    models = data
                elif isinstance(data, dict):
                    if "data" in data and isinstance(data["data"], list):
                        models = data["data"]
                    elif "models" in data and isinstance(data["models"], list):
                        models = data["models"]
                    elif "results" in data and isinstance(data["results"], list):
                        models = data["results"]
                
                if models:
                    # 提取模型名称
                    model_names = []
                    for m in models:
                        if isinstance(m, dict) and "id" in m:
                            model_names.append(m["id"])
                        elif isinstance(m, str):
                            model_names.append(m)
                    
                    if model_names:
                        self._detected_models = model_names
                        logger.info(f"✅ Found {len(model_names)} models: {model_names}")
                        return model_names
                
                logger.warning("⚠️  Response doesn't contain models")
                return []
        
        except Exception as e:
            logger.error(f"❌ Model detection failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def available_models(self) -> List[str]:
        """返回可供工作台选择的模型，不触发远程请求。"""
        return list(dict.fromkeys([self.config.model, *self._detected_models]))

    def validate_model(self, model: str) -> str:
        """只允许工作台使用已配置或已探测到的模型。"""
        selected = model or self.config.model
        if selected not in self.available_models():
            raise ValueError("所选模型不可用，请刷新模型列表后重试")
        return selected

    def update_config(self, new_config: Dict[str, Any]):
        """更新配置"""
        for key, value in new_config.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self._detected_models = []
        logger.info("Model config updated: model=%s", self.config.model)
