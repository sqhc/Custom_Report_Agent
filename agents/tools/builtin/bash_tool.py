"""BashTool - 命令行执行工具"""

import os
import subprocess
from typing import Any, Dict, List
from ..base_tool import BaseTool, ToolParameter, ToolResult


class BashTool(BaseTool):
    """
    执行 shell 命令

    在沙箱环境中执行 shell 命令，返回输出结果。
    """

    name = "bash"
    description = "在沙箱环境中执行 shell 命令"
    parameters = [
        ToolParameter(
            name="command",
            description="要执行的 shell 命令",
            param_type="string",
            required=True
        ),
        ToolParameter(
            name="timeout",
            description="命令执行超时时间（秒）",
            param_type="number",
            required=False,
            default=60
        ),
        ToolParameter(
            name="cwd",
            description="命令执行的工作目录",
            param_type="string",
            required=False,
            default="."
        )
    ]

    def execute(
        self,
        command: str,
        timeout: int = 60,
        cwd: str = "."
    ) -> Dict[str, Any]:
        """
        执行 shell 命令

        Args:
            command: 要执行的命令
            timeout: 超时时间（秒）
            cwd: 工作目录

        Returns:
            执行结果，包含 stdout、stderr 和 return_code
        """
        try:
            # 设置环境变量
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"

            # 执行命令
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )

            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
                "success": result.returncode == 0
            }

        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds",
                "return_code": -1,
                "success": False
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "success": False
            }

    def get_schema(self) -> Dict[str, Any]:
        """获取工具 Schema"""
        return super().get_schema()
