"""测试内置工具"""

import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from agents.tools.tool_registry import ToolRegistry
from agents.tools.builtin.bash_tool import BashTool
from agents.tools.builtin.file_tool import FileReadTool, FileWriteTool
from agents.tools.builtin.memory_tool import MemoryReadTool, MemoryWriteTool
from agents.tools.builtin.web_tool import WebFetchTool, WebSearchTool


@contextmanager
def _temp_cwd():
    """在临时目录中执行，避免向仓库根写入 MEMORY.md / memory/ 等副作用文件"""
    original = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            yield tmp
        finally:
            os.chdir(original)


def test_bash_tool():
    """测试 Bash 工具"""
    print("\n=== 测试 Bash 工具 ===")
    tool = BashTool()

    # 测试执行命令
    result = tool.execute(command="echo 'Hello World'")
    print(f"命令执行结果：{result}")
    assert "Hello World" in str(result), f"Bash 输出异常：{result}"


def test_file_tools():
    """测试文件工具"""
    print("\n=== 测试文件工具 ===")

    # 测试读取文件（用本文件自身，避免依赖 /etc/hosts 等系统路径）
    read_tool = FileReadTool()
    result = read_tool.execute(path=__file__, start_line=1, end_line=5)
    print(f"文件读取结果：{result[:200]}...")
    assert result, "文件读取返回空"

    # 测试写入文件：写入临时目录，不污染仓库
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "test_file.txt")
        write_tool = FileWriteTool()
        result = write_tool.execute(path=target, content="这是一条测试内容")
        print(f"文件写入结果：{result}")
        assert os.path.exists(target), "文件未写入"
        assert open(target, encoding="utf-8").read() == "这是一条测试内容"


def test_memory_tools():
    """测试记忆工具"""
    print("\n=== 测试记忆工具 ===")

    # 记忆工具使用相对路径，必须在临时目录中运行，
    # 否则会向仓库根写入 MEMORY.md 与 memory/
    with _temp_cwd():
        # 测试写入记忆
        write_tool = MemoryWriteTool()
        result = write_tool.execute(
            name="test_memory",
            type="user",
            description="测试记忆记录",
            content="这是测试记忆的详细内容。"
        )
        print(f"记忆写入结果：{result}")

        # 确认文件确实落在临时目录中
        assert Path("memory/test_memory.md").exists(), "记忆文件未创建"
        assert Path("MEMORY.md").exists(), "记忆索引未创建"

        # 测试读取记忆
        read_tool = MemoryReadTool()
        result = read_tool.execute()
        print(f"记忆读取结果：{result[:500]}...")
        assert "test_memory" in result, "读取结果未包含刚写入的记忆"


def test_web_tools():
    """测试网络工具

    网络不可用时不应让测试失败（CI / 离线环境常见），
    但需要确认工具返回了可解析的结果而非抛异常。
    """
    print("\n=== 测试网络工具 ===")

    # 测试网页抓取
    fetch_tool = WebFetchTool()
    result = fetch_tool.execute(url="https://example.com", extract="text")
    print(f"网页抓取结果：{str(result)[:200]}...")
    assert result is not None, "网页抓取返回 None"

    # 测试网页搜索
    search_tool = WebSearchTool()
    result = search_tool.execute(query="Python programming", num_results=3)
    print(f"网页搜索结果：{str(result)[:200]}...")
    assert result is not None, "网页搜索返回 None"


def test_tool_registry():
    """测试工具注册表"""
    print("\n=== 测试工具注册表 ===")

    # ToolRegistry 是全局单例：先清空，避免测试间相互污染
    ToolRegistry.clear()

    # 手动注册工具
    ToolRegistry.register(BashTool(), "bash")
    ToolRegistry.register(FileReadTool(), "file_read")
    ToolRegistry.register(FileWriteTool(), "file_write")
    ToolRegistry.register(MemoryReadTool(), "memory_read")
    ToolRegistry.register(MemoryWriteTool(), "memory_write")
    ToolRegistry.register(WebFetchTool(), "web_fetch")
    ToolRegistry.register(WebSearchTool(), "web_search")

    # 列出所有工具
    tools = ToolRegistry.list_tools()
    print(f"已注册工具：{tools}")
    assert len(tools) == 7, f"注册数量不符：{tools}"
    assert "bash" in tools and "memory_write" in tools

    # 获取工具 Schema
    schemas = ToolRegistry.get_tool_schemas()
    print(f"工具 Schema 数量：{len(schemas)}")
    assert len(schemas) == 7
    for schema in schemas[:3]:
        print(f"  - {schema['name']}: {schema['description'][:50]}...")

    # 查询与移除
    assert ToolRegistry.get("bash") is not None
    ToolRegistry.remove("bash")
    assert "bash" not in ToolRegistry.list_tools(), "移除后仍存在"


if __name__ == "__main__":
    test_bash_tool()
    test_file_tools()
    test_memory_tools()
    test_web_tools()
    test_tool_registry()
    print("\n=== 所有测试完成 ===")
