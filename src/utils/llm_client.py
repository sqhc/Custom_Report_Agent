"""LLM 客户端 - 支持重试和降级策略"""
import json
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from pathlib import Path
import hashlib
import time

import requests
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class HeaderDetectionResult:
    """表头检测结果"""
    header_row: int  # 表头所在的行号（0-based）
    data_start_row: int  # 数据开始的行号（0-based）
    column_mapping: Dict[str, str]  # 字段名 -> 列名映射
    confidence: float  # 置信度
    raw_response: str  # 原始响应


class LLMClient:
    """LLM 客户端，支持 Ollama 和 API 调用"""

    # 缓存目录
    CACHE_DIR = Path(__file__).parent.parent.parent / ".llm_cache"
    CACHE_DIR.mkdir(exist_ok=True)

    def __init__(
        self,
        primary_host: str = None,
        primary_model: str = None,
        fallback_model: str = None,
        timeout: int = 120,
        max_retries: int = 3,
        enable_cache: bool = True
    ):
        self.primary_host = primary_host or os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        self.primary_model = primary_model or os.getenv('OLLAMA_MODEL', 'qwen3.5:27b')
        self.fallback_model = fallback_model or 'glm-4.7-flash'
        self.timeout = timeout
        self.max_retries = max_retries
        self.enable_cache = enable_cache

        logger.info(f"LLM 客户端初始化：主模型={self.primary_model}, 降级模型={self.fallback_model}")

    def _get_cache_key(self, prompt: str, model: str) -> str:
        """生成缓存键"""
        cache_str = f"{model}:{prompt}"
        return hashlib.md5(cache_str.encode()).hexdigest()

    def _load_from_cache(self, cache_key: str) -> Optional[str]:
        """从缓存加载结果"""
        if not self.enable_cache:
            return None

        cache_file = self.CACHE_DIR / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.debug(f"从缓存加载：{cache_key[:16]}...")
                    return data.get('response')
            except Exception as e:
                logger.warning(f"缓存读取失败：{e}")
        return None

    def _save_to_cache(self, cache_key: str, prompt: str, response: str, model: str):
        """保存结果到缓存"""
        if not self.enable_cache:
            return

        try:
            cache_file = self.CACHE_DIR / f"{cache_key}.json"
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'prompt': prompt,
                    'response': response,
                    'model': model,
                    'timestamp': time.time()
                }, f, ensure_ascii=False, indent=2)
            logger.debug(f"缓存已保存：{cache_key[:16]}...")
        except Exception as e:
            logger.warning(f"缓存保存失败：{e}")

    def _call_ollama(self, model: str, prompt: str, system: str = "") -> Optional[str]:
        """调用 Ollama API"""
        url = f"{self.primary_host}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": False
        }

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            return result.get('response', '')
        except requests.exceptions.Timeout:
            logger.error(f"Ollama 调用超时 (模型：{model})")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama 请求失败：{e}")
            return None
        except Exception as e:
            logger.error(f"Ollama 响应解析失败：{e}")
            return None

    def call_with_retry(
        self,
        prompt: str,
        system: str = "",
        require_json: bool = False
    ) -> Optional[str]:
        """
        调用 LLM，带重试和降级策略

        Args:
            prompt: 用户提示词
            system: 系统提示词
            require_json: 是否要求返回 JSON 格式

        Returns:
            LLM 返回的文本，失败返回 None
        """
        # 尝试从缓存加载
        cache_key = self._get_cache_key(prompt, self.primary_model)
        cached = self._load_from_cache(cache_key)
        if cached:
            if not require_json or self._is_valid_json(cached):
                return cached
            logger.debug("缓存结果不符合 JSON 要求，重新请求")

        # 尝试主模型（带重试）
        for attempt in range(1, self.max_retries + 1):
            logger.info(f"调用主模型 {self.primary_model} (尝试 {attempt}/{self.max_retries})")
            result = self._call_ollama(self.primary_model, prompt, system)

            if result is None:
                logger.warning(f"主模型调用失败，尝试 {attempt + 1}")
                continue

            # 检查是否为有效 JSON（如果需要）
            if require_json and not self._is_valid_json(result):
                logger.warning(f"主模型返回非 JSON 格式：{result[:100]}...")
                continue

            logger.info("主模型调用成功")
            self._save_to_cache(cache_key, prompt, result, self.primary_model)
            return result

        # 降级到备用模型
        logger.warning(f"主模型 {self.max_retries} 次重试失败，降级到 {self.fallback_model}")
        fallback_cache_key = self._get_cache_key(prompt, self.fallback_model)

        for attempt in range(1, self.max_retries + 1):
            logger.info(f"调用降级模型 {self.fallback_model} (尝试 {attempt}/{self.max_retries})")
            result = self._call_ollama(self.fallback_model, prompt, system)

            if result is None:
                logger.warning(f"降级模型调用失败，尝试 {attempt + 1}")
                continue

            if require_json and not self._is_valid_json(result):
                logger.warning(f"降级模型返回非 JSON 格式：{result[:100]}...")
                continue

            logger.info("降级模型调用成功")
            self._save_to_cache(fallback_cache_key, prompt, result, self.fallback_model)
            return result

        logger.error("所有模型调用均失败")
        return None

    def _extract_raw_json(self, text: str) -> str:
        """从文本中提取原始 JSON 字符串（去除 markdown 代码块标记）"""
        if not text:
            return ""

        text = text.strip()
        # 去除 ```json 或 ``` 开头
        if text.startswith('```json'):
            text = text[7:].strip()
        elif text.startswith('```'):
            text = text[3:].strip()

        # 去除末尾的 ```
        if text.endswith('```'):
            text = text[:-3].strip()

        return text

    def _is_valid_json(self, text: str) -> bool:
        """检查文本是否为有效 JSON"""
        if not text:
            return False
        try:
            text = self._extract_raw_json(text)
            json.loads(text)
            return True
        except (json.JSONDecodeError, ValueError):
            return False

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """从文本中提取 JSON"""
        if not text:
            return None

        try:
            text = self._extract_raw_json(text)
            return json.loads(text)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"JSON 解析失败：{e}, 文本：{text[:200]}...")
            return None


# 全局 LLM 客户端实例
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """获取全局 LLM 客户端实例"""
    global _llm_client
    if _llm_client is None:
        from .config import Config
        _llm_client = LLMClient(
            primary_host=Config.OLLAMA_HOST,
            primary_model=Config.OLLAMA_MODEL,
            timeout=Config.OLLAMA_TIMEOUT
        )
    return _llm_client
