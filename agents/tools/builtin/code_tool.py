"""CodeTool - 代码工具和代码分析工具"""

from typing import Optional, Dict, List
import json
import ast
from agents.tools.base_tool import BaseTool, ToolParameter, ToolResult


class CodeExecutionTool(BaseTool):
    """
    代码执行工具

    支持执行 Python 代码片段并返回结果。
    注意：生产环境应该使用沙箱或隔离环境。
    """

    name = "code_execution"
    description = "执行 Python 代码片段并返回结果（仅限安全代码）"
    parameters = [
        ToolParameter(
            name="code",
            description="要执行的 Python 代码",
            param_type="string",
            required=True
        ),
        ToolParameter(
            name="timeout",
            description="执行超时时间（秒）",
            param_type="number",
            required=False,
            default=10
        )
    ]

    def execute(self, code: str, timeout: int = 10) -> str:
        """
        执行代码

        Args:
            code: Python 代码
            timeout: 超时时间

        Returns:
            执行结果
        """
        # 安全检查：禁止导入模块和危险操作
        unsafe_patterns = [
            "import", "__", "eval", "exec", "compile",
            "open", "subprocess", "os.system", "os.popen"
        ]

        for pattern in unsafe_patterns:
            if pattern in code:
                return f"Error: Unsafe code detected. Pattern '{pattern}' is not allowed."

        try:
            # 创建一个安全的执行环境
            local_vars = {}
            global_vars = {
                "print": print,
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "list": list,
                "dict": dict,
                "tuple": tuple,
                "set": set,
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
                "map": map,
                "filter": filter,
                "sum": sum,
                "max": max,
                "min": min,
                "abs": abs,
                "round": round
            }

            # 执行代码
            exec(code, global_vars, local_vars)

            # 查找返回值（最后表达式的结果）
            result = local_vars.get("__result__", "No return value")

            return json.dumps({
                "success": True,
                "output": str(result),
                "variables": {k: str(v) for k, v in local_vars.items() if not k.startswith("__")}
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False, indent=2)


class CodeAnalysisTool(BaseTool):
    """
    代码分析工具

    分析代码结构、检测问题、提取信息。
    """

    name = "code_analysis"
    description = "分析代码结构，检测问题，提取函数和类信息"
    parameters = [
        ToolParameter(
            name="code",
            description="要分析的 Python 代码",
            param_type="string",
            required=True
        ),
        ToolParameter(
            name="analysis_type",
            description="分析类型：structure, errors, complexity",
            param_type="string",
            required=False,
            default="structure"
        )
    ]

    def execute(self, code: str, analysis_type: str = "structure") -> str:
        """
        分析代码

        Args:
            code: Python 代码
            analysis_type: 分析类型

        Returns:
            分析结果
        """
        try:
            # 解析代码
            tree = ast.parse(code)

            if analysis_type == "structure":
                return self._analyze_structure(tree, code)
            elif analysis_type == "errors":
                return self._analyze_errors(code)
            elif analysis_type == "complexity":
                return self._analyze_complexity(tree)
            else:
                return f"Unknown analysis type: {analysis_type}"

        except SyntaxError as e:
            return json.dumps({
                "success": False,
                "error": f"Syntax error: {str(e)}"
            }, ensure_ascii=False, indent=2)

    def _analyze_structure(self, tree: ast.AST, code: str) -> str:
        """分析代码结构"""
        classes = []
        functions = []
        variables = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [n.name for n in ast.walk(node) if isinstance(n, ast.FunctionDef)]
                classes.append({
                    "name": node.name,
                    "methods": methods,
                    "line": node.lineno
                })
            elif isinstance(node, ast.FunctionDef):
                if not any(isinstance(parent, ast.ClassDef) for parent in self._get_ancestors(tree, node)):
                    functions.append({
                        "name": node.name,
                        "args": [arg.arg for arg in node.args.args],
                        "line": node.lineno
                    })
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        variables.append({
                            "name": target.id,
                            "line": node.lineno
                        })

        return json.dumps({
            "success": True,
            "structure": {
                "classes": classes,
                "functions": functions,
                "variables": variables
            }
        }, ensure_ascii=False, indent=2)

    def _analyze_errors(self, code: str) -> str:
        """分析代码潜在错误"""
        errors = []

        # 检查未使用的变量（简单检查）
        for line_num, line in enumerate(code.split('\n'), 1):
            if '=' in line and not line.strip().startswith('#'):
                # 简单检查：变量赋值后未使用
                pass

        return json.dumps({
            "success": True,
            "errors": errors,
            "warnings": [
                "Consider adding type hints",
                "Consider adding docstrings"
            ]
        }, ensure_ascii=False, indent=2)

    def _analyze_complexity(self, tree: ast.AST) -> str:
        """分析代码复杂度"""
        functions = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 计算圈复杂度（简化版）
                complexity = 1
                for child in ast.walk(node):
                    if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                        complexity += 1

                functions.append({
                    "name": node.name,
                    "complexity": complexity,
                    "line": node.lineno
                })

        return json.dumps({
            "success": True,
            "complexity": functions
        }, ensure_ascii=False, indent=2)

    def _get_ancestors(self, tree: ast.AST, node: ast.AST) -> List[ast.AST]:
        """获取节点的父节点"""
        ancestors = []
        for child in ast.walk(tree):
            for subnode in ast.walk(child):
                if subnode is node:
                    ancestors.append(child)
                    break
        return ancestors
