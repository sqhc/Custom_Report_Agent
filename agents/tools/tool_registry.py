"""ToolRegistry - 工具注册表"""

from typing import Dict, List, Optional, Type
import importlib
import inspect
import os
from .base_tool import BaseTool


class ToolRegistry:
    """
    工具注册表

    全局单例，用于注册、查找和管理工具。
    """

    _instance: Optional['ToolRegistry'] = None
    _tools: Dict[str, BaseTool] = {}
    _tool_classes: Dict[str, Type[BaseTool]] = {}

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def auto_discover(cls, package_name: str = "agents.tools.builtin"):
        """
        自动发现和注册工具

        Args:
            package_name: 工具包路径
        """
        try:
            package = importlib.import_module(package_name)
            package_path = package.__path__[0]

            for filename in os.listdir(package_path):
                if filename.endswith(".py") and not filename.startswith("_"):
                    module_name = filename[:-3]
                    module = importlib.import_module(f"{package_name}.{module_name}")

                    # 查找模块中的工具类
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, BaseTool) and obj != BaseTool:
                            cls.register_class(obj)
                            print(f"Auto-registered tool: {obj.name}")

        except Exception as e:
            print(f"Auto-discover error: {e}")

    @classmethod
    def register(
        cls,
        tool: BaseTool,
        name: Optional[str] = None
    ):
        """
        注册工具实例

        Args:
            tool: 工具实例
            name: 工具名称（默认使用工具自带的名称）
        """
        tool_name = name or tool.name
        cls._tools[tool_name] = tool

    @classmethod
    def register_class(
        cls,
        tool_class: Type[BaseTool],
        name: Optional[str] = None
    ):
        """
        注册工具类（延迟实例化）

        Args:
            tool_class: 工具类
            name: 工具名称
        """
        tool_name = name or tool_class.__name__
        cls._tool_classes[tool_name] = tool_class

    @classmethod
    def get(cls, name: str) -> Optional[BaseTool]:
        """
        获取工具

        Args:
            name: 工具名称

        Returns:
            工具实例，如果不存在则返回 None
        """
        # 先查找已注册的实例
        if name in cls._tools:
            return cls._tools[name]

        # 尝试从类实例化
        if name in cls._tool_classes:
            tool = cls._tool_classes[name]()
            cls._tools[name] = tool
            return tool

        return None

    @classmethod
    def list_tools(cls) -> List[str]:
        """
        列出所有已注册的工具名称

        Returns:
            工具名称列表
        """
        return list(cls._tools.keys()) + list(cls._tool_classes.keys())

    @classmethod
    def get_all(cls) -> Dict[str, BaseTool]:
        """
        获取所有工具（实例化所有注册的类）

        Returns:
            工具名称到实例的映射
        """
        all_tools = cls._tools.copy()

        for name, tool_class in cls._tool_classes.items():
            if name not in all_tools:
                all_tools[name] = tool_class()

        return all_tools

    @classmethod
    def remove(cls, name: str):
        """
        移除工具

        Args:
            name: 工具名称
        """
        if name in cls._tools:
            del cls._tools[name]
        if name in cls._tool_classes:
            del cls._tool_classes[name]

    @classmethod
    def clear(cls):
        """清除所有注册的工具"""
        cls._tools.clear()
        cls._tool_classes.clear()

    @classmethod
    def get_tool_schemas(cls) -> List[Dict]:
        """
        获取所有工具的 Schema

        Returns:
            工具 Schema 列表
        """
        all_tools = cls.get_all()
        return [tool.get_schema() for tool in all_tools.values()]
