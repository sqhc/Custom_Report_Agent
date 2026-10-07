"""AI 推理引擎

本模块通过 :class:`~src.agent.llm_client.BaseLLMClient` 访问大模型，
后端由环境变量 ``LLM_BACKEND`` 决定（``ollama`` 本地 / ``openai`` 远程兼容接口）。

对外接口（类名、方法签名、返回值）与改造前保持一致，
现有调用方无需任何改动。
"""
import json
from typing import Optional, Dict, Any, Callable, List

from ..utils.config import Config
from ..utils.logger import setup_logger
from .llm_client import BaseLLMClient, get_llm_client
from .prompts import Prompts

logger = setup_logger(__name__)


class AIReasoner:
    """AI 推理引擎"""

    def __init__(self, model: str = None, host: str = None,
                 client: BaseLLMClient = None):
        """
        初始化 AI 推理引擎

        :param model: 模型名称（不传则使用当前后端配置的模型）
        :param host: Ollama 服务器地址（仅本地模式生效）
        :param client: 可选的客户端实例，用于依赖注入/测试
        """
        if client is not None:
            self.client = client
        else:
            # 仅传递当前后端认识的参数
            overrides = {}
            if model:
                overrides['model'] = model
            if host and (Config.LLM_BACKEND or '').strip().lower() == 'ollama':
                overrides['host'] = host

            self.client = get_llm_client(**overrides)

        # 保留公开属性，兼容既有调用方
        self.model = self.client.model
        self.host = getattr(self.client, 'host', None)

        logger.info(
            f"AI Reasoner 初始化完成：后端={self.client.backend}, 模型={self.model}"
        )

    def is_available(self) -> bool:
        """检查 AI 是否可用（非阻塞，不发起网络探活）"""
        return self.client is not None and self.client.is_available()

    def chat(self, prompt: str, system_prompt: str = "你是一位专业的 AI 助手") -> Optional[str]:
        """
        发送聊天请求
        :param prompt: 用户提示
        :param system_prompt: 系统提示
        :return: AI 回复，失败返回 None
        """
        if not self.is_available():
            logger.error("AI 不可用")
            return None

        try:
            return self.client.chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ])
        except Exception as e:
            logger.error(f"AI 聊天失败：{e}")
            return None

    def chat_with_callback(self, prompt: str, callback: Callable[[str], None] = None) -> Optional[str]:
        """
        流式聊天请求
        :param prompt: 用户提示
        :param callback: 流式回调函数
        :return: AI 回复，失败返回 None
        """
        if not self.is_available():
            logger.error("AI 不可用")
            return None

        try:
            return self.client.chat_stream(
                [{"role": "user", "content": prompt}],
                callback=callback
            )
        except Exception as e:
            logger.error(f"AI 流式聊天失败：{e}")
            return None

    def analyze_data(self, data_preview: str, columns: List[str]) -> Dict[str, Any]:
        """
        分析数据
        :param data_preview: 数据预览文本
        :param columns: 列名列表
        :return: 分析结果
        """
        prompt = Prompts.ANALYZE_DATA.format(
            data_preview=data_preview,
            columns=columns
        )

        response = self.chat(prompt, system_prompt="你是一位海关报关数据分析专家")

        if response:
            return self._parse_json_response(response, {"analysis": "分析失败", "details": response})
        return {"analysis": "分析失败", "details": response}

    def _parse_json_response(self, response: str, default: Dict[str, Any]) -> Dict[str, Any]:
        """解析 LLM 响应中的 JSON"""
        try:
            # 去除 markdown 代码块标记
            text = response.strip()
            if text.startswith("```json"):
                text = text[7:].strip()
            elif text.startswith("```"):
                text = text[3:].strip()
            if text.endswith("```"):
                text = text[:-3].strip()

            # 尝试直接解析
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试提取 JSON 对象
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                try:
                    return json.loads(response[json_start:json_end])
                except json.JSONDecodeError:
                    pass
            logger.warning("无法解析 JSON 响应")
            return default

    def get_fix_suggestion(self, validation_report: Dict[str, Any]) -> str:
        """
        获取数据修正建议
        :param validation_report: 验证报告
        :return: 修正建议
        """
        prompt = Prompts.FIX_SUGGESTION.format(
            validation_report=json.dumps(validation_report, indent=2, ensure_ascii=False)
        )

        return self.chat(prompt, system_prompt="你是一位海关报关数据修正专家")

    def select_template(self, data_type: str, product_count: int,
                       exporter: str, importer: str) -> Dict[str, Any]:
        """
        智能选择模板类型
        :param data_type: 数据类型
        :param product_count: 产品数量
        :param exporter: 出口商
        :param importer: 进口商
        :return: 模板选择建议
        """
        prompt = Prompts.SELECT_TEMPLATE.format(
            data_type=data_type,
            product_count=product_count,
            exporter=exporter,
            importer=importer
        )

        response = self.chat(prompt, system_prompt="你是一位报关单据选择专家")

        if response:
            return {
                "recommendation": response,
                "confidence": "high"  # 简化版本
            }

        return {
            "recommendation": "推荐使用报关单",
            "confidence": "medium"
        }

    def handle_anomaly(self, anomaly_description: str, related_data: Dict[str, Any]) -> str:
        """
        处理异常
        :param anomaly_description: 异常描述
        :param related_data: 相关数据
        :return: 处理建议
        """
        prompt = Prompts.HANDLE_ANOMALY.format(
            anomaly_description=anomaly_description,
            related_data=json.dumps(related_data, indent=2, ensure_ascii=False)
        )

        return self.chat(prompt, system_prompt="你是一位报关异常处理专家")

    def extract_customs_info(self, raw_table_text: str) -> Dict[str, Any]:
        """
        从海关报表中提取报关信息
        :param raw_table_text: 原始表格文本内容
        :return: 提取的报关信息 JSON
        """
        prompt = Prompts.CUSTOMS_EXTRACTION.format(
            raw_table_text=raw_table_text
        )

        response = self.chat(
            prompt,
            system_prompt=Prompts.CUSTOMS_EXPERT_SYSTEM
        )

        return self._parse_json_response(
            response or "",
            {"error": "提取失败", "raw_response": response}
        )


# 别名：部分文档与调用方使用 Reasoner 这一名称
Reasoner = AIReasoner

__all__ = ['AIReasoner', 'Reasoner']
