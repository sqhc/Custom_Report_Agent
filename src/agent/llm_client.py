"""LLM 客户端抽象层

支持两种后端：

* ``ollama`` —— 本地 Ollama 服务（默认，行为与改造前完全一致）
* ``openai`` —— 任何兼容 OpenAI 接口的远程服务（OpenAI / DeepSeek / Moonshot 等）

通过环境变量 ``LLM_BACKEND`` 切换，使用 :func:`get_llm_client` 获取客户端实例。

设计要点
--------
* ``openai`` 采用**惰性导入**：未安装该库时，本模块依然可以正常导入，
  只有真正构造 :class:`OpenAICompatibleClient` 时才抛出
  :class:`~src.utils.llm_errors.LLMNotInstalledError`。
* 重试逻辑由本模块自行实现（关闭 SDK 内建重试），
  以便错误信息中能明确携带 HTTP 状态码。
"""
import time
from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Optional

from ..utils.config import Config
from ..utils.llm_errors import (
    LLMClientError,
    LLMConfigError,
    LLMNotInstalledError,
)
from ..utils.logger import setup_logger

logger = setup_logger(__name__)

# 允许重试的 HTTP 状态码（限流与服务端错误）
RETRYABLE_STATUS_CODES = frozenset({408, 409, 429, 500, 502, 503, 504})


class BaseLLMClient(ABC):
    """LLM 客户端抽象基类"""

    #: 后端标识，子类必须覆盖
    backend: str = 'base'

    def __init__(self, model: str, timeout: int = 120, max_retries: int = 3,
                 retry_backoff: float = 1.0):
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------
    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """发送多轮对话请求

        :param messages: 形如 ``[{"role": "system", "content": "..."}, ...]`` 的消息列表
        :return: 模型回复文本
        :raises LLMClientError: 调用失败（消息中包含状态码与尝试次数）
        """

    @abstractmethod
    def generate(self, prompt: str, system: str = "") -> str:
        """单提示文本生成（等价于 Ollama 的 ``/api/generate``）

        :param prompt: 用户提示
        :param system: 系统提示
        :return: 模型回复文本
        """

    def chat_stream(self, messages: List[Dict[str, str]],
                    callback: Optional[Callable[[str], None]] = None) -> str:
        """流式对话请求（默认实现退化为非流式，以兼容不支持流式的后端）"""
        text = self.chat(messages)
        if callback:
            callback(text)
        return text

    def is_available(self) -> bool:
        """客户端是否可用

        注意：这是**非阻塞**检查，不会向服务端发起探活请求，
        以保持与改造前 ``AIReasoner.is_available()`` 相同的语义与耗时。
        """
        return True

    def close(self):
        """释放底层资源（默认无操作）"""

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _build_messages(self, prompt: str, system: str = "") -> List[Dict[str, str]]:
        """把单提示组装为标准消息列表"""
        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _sleep_before_retry(self, attempt: int):
        """指数退避等待（attempt 从 1 开始）"""
        delay = self.retry_backoff * (2 ** (attempt - 1))
        if delay > 0:
            time.sleep(delay)

    def __repr__(self) -> str:  # pragma: no cover - 调试辅助
        return f"<{type(self).__name__} backend={self.backend} model={self.model}>"


class OllamaClient(BaseLLMClient):
    """本地 Ollama 客户端

    封装原有 ``ollama`` 库调用逻辑，行为与改造前保持一致。
    """

    backend = 'ollama'

    def __init__(self, model: str = None, host: str = None, timeout: int = None,
                 max_retries: int = None, retry_backoff: float = None):
        try:
            import ollama
            self._ollama = ollama
            self._available = True
        except ImportError:
            self._ollama = None
            self._available = False

        super().__init__(
            model=model or Config.OLLAMA_MODEL,
            timeout=timeout if timeout is not None else Config.OLLAMA_TIMEOUT,
            max_retries=max_retries if max_retries is not None else Config.LLM_MAX_RETRIES,
            retry_backoff=retry_backoff if retry_backoff is not None else Config.LLM_RETRY_BACKOFF,
        )
        self.host = host or Config.OLLAMA_HOST
        self.client = None

        if self._available:
            self.client = self._ollama.Client(host=self.host)
            logger.info(f"Ollama 客户端初始化完成：模型={self.model}, 主机={self.host}")
        else:
            logger.warning("Ollama 库不可用，AI 功能将受限。请执行 pip install ollama")

    def is_available(self) -> bool:
        return self._available and self.client is not None

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """调用 ``ollama.Client.chat``"""
        if not self.is_available():
            raise LLMClientError("Ollama 不可用：未安装 ollama 库或客户端初始化失败")
        try:
            response = self.client.chat(model=self.model, messages=messages, **kwargs)
            return response["message"]["content"]
        except Exception as e:
            # 与改造前一致：由上层统一捕获并记日志
            raise LLMClientError(f"Ollama 调用失败：{e}") from e

    def generate(self, prompt: str, system: str = "") -> str:
        """通过 ``chat`` 实现单提示生成，避免依赖 responses API"""
        return self.chat(self._build_messages(prompt, system))

    def chat_stream(self, messages: List[Dict[str, str]],
                    callback: Optional[Callable[[str], None]] = None) -> str:
        """流式调用 ``ollama.Client.chat(stream=True)``"""
        if not self.is_available():
            raise LLMClientError("Ollama 不可用：未安装 ollama 库或客户端初始化失败")
        full_response = ""
        for chunk in self.client.chat(model=self.model, messages=messages, stream=True):
            content = chunk.get("message", {}).get("content", "")
            if not content:
                continue
            full_response += content
            if callback:
                callback(content)
        return full_response


class OpenAICompatibleClient(BaseLLMClient):
    """OpenAI 兼容接口客户端

    适用于 OpenAI、DeepSeek、Moonshot 等提供 ``/v1/chat/completions`` 的服务。

    ``openai`` 库为惰性导入：只有真正实例化本类时才需要安装。
    """

    backend = 'openai'

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None,
                 timeout: int = None, max_retries: int = None, retry_backoff: float = None):
        super().__init__(
            model=model or Config.OPENAI_MODEL,
            timeout=timeout if timeout is not None else Config.OPENAI_TIMEOUT,
            max_retries=max_retries if max_retries is not None else Config.LLM_MAX_RETRIES,
            retry_backoff=retry_backoff if retry_backoff is not None else Config.LLM_RETRY_BACKOFF,
        )
        self.api_key = api_key if api_key is not None else Config.OPENAI_API_KEY
        self.base_url = base_url if base_url is not None else Config.OPENAI_BASE_URL

        if not self.api_key:
            raise LLMConfigError(
                "缺少 OPENAI_API_KEY，无法使用 openai 后端。\n"
                "  请设置：export OPENAI_API_KEY=sk-xxxxxxxx"
            )

        # 惰性导入 openai
        try:
            from openai import OpenAI
        except ImportError as e:
            raise LLMNotInstalledError(
                "未安装 openai 库，无法使用 LLM_BACKEND=openai。\n"
                '  请执行：pip install "openai>=1.0.0"\n'
                "  若想继续使用本地 Ollama，请设置 LLM_BACKEND=ollama。"
            ) from e

        # max_retries=0：关闭 SDK 内建重试，统一由本类负责
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=0,
        )
        logger.info(
            f"OpenAI 兼容客户端初始化完成：模型={self.model}, 地址={self.base_url}, "
            f"最大重试={self.max_retries}"
        )

    # ------------------------------------------------------------------
    # 错误处理
    # ------------------------------------------------------------------
    @staticmethod
    def _status_code_of(error: Exception) -> Optional[int]:
        """尽力从异常中提取 HTTP 状态码"""
        for attr in ('status_code', 'http_status', 'code'):
            value = getattr(error, attr, None)
            if isinstance(value, int):
                return value
        response = getattr(error, 'response', None)
        status = getattr(response, 'status_code', None)
        if isinstance(status, int):
            return status
        return None

    @classmethod
    def _is_retryable(cls, error: Exception) -> bool:
        """判断异常是否值得重试

        * 限流 / 服务端错误 / 网络超时 —— 可重试
        * 其它 4xx（401、403、404、400 等）—— 不可重试，立即失败
        """
        import openai  # 局部导入：仅在已确认安装后才可达

        if isinstance(error, (openai.APITimeoutError, openai.APIConnectionError,
                              openai.RateLimitError, openai.InternalServerError)):
            return True

        status = cls._status_code_of(error)
        if status is None:
            # 无状态码（例如网络层错误）：保守重试
            return True
        return status in RETRYABLE_STATUS_CODES

    def _describe(self, error: Exception) -> str:
        """构造包含状态码的可读错误描述"""
        status = self._status_code_of(error)
        status_part = f"HTTP {status}" if status is not None else "无状态码"
        return (
            f"OpenAI 兼容接口调用失败 [{status_part}]：{error} "
            f"(模型={self.model}, 地址={self.base_url})"
        )

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """调用 ``chat.completions.create``，失败时按策略重试"""
        last_error: Optional[Exception] = None
        attempts = 0

        for attempt in range(1, self.max_retries + 1):
            attempts = attempt
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    **kwargs,
                )
                content = response.choices[0].message.content
                logger.debug(f"OpenAI 调用成功（尝试 {attempt}/{self.max_retries}）")
                return content or ""
            except Exception as e:
                last_error = e
                status = self._status_code_of(e)

                if not self._is_retryable(e):
                    logger.error(f"OpenAI 调用遇到不可重试错误：{self._describe(e)}")
                    raise LLMClientError(
                        f"{self._describe(e)}，该错误不可重试（已尝试 {attempt} 次）",
                        status_code=status,
                        attempts=attempt,
                    ) from e

                logger.warning(
                    f"OpenAI 调用失败（尝试 {attempt}/{self.max_retries}）：{self._describe(e)}"
                )
                if attempt < self.max_retries:
                    self._sleep_before_retry(attempt)

        status = self._status_code_of(last_error) if last_error else None
        raise LLMClientError(
            f"{self._describe(last_error) if last_error else 'OpenAI 调用失败'}"
            f"，已重试 {attempts} 次仍未成功",
            status_code=status,
            attempts=attempts,
        ) from last_error

    def generate(self, prompt: str, system: str = "") -> str:
        """单提示生成：组装 system/user 消息后走 ``chat``"""
        return self.chat(self._build_messages(prompt, system))

    def chat_stream(self, messages: List[Dict[str, str]],
                    callback: Optional[Callable[[str], None]] = None) -> str:
        """流式调用

        流式请求**不做重试**——避免重试导致已输出的内容重复。
        """
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
            )
            full_response = ""
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                # 部分厂商的首块 / 末块 content 为 None
                content = getattr(delta, "content", None)
                if not content:
                    continue
                full_response += content
                if callback:
                    callback(content)
            return full_response
        except Exception as e:
            logger.error(f"OpenAI 流式调用失败：{self._describe(e)}")
            raise LLMClientError(
                self._describe(e),
                status_code=self._status_code_of(e),
                attempts=1,
            ) from e


# ----------------------------------------------------------------------
# 工厂
# ----------------------------------------------------------------------
_llm_client: Optional[BaseLLMClient] = None


def _build_client(backend: str, **overrides) -> BaseLLMClient:
    """按后端类型构造客户端"""
    if backend == 'openai':
        return OpenAICompatibleClient(**overrides)
    if backend == 'ollama':
        return OllamaClient(**overrides)
    raise LLMConfigError(
        f"无效的 LLM_BACKEND：{backend!r}。"
        f"合法取值为 \"ollama\" 或 \"openai\"。"
    )


def get_llm_client(force_new: bool = False, **overrides) -> BaseLLMClient:
    """获取 LLM 客户端实例（默认单例）

    后端由 ``Config.LLM_BACKEND`` 决定，并在**调用时**读取（而非导入时），
    便于运行时切换与测试打桩。

    :param force_new: 为 True 时强制新建实例（不覆盖单例）
    :param overrides: 透传给具体客户端构造函数的参数
    :raises LLMConfigError: 配置非法或缺少 API Key
    """
    global _llm_client

    # 配置校验（LLM_BACKEND=ollama 时为空操作）
    Config.validate_llm()
    backend = (Config.LLM_BACKEND or '').strip().lower()

    if overrides:
        return _build_client(backend, **overrides)

    if not force_new and _llm_client is not None \
            and getattr(_llm_client, 'backend', None) == backend:
        return _llm_client

    client = _build_client(backend)
    if not force_new:
        _llm_client = client
    return client


def reset_llm_client():
    """重置全局客户端缓存（供测试使用）"""
    global _llm_client
    _llm_client = None


__all__ = [
    'BaseLLMClient',
    'OllamaClient',
    'OpenAICompatibleClient',
    'get_llm_client',
    'reset_llm_client',
    'RETRYABLE_STATUS_CODES',
]
