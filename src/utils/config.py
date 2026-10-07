"""配置管理"""
import os
from pathlib import Path
from typing import Optional

from .llm_errors import LLMConfigError

# 可选的 .env 支持（python-dotenv 已在 requirements 中，但不强制安装）
try:  # pragma: no cover - 环境相关
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - 未安装时不产生任何影响
    pass


def mask_secret(value: Optional[str]) -> str:
    """对密钥进行脱敏，用于日志与配置打印

    短于 8 个字符的密钥一律完全隐藏，避免因截断反而暴露内容。
    """
    if not value:
        return "<未设置>"
    if len(value) < 8:
        return "*" * len(value)
    return f"{value[:3]}...{value[-4:]}"


class Config:
    """应用配置"""

    # 支持的 LLM 后端
    SUPPORTED_LLM_BACKENDS = ('ollama', 'openai')

    # 项目根目录
    PROJECT_ROOT = Path(__file__).parent.parent.parent

    # 输出目录
    OUTPUT_DIR = PROJECT_ROOT / "output"
    OUTPUT_DIR.mkdir(exist_ok=True)

    # 模板目录
    TEMPLATE_DIR = PROJECT_ROOT / "templates"
    TEMPLATE_DIR.mkdir(exist_ok=True)

    # 日志目录
    LOG_DIR = PROJECT_ROOT / "logs"
    LOG_DIR.mkdir(exist_ok=True)

    # 日志配置
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = LOG_DIR / "customs_agent.log"

    # ------------------------------------------------------------------
    # LLM 后端选择
    # ------------------------------------------------------------------
    # "ollama"（默认，本地） 或 "openai"（任何兼容 OpenAI 接口的远程服务）
    LLM_BACKEND = os.getenv('LLM_BACKEND', 'ollama').strip().lower()

    # Ollama 配置（本地模式，保留原有行为）
    OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen3.5:27b')
    OLLAMA_TIMEOUT = int(os.getenv('OLLAMA_TIMEOUT', 120))

    # OpenAI 兼容服务配置（远程模式）
    # 适用于 OpenAI、DeepSeek、Moonshot 等
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o')
    OPENAI_TIMEOUT = int(os.getenv('OPENAI_TIMEOUT', 120))
    # 远程模式的降级模型，留空表示不降级
    OPENAI_FALLBACK_MODEL = os.getenv('OPENAI_FALLBACK_MODEL', '')

    # 通用重试配置
    LLM_MAX_RETRIES = int(os.getenv('LLM_MAX_RETRIES', 3))
    LLM_RETRY_BACKOFF = float(os.getenv('LLM_RETRY_BACKOFF', 1.0))

    # 数据配置
    DEFAULT_ENCODING = 'utf-8'
    DEFAULT_SHEET_NAME = 'Sheet1'
    MAX_ROWS_FOR_PREVIEW = 100

    # 模板配置
    SUPPORTED_FORMATS = ['csv', 'xlsx', 'xls']

    @classmethod
    def set_output_dir(cls, path: str):
        """设置输出目录"""
        cls.OUTPUT_DIR = Path(path)
        cls.OUTPUT_DIR.mkdir(exist_ok=True)

    @classmethod
    def set_ollama_model(cls, model: str):
        """设置 Ollama 模型"""
        cls.OLLAMA_MODEL = model

    @classmethod
    def set_llm_backend(cls, backend: str):
        """设置 LLM 后端（"ollama" 或 "openai"）"""
        cls.LLM_BACKEND = (backend or '').strip().lower()

    @classmethod
    def set_llm_model(cls, model: str):
        """设置当前后端的模型名称"""
        if cls.LLM_BACKEND == 'openai':
            cls.OPENAI_MODEL = model
        else:
            cls.OLLAMA_MODEL = model

    @classmethod
    def active_model(cls) -> str:
        """返回当前后端生效的模型名"""
        if cls.LLM_BACKEND == 'openai':
            return cls.OPENAI_MODEL
        return cls.OLLAMA_MODEL

    @classmethod
    def validate_llm(cls):
        """校验当前 LLM 配置，非法时抛出 :class:`LLMConfigError`

        仅在 ``LLM_BACKEND == "openai"`` 时进行校验；
        默认的 ``"ollama"`` 模式不做任何校验，以保证完全向后兼容。
        """
        backend = (cls.LLM_BACKEND or '').strip().lower()

        if backend not in cls.SUPPORTED_LLM_BACKENDS:
            supported = '" 或 "'.join(cls.SUPPORTED_LLM_BACKENDS)
            raise LLMConfigError(
                f"无效的 LLM_BACKEND：{cls.LLM_BACKEND!r}。合法取值为 \"{supported}\"。\n"
                f"示例：export LLM_BACKEND=openai"
            )

        if backend != 'openai':
            return

        problems = []
        if not cls.OPENAI_API_KEY or not cls.OPENAI_API_KEY.strip():
            problems.append(
                "  缺少 OPENAI_API_KEY。\n"
                "    请设置你的 API 密钥：\n"
                "      export OPENAI_API_KEY=sk-xxxxxxxx\n"
                "    （或在项目根目录创建 .env 文件，参考 .env.example）"
            )
        if not cls.OPENAI_BASE_URL or not cls.OPENAI_BASE_URL.strip():
            problems.append(
                "  OPENAI_BASE_URL 为空。请设置服务地址，例如：\n"
                "      export OPENAI_BASE_URL=https://api.openai.com/v1"
            )
        elif not cls.OPENAI_BASE_URL.strip().lower().startswith(('http://', 'https://')):
            problems.append(
                f"  OPENAI_BASE_URL 格式非法：{cls.OPENAI_BASE_URL!r}，必须以 http:// 或 https:// 开头。"
            )
        if not cls.OPENAI_MODEL or not cls.OPENAI_MODEL.strip():
            problems.append(
                "  OPENAI_MODEL 为空。请设置模型名，例如：\n"
                "      export OPENAI_MODEL=gpt-4o"
            )

        if problems:
            detail = "\n".join(problems)
            raise LLMConfigError(
                "LLM_BACKEND=openai 配置不完整，无法启动：\n"
                f"{detail}\n"
                "  提示：若想继续使用本地 Ollama，请执行 unset LLM_BACKEND 或设置 LLM_BACKEND=ollama。"
            )

    @classmethod
    def get_output_path(cls, filename: str) -> Path:
        """获取输出文件路径"""
        return cls.OUTPUT_DIR / filename

    @classmethod
    def print_config(cls):
        """打印当前配置（密钥自动脱敏）"""
        print("=" * 40)
        print("配置信息:")
        print(f"  项目根目录：{cls.PROJECT_ROOT}")
        print(f"  输出目录：{cls.OUTPUT_DIR}")
        print(f"  日志目录：{cls.LOG_DIR}")
        print(f"  LLM 后端：{cls.LLM_BACKEND}")
        if cls.LLM_BACKEND == 'openai':
            print(f"  OpenAI 地址：{cls.OPENAI_BASE_URL}")
            print(f"  OpenAI 模型：{cls.OPENAI_MODEL}")
            print(f"  OpenAI 密钥：{mask_secret(cls.OPENAI_API_KEY)}")
            print(f"  OpenAI 超时：{cls.OPENAI_TIMEOUT}s")
            if cls.OPENAI_FALLBACK_MODEL:
                print(f"  OpenAI 降级模型：{cls.OPENAI_FALLBACK_MODEL}")
        else:
            print(f"  Ollama 主机：{cls.OLLAMA_HOST}")
            print(f"  Ollama 模型：{cls.OLLAMA_MODEL}")
            print(f"  Ollama 超时：{cls.OLLAMA_TIMEOUT}s")
        print(f"  最大重试次数：{cls.LLM_MAX_RETRIES}")
        print(f"  日志级别：{cls.LOG_LEVEL}")
        print("=" * 40)
