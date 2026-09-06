"""Agent Manager - 多智能体协作管理器"""

from typing import Optional, Dict, Any, List, Type
from dataclasses import dataclass, field
from enum import Enum
import uuid
import time

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from src.utils.logger import setup_logger
from .agent import Agent, AgentState
from .agent_runner import AgentRunner, ExecutionResult, ExecutionState

logger = setup_logger(__name__)
console = Console()


class CollaborationMode(Enum):
    """协作模式枚举"""
    SEQUENTIAL = "sequential"  # 顺序执行
    PARALLEL = "parallel"     # 并行执行
    MASTER_WORKER = "master_worker"  # 主从模式
    VOTING = "voting"         # 投票模式


@dataclass
class AgentConfig:
    """Agent 配置"""
    name: str
    description: str
    system_prompt: Optional[str] = None
    tools: Optional[List] = None
    max_iterations: int = 10
    verbose: bool = True


class AgentManager:
    """
    多智能体协作管理器

    支持创建、管理多个 Agent，协调它们之间的协作。
    """

    def __init__(self, name: str = "AgentManager"):
        """
        初始化 Agent 管理器

        Args:
            name: 管理器名称
        """
        self.name = name
        self.agents: Dict[str, Agent] = {}
        self.agent_configs: Dict[str, AgentConfig] = {}
        self.collaboration_history: List[Dict[str, Any]] = []

        logger.info(f"AgentManager '{self.name}' 初始化完成")

    def register_agent(
        self,
        agent: Agent,
        config: Optional[AgentConfig] = None
    ):
        """
        注册 Agent

        Args:
            agent: Agent 实例
            config: 可选的配置
        """
        agent_id = config.name if config else agent.name
        self.agents[agent_id] = agent
        if config:
            self.agent_configs[agent_id] = config

        logger.info(f"已注册 Agent: {agent_id}")

    def create_agent(
        self,
        config: AgentConfig,
        agent_class: Type[Agent] = Agent
    ) -> Agent:
        """
        根据配置创建 Agent

        Args:
            config: Agent 配置
            agent_class: Agent 类

        Returns:
            Agent: 新创建的 Agent
        """
        agent = agent_class(
            name=config.name,
            description=config.description,
            system_prompt=config.system_prompt,
            tools=config.tools,
            max_iterations=config.max_iterations,
            verbose=config.verbose
        )
        self.register_agent(agent, config)
        return agent

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """获取 Agent"""
        return self.agents.get(agent_id)

    def list_agents(self) -> List[str]:
        """列出所有注册的 Agent ID"""
        return list(self.agents.keys())

    def remove_agent(self, agent_id: str):
        """移除 Agent"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            if agent_id in self.agent_configs:
                del self.agent_configs[agent_id]
            logger.info(f"已移除 Agent: {agent_id}")

    def run_single(
        self,
        agent_id: str,
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """
        运行单个 Agent

        Args:
            agent_id: Agent ID
            task: 任务描述
            context: 额外的上下文信息

        Returns:
            ExecutionResult: 执行结果
        """
        agent = self.get_agent(agent_id)
        if not agent:
            return ExecutionResult(
                state=ExecutionState.FAILED,
                error=f"Agent '{agent_id}' 不存在"
            )

        runner = AgentRunner(agent)
        return runner.run_sync(task, context)

    def run_sequential(
        self,
        agent_ids: List[str],
        tasks: List[str],
        pass_context: bool = True
    ) -> List[ExecutionResult]:
        """
        顺序运行多个 Agent

        Args:
            agent_ids: Agent ID 列表
            tasks: 任务列表
            pass_context: 是否传递上下文

        Returns:
            List[ExecutionResult]: 执行结果列表
        """
        if len(agent_ids) != len(tasks):
            raise ValueError("Agent IDs 和 tasks 数量必须一致")

        results = []
        context = {}

        for agent_id, task in zip(agent_ids, tasks):
            agent = self.get_agent(agent_id)
            if not agent:
                results.append(ExecutionResult(
                    state=ExecutionState.FAILED,
                    error=f"Agent '{agent_id}' 不存在"
                ))
                continue

            runner = AgentRunner(agent)
            result = runner.run_sync(task, context if pass_context else None)
            results.append(result)

            # 更新上下文
            if pass_context and result.state == ExecutionState.COMPLETED:
                context[agent_id] = {
                    "output": result.output,
                    "execution_time": result.execution_time
                }

        self._record_collaboration("sequential", agent_ids, results)
        return results

    def run_parallel(
        self,
        agent_ids: List[str],
        tasks: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ExecutionResult]:
        """
        并行运行多个 Agent

        Args:
            agent_ids: Agent ID 列表
            tasks: 任务列表
            context: 额外的上下文信息

        Returns:
            List[ExecutionResult]: 执行结果列表
        """
        if len(agent_ids) != len(tasks):
            raise ValueError("Agent IDs 和 tasks 数量必须一致")

        runners = []
        for agent_id, task in zip(agent_ids, tasks):
            agent = self.get_agent(agent_id)
            if agent:
                runner = AgentRunner(agent)
                runner.run_async(task, context)
                runners.append(runner)

        # 等待所有执行完成
        results = []
        for runner in runners:
            result = runner.wait()
            results.append(result or ExecutionResult(
                state=ExecutionState.FAILED,
                error="执行超时"
            ))

        self._record_collaboration("parallel", agent_ids, results)
        return results

    def run_master_worker(
        self,
        master_id: str,
        worker_ids: List[str],
        master_task: str,
        worker_task_template: str
    ) -> Dict[str, Any]:
        """
        主从模式运行

        Args:
            master_id: Master Agent ID
            worker_ids: Worker Agent ID 列表
            master_task: Master 任务
            worker_task_template: Worker 任务模板（支持 {index} 占位符）

        Returns:
            Dict[str, Any]: 包含 master 和 workers 的结果
        """
        # 运行 Worker
        worker_tasks = [
            worker_task_template.format(index=i)
            for i in range(len(worker_ids))
        ]
        worker_results = self.run_parallel(worker_ids, worker_tasks)

        # 聚合 Worker 结果
        worker_outputs = []
        for idx, result in enumerate(worker_results):
            if result.state == ExecutionState.COMPLETED:
                worker_outputs.append({
                    "worker": worker_ids[idx],
                    "output": result.output
                })

        # Master 聚合结果
        context = {"worker_results": worker_outputs}
        master_result = self.run_single(master_id, master_task, context)

        result = {
            "master": master_result,
            "workers": worker_results,
            "worker_outputs": worker_outputs
        }

        self._record_collaboration("master_worker", [master_id] + worker_ids, [master_result])
        return result

    def run_voting(
        self,
        agent_ids: List[str],
        task: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        投票模式运行

        Args:
            agent_ids: Agent ID 列表
            task: 任务描述
            context: 额外的上下文信息

        Returns:
            Dict[str, Any]: 包含投票结果
        """
        # 并行运行所有 Agent
        tasks = [task] * len(agent_ids)
        results = self.run_parallel(agent_ids, tasks, context)

        # 统计投票结果
        votes: Dict[str, List[str]] = {}
        for idx, result in enumerate(results):
            if result.state == ExecutionState.COMPLETED and result.output:
                output = result.output.strip()
                if output not in votes:
                    votes[output] = []
                votes[output].append(agent_ids[idx])

        # 找出得票最多的
        winner = None
        max_votes = 0
        for output, voters in votes.items():
            if len(voters) > max_votes:
                max_votes = len(voters)
                winner = output

        result = {
            "task": task,
            "total_agents": len(agent_ids),
            "votes": votes,
            "winner": winner,
            "winning_votes": max_votes,
            "all_results": results
        }

        self._record_collaboration("voting", agent_ids, results)
        return result

    def _record_collaboration(
        self,
        mode: str,
        agent_ids: List[str],
        results: List[ExecutionResult]
    ):
        """记录协作历史"""
        record = {
            "id": str(uuid.uuid4()),
            "mode": mode,
            "agent_ids": agent_ids,
            "timestamp": time.time(),
            "results": [
                {
                    "state": r.state.value,
                    "output": r.output,
                    "error": r.error,
                    "execution_time": r.execution_time
                }
                for r in results
            ]
        }
        self.collaboration_history.append(record)

    def display_status(self):
        """显示当前状态"""
        tree = Tree(f"[bold]AgentManager: {self.name}[/bold]")

        # 注册状态
        registered_node = tree.add("[cyan]Registered Agents[/cyan]")
        for agent_id in self.list_agents():
            agent = self.agents[agent_id]
            status = agent.state.value
            registered_node.add(f"[green]{agent_id}[/green] - {status}")

        # 协作历史
        if self.collaboration_history:
            history_node = tree.add(f"[yellow]Collaboration History ({len(self.collaboration_history)} records)[/yellow]")
            for record in self.collaboration_history[-5:]:  # 显示最近 5 条
                history_node.add(f"{record['mode']}: {', '.join(record['agent_ids'])}")

        console.print(tree)

    def get_collaboration_history(
        self,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取协作历史"""
        if limit:
            return self.collaboration_history[-limit:]
        return self.collaboration_history.copy()

    def reset_all(self):
        """重置所有 Agent"""
        for agent in self.agents.values():
            agent.reset()
        logger.info("所有 Agent 已重置")
