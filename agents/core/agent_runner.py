"""Agent Runner - 管理 Agent 执行生命周期"""

import time
import threading
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.utils.logger import setup_logger

logger = setup_logger(__name__)
console = Console()


class ExecutionState(Enum):
    """执行状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionResult:
    """执行结果"""
    state: ExecutionState
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    iterations: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentRunner:
    """
    Agent 执行器

    管理 Agent 的执行生命周期，支持异步执行、进度跟踪、超时控制等功能。
    """

    def __init__(
        self,
        agent,
        timeout: Optional[float] = None,
        enable_progress: bool = True
    ):
        """
        初始化 Agent Runner

        Args:
            agent: Agent 实例
            timeout: 执行超时时间（秒），None 表示无限制
            enable_progress: 是否显示进度
        """
        self.agent = agent
        self.timeout = timeout
        self.enable_progress = enable_progress
        self.result: Optional[ExecutionResult] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def run_sync(self, task: str, context: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        """
        同步运行 Agent

        Args:
            task: 任务描述
            context: 额外的上下文信息

        Returns:
            ExecutionResult: 执行结果
        """
        start_time = time.time()
        self._stop_event.clear()

        try:
            if self.enable_progress:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console
                ) as progress:
                    progress.add_task("Running agent...", total=None)
                    response = self.agent.run(task, context)
            else:
                response = self.agent.run(task, context)

            execution_time = time.time() - start_time

            self.result = ExecutionResult(
                state=ExecutionState.COMPLETED if response.success else ExecutionState.FAILED,
                output=response.answer or response.thought,
                error=response.error,
                execution_time=execution_time,
                iterations=self.agent.current_iteration,
                metadata={
                    "final_state": self.agent.state.value,
                    "message_count": len(self.agent.messages)
                }
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Agent 执行失败：{e}")
            self.result = ExecutionResult(
                state=ExecutionState.FAILED,
                error=str(e),
                execution_time=execution_time
            )

        return self.result

    def run_async(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        callback: Optional[Callable[[ExecutionResult], None]] = None
    ) -> 'AgentRunner':
        """
        异步运行 Agent

        Args:
            task: 任务描述
            context: 额外的上下文信息
            callback: 完成回调函数

        Returns:
            self: 支持链式调用
        """
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_thread,
            args=(task, context, callback)
        )
        self._thread.start()
        return self

    def _run_thread(
        self,
        task: str,
        context: Optional[Dict[str, Any]],
        callback: Optional[Callable[[ExecutionResult], None]]
    ):
        """运行线程"""
        try:
            result = self.run_sync(task, context)
            if callback:
                callback(result)
        except Exception as e:
            logger.error(f"异步执行失败：{e}")
            error_result = ExecutionResult(
                state=ExecutionState.FAILED,
                error=str(e)
            )
            if callback:
                callback(error_result)

    def wait(self, timeout: Optional[float] = None) -> Optional[ExecutionResult]:
        """
        等待异步执行完成

        Args:
            timeout: 等待超时时间

        Returns:
            ExecutionResult: 执行结果，如果超时返回 None
        """
        if self._thread:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                return None
        return self.result

    def stop(self):
        """停止执行"""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            logger.info("Agent 正在停止...")
        self.result = ExecutionResult(
            state=ExecutionState.CANCELLED,
            error="执行被取消"
        )

    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._thread is not None and self._thread.is_alive()

    def get_result(self) -> Optional[ExecutionResult]:
        """获取执行结果"""
        return self.result

    def run_with_timeout(
        self,
        task: str,
        timeout: float,
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """
        带超时控制的运行

        Args:
            task: 任务描述
            timeout: 超时时间（秒）
            context: 额外的上下文信息

        Returns:
            ExecutionResult: 执行结果
        """
        self.run_async(task, context)

        result = self.wait(timeout=timeout)
        if result is None:
            self.stop()
            return ExecutionResult(
                state=ExecutionState.FAILED,
                error=f"执行超时（{timeout}秒）"
            )
        return result


class BatchRunner:
    """
    批量执行器

    支持批量运行多个任务，提供进度跟踪和结果聚合。
    """

    def __init__(
        self,
        agent,
        max_concurrent: int = 1,
        timeout: Optional[float] = None
    ):
        """
        初始化批量执行器

        Args:
            agent: Agent 实例
            max_concurrent: 最大并发数
            timeout: 单个任务超时时间
        """
        self.agent = agent
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.results: List[ExecutionResult] = []
        self._lock = threading.Lock()

    def run_batch(
        self,
        tasks: List[Dict[str, Any]],
        show_progress: bool = True
    ) -> List[ExecutionResult]:
        """
        批量运行任务

        Args:
            tasks: 任务列表，每个任务包含 {"task": str, "context": Optional[Dict]}
            show_progress: 是否显示进度

        Returns:
            List[ExecutionResult]: 执行结果列表
        """
        self.results = []

        if show_progress:
            table = Table(title="Batch Execution")
            table.add_column("Task", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Time", style="yellow")
            console.print(table)

        for idx, task_data in enumerate(tasks):
            task = task_data.get("task", "")
            context = task_data.get("context")

            runner = AgentRunner(self.agent, timeout=self.timeout, enable_progress=False)
            result = runner.run_sync(task, context)

            with self._lock:
                self.results.append(result)

            if show_progress:
                status = "✓" if result.state == ExecutionState.COMPLETED else "✗"
                table = Table(show_header=False, box=None)
                table.add_row(
                    f"Task {idx + 1}: {task[:50]}...",
                    f"[bold {status}]",
                    f"{result.execution_time:.2f}s"
                )
                console.print(table)

            # 重置 Agent 状态
            self.agent.reset()

        return self.results

    def get_summary(self) -> Dict[str, Any]:
        """获取执行摘要"""
        if not self.results:
            return {"total": 0}

        completed = sum(1 for r in self.results if r.state == ExecutionState.COMPLETED)
        failed = sum(1 for r in self.results if r.state == ExecutionState.FAILED)
        total_time = sum(r.execution_time for r in self.results)

        return {
            "total": len(self.results),
            "completed": completed,
            "failed": failed,
            "total_time": total_time,
            "average_time": total_time / len(self.results) if self.results else 0
        }

    def export_results(self, filepath: str):
        """导出结果到文件"""
        data = []
        for idx, result in enumerate(self.results):
            data.append({
                "task_index": idx,
                "state": result.state.value,
                "output": result.output,
                "error": result.error,
                "execution_time": result.execution_time,
                "metadata": result.metadata
            })

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"结果已导出到：{filepath}")
