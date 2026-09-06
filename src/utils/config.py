"""配置管理"""
import os
from pathlib import Path
from typing import Optional


class Config:
    """应用配置"""

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

    # Ollama 配置
    OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen3.5:27b')
    OLLAMA_TIMEOUT = int(os.getenv('OLLAMA_TIMEOUT', 120))

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
    def get_output_path(cls, filename: str) -> Path:
        """获取输出文件路径"""
        return cls.OUTPUT_DIR / filename

    @classmethod
    def print_config(cls):
        """打印当前配置"""
        print("=" * 40)
        print("配置信息:")
        print(f"  项目根目录：{cls.PROJECT_ROOT}")
        print(f"  输出目录：{cls.OUTPUT_DIR}")
        print(f"  日志目录：{cls.LOG_DIR}")
        print(f"  Ollama 主机：{cls.OLLAMA_HOST}")
        print(f"  Ollama 模型：{cls.OLLAMA_MODEL}")
        print(f"  Ollama 超时：{cls.OLLAMA_TIMEOUT}s")
        print(f"  日志级别：{cls.LOG_LEVEL}")
        print("=" * 40)
