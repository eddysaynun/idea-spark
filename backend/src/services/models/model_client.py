"""OpenAI-compatible 模型调用接口。"""

import json
import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from utils.http_client import request_text

logger = logging.getLogger(__name__)


class TransientModelError(RuntimeError):
    pass


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
    
    def __init__(self, config: ModelConfig, service_binding=None):
        self.config = config
        self.service_binding = service_binding
    
    async def __aenter__(self):
        """异步上下文管理器进入"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        return None

    async def close(self):
        """关闭复用的 HTTP session。"""
        return None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(TransientModelError),
        reraise=True,
    )
    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        *,
        thinking: bool = False,
        max_tokens: Optional[int] = None,
        trace_id: str = "",
        stage: str = "",
    ) -> str:
        """
        生成文本（非流式）
        
        Args:
            prompt: 输入提示
            
        Returns:
            模型生成的文本
        """
        started = time.perf_counter()
        try:
            result = await self._call_compatible(
                prompt, model, thinking=thinking, max_tokens=max_tokens
            )
            self._log_call(
                trace_id, stage, model, thinking, False, started, len(result), True
            )
            return result
        except Exception as e:
            self._log_call(trace_id, stage, model, thinking, False, started, 0, False)
            logger.error(f"Model generation failed: {e}")
            raise

    async def generate_stream(
        self,
        prompt: str,
        model: Optional[str] = None,
        *,
        thinking: bool = False,
        max_tokens: Optional[int] = None,
        trace_id: str = "",
        stage: str = "",
    ):
        """
        流式生成文本
        
        Args:
            prompt: 输入提示
            
        Yields:
            流式数据块 (包含 thinking 和 content)
        """
        started = time.perf_counter()
        output_chars = 0
        try:
            async for chunk in self._call_compatible_stream(
                prompt, model, thinking=thinking, max_tokens=max_tokens
            ):
                if chunk["type"] == "content":
                    output_chars += len(chunk["data"])
                yield chunk
            self._log_call(
                trace_id, stage, model, thinking, True, started, output_chars, True
            )
        except Exception as e:
            self._log_call(
                trace_id, stage, model, thinking, True, started, output_chars, False
            )
            logger.error(f"Model stream generation failed: {e}")
            yield {"type": "error", "data": str(e)}

    def _log_call(
        self,
        trace_id: str,
        stage: str,
        model: Optional[str],
        thinking: bool,
        stream: bool,
        started: float,
        output_chars: int,
        success: bool,
    ) -> None:
        logger.info(json.dumps({
            "event": "model_call",
            "trace_id": trace_id,
            "stage": stage,
            "model": model or self.config.model,
            "thinking": thinking,
            "stream": stream,
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "output_chars": output_chars,
            "success": success,
        }, ensure_ascii=False))
    
    async def _call_compatible(
        self,
        prompt: str,
        model_override: Optional[str] = None,
        *,
        thinking: bool = False,
        max_tokens: Optional[int] = None,
    ) -> str:
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
            "max_tokens": max_tokens or self.config.max_tokens,
            "stream": False  # 非流式
        }
        self._apply_model_compatibility(payload, model, thinking)
        
        logger.info(f"📡 Calling compatible API: {url} with model: {model}")
        
        if self.service_binding is not None:
            response = await self._binding_fetch(
                url,
                method="POST",
                headers=headers,
                body=json.dumps(payload),
            )
            text_data = await response.text()
            return self._parse_completion_response(response.status, text_data)

        status, text_data = await request_text(
            url, method="POST", headers=headers, body=json.dumps(payload), timeout=self.config.timeout
        )
        return self._parse_completion_response(status, text_data)

    async def _call_compatible_stream(
        self,
        prompt: str,
        model_override: Optional[str] = None,
        *,
        thinking: bool = False,
        max_tokens: Optional[int] = None,
    ):
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
            "max_tokens": max_tokens or self.config.max_tokens,
            "stream": True  # 流式
        }
        self._apply_model_compatibility(payload, model, thinking)
        
        logger.info(f"📡 Calling compatible API (stream): {url} with model: {model}")
        
        if self.service_binding is not None:
            response = await self._binding_fetch(
                url,
                method="POST",
                headers=headers,
                body=json.dumps(payload),
            )
            if response.status != 200:
                error_text = await response.text()
                raise RuntimeError(
                    f"Compatible API error: {response.status} - {error_text[:200]}"
                )
            stream_text = await response.text()
            has_content = False
            for chunk in self._parse_sse_text(stream_text):
                has_content = has_content or chunk["type"] == "content"
                yield chunk
            if not has_content:
                raise RuntimeError(
                    "模型未返回最终内容，可能是推理耗尽了输出预算"
                )
            return

        status, stream_text = await request_text(
            url, method="POST", headers=headers, body=json.dumps(payload), timeout=self.config.timeout
        )
        if status != 200:
            raise RuntimeError(f"Compatible API error: {status} - {stream_text[:200]}")
        has_content = False
        for chunk in self._parse_sse_text(stream_text):
            has_content = has_content or chunk["type"] == "content"
            yield chunk
        if not has_content:
            raise RuntimeError("模型未返回最终内容，可能是推理耗尽了输出预算")

    async def _binding_fetch(self, url: str, **options):
        """通过 Cloudflare Service Binding 调用模型代理。"""
        try:
            response = await self.service_binding.fetch(url, **options)
            logger.info("📡 Service Binding response status: %s", response.status)
            return response
        except Exception:
            logger.exception("❌ Model proxy Service Binding request failed")
            raise TransientModelError("Model proxy request failed") from None

    @staticmethod
    def _parse_completion_response(status: int, text_data: str) -> str:
        logger.info("📡 Response status: %s", status)
        if status != 200:
            logger.error("❌ Compatible API error: %s - %s", status, text_data[:500])
            error = f"Compatible API error: {status} - {text_data[:200]}"
            if status == 429 or status >= 500:
                raise TransientModelError(error)
            raise RuntimeError(error)
        if not text_data or not text_data.strip():
            raise RuntimeError("Empty response from API")
        try:
            data = json.loads(text_data)
            content = data["choices"][0]["message"]["content"]
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON response: {exc}") from exc
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Invalid response structure: {exc}") from exc
        logger.info("✅ Content extracted, length: %s", len(content))
        return content

    @classmethod
    def _parse_sse_text(cls, stream_text: str):
        """解析 Service Binding 返回的 OpenAI-compatible SSE 文本。"""
        for line in stream_text.splitlines():
            line = line.strip()
            if not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str == "[DONE]":
                break
            try:
                choice = json.loads(data_str).get("choices", [{}])[0]
            except (json.JSONDecodeError, IndexError, TypeError):
                continue
            thinking, content = cls._extract_stream_parts(choice)
            if thinking:
                yield {"type": "thinking", "data": thinking}
            if content:
                yield {"type": "content", "data": content}

    @staticmethod
    def _apply_model_compatibility(
        payload: Dict[str, Any], model: str, thinking: bool
    ) -> None:
        """为已知模型添加其 OpenAI-compatible 扩展参数。"""
        normalized = model.lower().replace("-", "").replace("_", "")
        if "qwen35" in normalized or "qwen3.5" in model.lower():
            payload["chat_template_kwargs"] = {"enable_thinking": thinking}

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
    
    def available_models(self) -> List[str]:
        """返回部署时授权给工作台的模型。"""
        return [self.config.model]

    def validate_model(self, model: str) -> str:
        """只允许工作台使用部署时配置的模型。"""
        selected = model or self.config.model
        if selected not in self.available_models():
            raise ValueError("所选模型不可用，请刷新模型列表后重试")
        return selected
