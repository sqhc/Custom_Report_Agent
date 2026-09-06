"""Agent 类 - 封装 LLM 客户端用于结构化任务委托"""

import json
import time
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from src.utils.logger import setup_logger
from src.utils.llm_client import LLMClient, get_llm_client

logger = setup_logger(__name__)
console = Console()


class AgentState(Enum):
    """Agent 状态枚举"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    THINKING = "thinking"
    ACTING = "acting"


@dataclass
class AgentMessage:
    """Agent 消息"""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    timestamp: float = field(default_factory=time.time)
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[str] = None


@dataclass
class AgentResponse:
    """Agent 响应"""
    thought: str  # 思考过程
    action: Optional[str] = None  # 执行的动作
    action_input: Optional[Dict[str, Any]] = None  # 动作参数
    answer: Optional[str] = None  # 最终答案
    success: bool = True
    error: Optional[str] = None


class Agent:
    """
    智能 Agent 类

    封装 LLM 客户端，提供结构化的任务委托和工具调用能力。
    支持思考 - 行动 - 观察的循环模式。
    """

    def __init__(
        self,
        name: str = "Agent",
        description: str = "一个通用的智能助手",
        system_prompt: Optional[str] = None,
        tools: Optional[List] = None,
        llm_client: Optional[LLMClient] = None,
        max_iterations: int = 10,
        verbose: bool = True
    ):
        self.name = name
        self.description = description
        self.tools = tools or []
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.state = AgentState.IDLE
        self.messages: List[AgentMessage] = []
        self.current_iteration = 0

        # 初始化 LLM 客户端
        self.llm_client = llm_client or get_llm_client()

        # 构建系统提示词
        self.system_prompt = self._build_system_prompt(system_prompt)

        logger.info(f"Agent '{self.name}' 初始化完成，可用工具：{[t.__name__ for t in self.tools]}")

    def _build_system_prompt(self, custom_prompt: Optional[str]) -> str:
        """构建系统提示词"""
        base_prompt = """你是一个智能助手，能够通过思考和行动来解决复杂的任务。

你的工作流程：
1. 思考 (Thought): 分析当前情况，决定下一步行动
2. 行动 (Action): 执行适当的动作或调用工具
3. 观察 (Observation): 获取行动结果
4. 重复直到得出最终答案 (Final Answer)

请严格按照以下 JSON 格式响应：
{
    "thought": "你的思考过程",
    "action": "工具名称（如果有）",
    "action_input": {"参数": "值"},
    "answer": "最终答案（如果任务完成）"
}

可用工具："""

        if self.tools:
            tool_descriptions = self._format_tools_description()
            base_prompt += "\n\n" + tool_descriptions

        if custom_prompt:
            base_prompt = f"{custom_prompt}\n\n{base_prompt}"

        return base_prompt

    def _format_tools_description(self) -> str:
        """格式化工具描述"""
        descriptions = []
        for tool in self.tools:
            desc = f"- {tool.__name__}: {getattr(tool, 'description', 'No description')}"
            if hasattr(tool, 'input_schema'):
                desc += f"\n  输入：{tool.input_schema}"
            descriptions.append(desc)
        return "\n".join(descriptions)

    def add_message(self, message: AgentMessage):
        """添加消息到对话历史"""
        self.messages.append(message)
        if self.verbose:
            self._display_message(message)

    def _display_message(self, message: AgentMessage):
        """显示消息"""
        if message.role == "user":
            console.print(Panel(message.content, title="User", border_style="blue"))
        elif message.role == "assistant":
            console.print(Panel(message.content, title="Assistant", border_style="green"))
        elif message.role == "tool":
            style = "yellow" if message.tool_output else "cyan"
            console.print(Panel(message.content, title=f"Tool: {message.tool_name}", border_style=style))

    def run(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        运行 Agent 执行任务

        Args:
            task: 任务描述
            context: 额外的上下文信息

        Returns:
            AgentResponse: 包含思考、行动和结果的响应
        """
        self.state = AgentState.RUNNING
        self.current_iteration = 0

        # 添加用户任务消息
        user_message = AgentMessage(role="user", content=task)
        self.add_message(user_message)

        console.print(Panel(f"任务：{task}", title=self.name, border_style="magenta"))

        try:
            while self.current_iteration < self.max_iterations:
                self.current_iteration += 1
                self.state = AgentState.THINKING

                # 构建对话历史
                prompt = self._build_prompt()

                # 调用 LLM
                response_text = self.llm_client.call_with_retry(
                    prompt=prompt,
                    system=self.system_prompt,
                    require_json=True
                )

                if not response_text:
                    raise Exception("LLM 调用失败，所有重试均失败")

                # 解析响应
                response_data = self.llm_client._extract_json(response_text)
                if not response_data:
                    raise Exception(f"无法解析 LLM 响应：{response_text}")

                # 创建响应对象
                response = AgentResponse(
                    thought=response_data.get("thought", ""),
                    action=response_data.get("action"),
                    action_input=response_data.get("action_input"),
                    answer=response_data.get("answer"),
                    success=True
                )

                # 添加助手消息
                assistant_message = AgentMessage(
                    role="assistant",
                    content=json.dumps(response_data, ensure_ascii=False, indent=2)
                )
                self.add_message(assistant_message)

                # 检查是否完成任务
                if response.answer:
                    self.state = AgentState.COMPLETED
                    console.print(Panel(response.answer, title="Final Answer", border_style="green"))
                    return response

                # 执行工具调用
                if response.action and self.tools:
                    self.state = AgentState.ACTING
                    result = self._execute_tool(response.action, response.action_input)

                    # 添加工具结果消息
                    tool_message = AgentMessage(
                        role="tool",
                        content=str(result),
                        tool_name=response.action,
                        tool_output=str(result)
                    )
                    self.add_message(tool_message)

            # 达到最大迭代次数
            self.state = AgentState.FAILED
            return AgentResponse(
                thought="达到最大迭代次数",
                success=False,
                error="达到最大迭代次数限制"
            )

        except Exception as e:
            self.state = AgentState.FAILED
            logger.error(f"Agent 执行失败：{e}")
            return AgentResponse(
                thought="执行过程中出错",
                success=False,
                error=str(e)
            )
        finally:
            self.current_iteration = 0

    def _build_prompt(self) -> str:
        """构建 prompt"""
        parts = []

        # 添加对话历史
        for msg in self.messages:
            if msg.role == "user":
                parts.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                parts.append(f"Assistant: {msg.content}")
            elif msg.role == "tool":
                parts.append(f"Observation: {msg.content}")

        return "\n\n".join(parts)

    def _execute_tool(self, tool_name: str, input_data: Dict[str, Any]) -> Any:
        """执行工具"""
        for tool in self.tools:
            if tool.__name__ == tool_name:
                try:
                    result = tool(**input_data)
                    logger.info(f"工具 '{tool_name}' 执行成功")
                    return result
                except Exception as e:
                    logger.error(f"工具 '{tool_name}' 执行失败：{e}")
                    return f"Error: {str(e)}"

        logger.warning(f"未找到工具：{tool_name}")
        return f"Error: Tool '{tool_name}' not found"

    def reset(self):
        """重置 Agent 状态"""
        self.state = AgentState.IDLE
        self.messages = []
        self.current_iteration = 0
        logger.info(f"Agent '{self.name}' 已重置")

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """获取对话历史"""
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp
            }
            for msg in self.messages
        ]
