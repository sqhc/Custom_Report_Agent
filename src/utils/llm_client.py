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
        enable_cache: bool = True,
        backend: str = None
    ):
        # 后端选择：默认跟随 Config.LLM_BACKEND（即环境变量 LLM_BACKEND）
        if backend is None:
            from .config import Config
            backend = getattr(Config, 'LLM_BACKEND', 'ollama')
        self.backend = (backend or 'ollama').strip().lower()

        if self.backend == 'openai':
            from .config import Config
            # 远程模式：模型默认取 OPENAI_MODEL；降级仅在显式配置时启用
            self.primary_host = primary_host or Config.OPENAI_BASE_URL
            self.primary_model = primary_model or Config.OPENAI_MODEL
            self.fallback_model = fallback_model or Config.OPENAI_FALLBACK_MODEL or ''
        else:
            self.primary_host = primary_host or os.getenv('OLLAMA_HOST', 'http://localhost:11434')
            self.primary_model = primary_model or os.getenv('OLLAMA_MODEL', 'qwen3.5:27b')
            # 保持原有默认降级模型不变
            self.fallback_model = fallback_model or 'glm-4.7-flash'

        self.timeout = timeout
        self.max_retries = max_retries
        self.enable_cache = enable_cache

        logger.info(
            f"LLM 客户端初始化：后端={self.backend}, 主模型={self.primary_model}, "
            f"降级模型={self.fallback_model or '<无>'}"
        )

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

    def _call_openai_compatible(self, model: str, prompt: str, system: str = "") -> Optional[str]:
        """调用 OpenAI 兼容接口（/v1/chat/completions）

        失败时记录包含 HTTP 状态码的错误日志并返回 None，
        以保持与 ``_call_ollama`` 一致的返回约定，便于复用上层重试逻辑。
        """
        from .config import Config

        api_key = Config.OPENAI_API_KEY
        if not api_key:
            logger.error("缺少 OPENAI_API_KEY，无法调用远程模型")
            return None

        # 惰性导入：未安装 openai 时不影响本模块的其它功能
        try:
            from openai import OpenAI
        except ImportError:
            logger.error(
                '未安装 openai 库。请执行：pip install "openai>=1.0.0"，'
                "或设置 LLM_BACKEND=ollama 使用本地模型。"
            )
            return None

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            client = OpenAI(
                api_key=api_key,
                base_url=self.primary_host,
                timeout=self.timeout,
                max_retries=0,  # 重试由上层 call_with_retry 统一管理
            )
            response = client.chat.completions.create(model=model, messages=messages)
            return response.choices[0].message.content or ""
        except Exception as e:
            status = getattr(e, 'status_code', None)
            if not isinstance(status, int):
                status = getattr(getattr(e, 'response', None), 'status_code', None)
            status_part = f"HTTP {status}" if isinstance(status, int) else "无状态码"
            logger.error(
                f"OpenAI 兼容接口调用失败 [{status_part}]：{e} "
                f"(模型={model}, 地址={self.primary_host})"
            )
            return None

    def _call_model(self, model: str, prompt: str, system: str = "") -> Optional[str]:
        """按当前后端分派调用"""
        if self.backend == 'openai':
            return self._call_openai_compatible(model, prompt, system)
        return self._call_ollama(model, prompt, system)

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
            result = self._call_model(self.primary_model, prompt, system)

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

        # 降级到备用模型（未配置降级模型时直接返回失败）
        if not self.fallback_model:
            logger.error("所有模型调用均失败（未配置降级模型）")
            return None

        logger.warning(f"主模型 {self.max_retries} 次重试失败，降级到 {self.fallback_model}")
        fallback_cache_key = self._get_cache_key(prompt, self.fallback_model)

        for attempt in range(1, self.max_retries + 1):
            logger.info(f"调用降级模型 {self.fallback_model} (尝试 {attempt}/{self.max_retries})")
            result = self._call_model(self.fallback_model, prompt, system)

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


def get_llm_client(force_new: bool = False, backend: str = None) -> LLMClient:
    """获取全局 LLM 客户端实例

    后端默认跟随 ``Config.LLM_BACKEND``（环境变量 ``LLM_BACKEND``），
    即 ``ollama`` 使用本地服务，``openai`` 使用兼容 OpenAI 接口的远程服务。

    :param force_new: 为 True 时强制新建实例（不覆盖单例）
    :param backend: 显式指定后端，覆盖配置
    """
    global _llm_client
    from .config import Config

    effective_backend = (backend or getattr(Config, 'LLM_BACKEND', 'ollama') or 'ollama').strip().lower()

    # 配置校验（LLM_BACKEND=ollama 时为空操作）
    if backend is None:
        Config.validate_llm()

    if effective_backend == 'openai':
        kwargs = {
            'backend': effective_backend,
            'primary_host': Config.OPENAI_BASE_URL,
            'primary_model': Config.OPENAI_MODEL,
            'timeout': Config.OPENAI_TIMEOUT,
            'max_retries': Config.LLM_MAX_RETRIES,
        }
    else:
        kwargs = {
            'backend': effective_backend,
            'primary_host': Config.OLLAMA_HOST,
            'primary_model': Config.OLLAMA_MODEL,
            'timeout': Config.OLLAMA_TIMEOUT,
        }

    if force_new:
        return LLMClient(**kwargs)

    if _llm_client is None or getattr(_llm_client, 'backend', None) != effective_backend:
        _llm_client = LLMClient(**kwargs)
    return _llm_client


def reset_llm_client():
    """重置全局客户端缓存（供测试使用）"""
    global _llm_client
    _llm_client = None
