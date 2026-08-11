"""
统一模型调用接口
支持 Hermes, OpenAI, Custom API
"""

import aiohttp
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """模型配置"""
    provider: str = "hermes"  # hermes, openai, custom
    hermes_url: str = "http://localhost:8080/api/chat"
    openai_api_key: str = ""
    openai_model: str = "gpt-4"
    custom_base_url: str = ""
    custom_model: str = "auto"  # auto = 自动检测
    custom_api_key: str = ""  # 新增：支持 API Key
    temperature: float = 0.7
    max_tokens: int = 16384  # 增加到 16384
    timeout: int = 600  # 增加到 10 分钟


class ModelClient:
    """
    统一模型客户端
    支持多种 AI 提供商
    """
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
    
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
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def generate(self, prompt: str) -> str:
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
            if self.config.provider == "hermes":
                return await self._call_hermes(prompt)
            elif self.config.provider == "openai":
                return await self._call_openai(prompt)
            elif self.config.provider == "custom":
                return await self._call_custom(prompt)
            else:
                raise ValueError(f"Unknown provider: {self.config.provider}")
        except Exception as e:
            logger.error(f"Model generation failed: {e}")
            raise

    async def generate_stream(self, prompt: str):
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
            if self.config.provider == "custom":
                async for chunk in self._call_custom_stream(prompt):
                    yield chunk
            else:
                # 非流式 fallback
                result = await self.generate(prompt)
                yield {"type": "content", "data": result}
        except Exception as e:
            logger.error(f"Model stream generation failed: {e}")
            yield {"type": "error", "data": str(e)}
    
    async def _call_hermes(self, prompt: str) -> str:
        """调用 Hermes API"""
        url = self.config.hermes_url
        
        payload = {
            "message": prompt,
            "stream": False
        }
        
        async with self.session.post(url, json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(f"Hermes API error: {response.status} - {error_text}")
            
            data = await response.json()
            
            # 尝试不同的响应字段
            if "response" in data:
                return data["response"]
            elif "content" in data:
                return data["content"]
            elif "message" in data:
                return data["message"]
            else:
                logger.warning(f"Unexpected Hermes response format: {data}")
                return str(data)
    
    async def _call_openai(self, prompt: str) -> str:
        """调用 OpenAI API"""
        url = "https://api.openai.com/v1/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.openai_api_key}"
        }
        
        payload = {
            "model": self.config.openai_model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens
        }
        
        async with self.session.post(url, headers=headers, json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(f"OpenAI API error: {response.status} - {error_text}")
            
            data = await response.json()
            return data["choices"][0]["message"]["content"]
    
    async def _call_custom(self, prompt: str) -> str:
        """调用 Custom API（非流式）"""
        url = f"{self.config.custom_base_url}/chat/completions"
        
        # 自动检测或获取 model
        model = self.config.custom_model
        if model == "auto":
            model = await self._auto_detect_model()
            logger.info(f"🔄 Auto-detected model: {model}")
        
        headers = {
            "Content-Type": "application/json",
        }
        
        # 如果有 API Key，添加到 headers
        if self.config.custom_api_key:
            headers["Authorization"] = f"Bearer {self.config.custom_api_key}"
        
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": False  # 非流式
        }
        
        logger.info(f"📡 Calling Custom API: {url} with model: {model}")
        logger.debug(f"📝 Request payload: {json.dumps(payload, ensure_ascii=False)[:500]}")
        
        async with self.session.post(url, headers=headers, json=payload) as response:
            logger.info(f"📡 Response status: {response.status}")
            
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"❌ Custom API error: {response.status} - {error_text[:500]}")
                raise RuntimeError(f"Custom API error: {response.status} - {error_text[:200]}")
            
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

    async def _call_custom_stream(self, prompt: str):
        """调用 Custom API（流式）"""
        url = f"{self.config.custom_base_url}/chat/completions"
        
        # 自动检测或获取 model
        model = self.config.custom_model
        if model == "auto":
            model = await self._auto_detect_model()
            logger.info(f"🔄 Auto-detected model: {model}")
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        
        # 如果有 API Key，添加到 headers
        if self.config.custom_api_key:
            headers["Authorization"] = f"Bearer {self.config.custom_api_key}"
        
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": True  # 流式
        }
        
        logger.info(f"📡 Calling Custom API (stream): {url} with model: {model}")
        
        async with self.session.post(url, headers=headers, json=payload) as response:
            logger.info(f"📡 Response status: {response.status}")
            
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"❌ Custom API error: {response.status} - {error_text[:500]}")
                raise RuntimeError(f"Custom API error: {response.status} - {error_text[:200]}")
            
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
                        
                        # 提取 thinking (如果有)
                        choice = data.get("choices", [{}])[0]
                        delta = choice.get("delta", {})
                        
                        # 检查 reasoning (thinking)
                        if "reasoning" in delta:
                            thinking = delta["reasoning"]
                            if thinking:
                                full_thinking += thinking
                                yield {"type": "thinking", "data": thinking}
                        elif "reasoning_content" in choice:
                            thinking = choice["reasoning_content"]
                            if thinking:
                                full_thinking += thinking
                                yield {"type": "thinking", "data": thinking}
                        
                        # 提取 content
                        if "content" in delta:
                            content = delta["content"]
                            if content is not None:
                                full_content += content
                                yield {"type": "content", "data": content}
                        elif "content" in choice:
                            content = choice["content"]
                            if content:
                                full_content += content
                                yield {"type": "content", "data": content}
                                
                    except json.JSONDecodeError as e:
                        continue
            
            # 流式结束后统一打印日志
            logger.info(f"✅ Stream completed: thinking={len(full_thinking)} chars, content={len(full_content)} chars")
            logger.debug(f"📝 Full thinking: {full_thinking[:500]}...")
            logger.debug(f"📝 Full content: {full_content[:500]}...")
    
    async def _auto_detect_model(self) -> str:
        """自动检测 Custom API 支持的模型（返回第一个）"""
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
        """检测 Custom API 支持的模型列表"""
        base_url = self.config.custom_base_url.rstrip('/')
        
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
                        logger.info(f"✅ Found {len(model_names)} models: {model_names}")
                        return model_names
                
                logger.warning("⚠️  Response doesn't contain models")
                return []
        
        except Exception as e:
            logger.error(f"❌ Model detection failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def update_config(self, new_config: Dict[str, Any]):
        """更新配置"""
        for key, value in new_config.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        logger.info(f"Model config updated: {self.config}")
