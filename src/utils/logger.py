"""日志模块"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
import os


def setup_logger(name: str = "customs_agent") -> logging.Logger:
    """
    设置日志记录器
    :param name: 日志名称
    :return: Logger 实例
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    # 清除旧的手柄
    logger.handlers.clear()

    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # 文件输出
    try:
        log_file = Path(__file__).parent.parent.parent / "logs" / "customs_agent.log"
        log_file.parent.mkdir(exist_ok=True)

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"无法创建日志文件：{e}")

    # 格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_handler.setFormatter(formatter)

    if logger.handlers:
        logger.handlers[0].setFormatter(formatter)

    logger.addHandler(console_handler)

    return logger


# 默认 logger 实例
logger = setup_logger()
