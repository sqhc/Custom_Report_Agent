"""BaseTool - 工具基类"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import inspect


@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    description: str
    param_type: str  # "string", "number", "boolean", "array", "object"
    required: bool = True
    default: Any = None


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseTool(ABC):
    """
    工具基类

    所有工具都应继承此基类，实现 execute 方法。
    提供工具元数据注册、参数验证等功能。
    """

    # 工具名称（可由类名自动生成）
    name: str = ""

    # 工具描述
    description: str = ""

    # 参数定义
    parameters: List[ToolParameter] = field(default_factory=list)

    # 是否启用
    enabled: bool = True

    def __init__(self, **kwargs):
        """初始化工具"""
        # 从类名生成工具名称
        if not self.name:
            self.name = self.__class__.__name__.replace("Tool", "")

        # 设置传入的参数
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """
        执行工具

        子类必须实现此方法

        Args:
            **kwargs: 工具参数

        Returns:
            执行结果

        Raises:
            Exception: 执行错误
        """
        pass

    def validate_params(self, **kwargs) -> List[str]:
        """
        验证参数

        Args:
            **kwargs: 工具参数

        Returns:
            错误信息列表，空列表表示验证通过
        """
        errors = []

        for param in self.parameters:
            if param.name not in kwargs:
                if param.required:
                    errors.append(f"Missing required parameter: {param.name}")
            else:
                value = kwargs[param.name]
                # 类型检查
                if param.param_type == "string" and not isinstance(value, str):
                    errors.append(f"Parameter {param.name} must be a string")
                elif param.param_type == "number" and not isinstance(value, (int, float)):
                    errors.append(f"Parameter {param.name} must be a number")
                elif param.param_type == "boolean" and not isinstance(value, bool):
                    errors.append(f"Parameter {param.name} must be a boolean")
                elif param.param_type == "array" and not isinstance(value, list):
                    errors.append(f"Parameter {param.name} must be an array")
                elif param.param_type == "object" and not isinstance(value, dict):
                    errors.append(f"Parameter {param.name} must be an object")

        return errors

    def run(self, **kwargs) -> ToolResult:
        """
        运行工具（包含验证和错误处理）

        Args:
            **kwargs: 工具参数

        Returns:
            ToolResult: 执行结果
        """
        if not self.enabled:
            return ToolResult(
                success=False,
                output=None,
                error=f"Tool '{self.name}' is disabled"
            )

        # 验证参数
        errors = self.validate_params(**kwargs)
        if errors:
            return ToolResult(
                success=False,
                output=None,
                error="; ".join(errors)
            )

        # 执行工具
        try:
            result = self.execute(**kwargs)
            return ToolResult(
                success=True,
                output=result
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e)
            )

    def get_schema(self) -> Dict[str, Any]:
        """
        获取工具 Schema（用于 LLM 提示）

        Returns:
            Dict: 工具 Schema
        """
        params = {}
        required = []

        for param in self.parameters:
            params[param.name] = {
                "type": param.param_type,
                "description": param.description
            }
            if param.required:
                required.append(param.name)

        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": params,
                "required": required
            }
        }

    def __call__(self, **kwargs) -> Any:
        """
        使工具实例可调用

        Args:
            **kwargs: 工具参数

        Returns:
            执行结果（直接返回 output，如果失败则抛出异常）
        """
        result = self.run(**kwargs)
        if not result.success:
            raise Exception(result.error)
        return result.output


def tool(
    name: Optional[str] = None,
    description: str = ""
):
    """
    工具装饰器

    用于快速创建工具函数

    Usage:
        @tool(name="search", description="搜索功能")
        def search(query: str):
            return f"Search results for {query}"
    """
    def decorator(func):
        # 生成工具名称
        tool_name = name or func.__name__

        # 解析函数签名获取参数
        sig = inspect.signature(func)
        parameters = []
        for param_name, param in sig.parameters.items():
            # 简单的类型映射
            param_type = "string"  # 默认
            if param.annotation == int:
                param_type = "number"
            elif param.annotation == float:
                param_type = "number"
            elif param.annotation == bool:
                param_type = "boolean"
            elif param.annotation == list:
                param_type = "array"
            elif param.annotation == dict:
                param_type = "object"

            parameters.append(ToolParameter(
                name=param_name,
                description=f"Parameter: {param_name}",
                param_type=param_type,
                required=param.default == inspect.Parameter.empty
            ))

        # 创建工具类
        class DecoratedTool(BaseTool):
            def __init__(self):
                super().__init__()
                self.name = tool_name
                self.description = description or func.__doc__ or ""
                self.parameters = parameters

            def execute(self, **kwargs):
                return func(**kwargs)

        return DecoratedTool()

    return decorator
