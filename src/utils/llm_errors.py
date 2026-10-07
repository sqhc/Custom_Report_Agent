"""LLM 相关异常定义

本模块**不允许**导入任何项目内其它模块，以避免循环导入：
``src.utils.config``、``src.agent.llm_client`` 和 ``src.utils.llm_client``
都需要引用这些异常，因此它们必须保持零依赖。
"""
from typing import Optional


class LLMConfigError(ValueError):
    """LLM 配置缺失或非法（启动期错误，应直接终止并提示用户）"""


class LLMClientError(RuntimeError):
    """LLM 调用失败（运行期错误）

    :param message: 错误描述
    :param status_code: HTTP 状态码，未知时为 None
    :param attempts: 实际尝试次数
    """

    def __init__(self, message: str, status_code: Optional[int] = None, attempts: int = 0):
        super().__init__(message)
        self.status_code = status_code
        self.attempts = attempts


class LLMNotInstalledError(LLMConfigError):
    """缺少所需的第三方 SDK（例如 openai）"""
