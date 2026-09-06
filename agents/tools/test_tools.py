"""测试内置工具"""

import sys
sys.path.insert(0, '/Users/shenqing/Desktop/custom_agent_project')

from agents.tools.tool_registry import ToolRegistry
from agents.tools.builtin.bash_tool import BashTool
from agents.tools.builtin.file_tool import FileReadTool, FileWriteTool
from agents.tools.builtin.memory_tool import MemoryReadTool, MemoryWriteTool
from agents.tools.builtin.web_tool import WebFetchTool, WebSearchTool


def test_bash_tool():
    """测试 Bash 工具"""
    print("\n=== 测试 Bash 工具 ===")
    tool = BashTool()

    # 测试执行命令
    result = tool.execute(command="echo 'Hello World'")
    print(f"命令执行结果：{result}")


def test_file_tools():
    """测试文件工具"""
    print("\n=== 测试文件工具 ===")

    # 测试读取文件
    read_tool = FileReadTool()
    result = read_tool.execute(path="/etc/hosts", start_line=1, end_line=5)
    print(f"文件读取结果：{result[:200]}...")

    # 测试写入文件
    write_tool = FileWriteTool()
    result = write_tool.execute(
        path="/tmp/test_file.txt",
        content="这是一条测试内容"
    )
    print(f"文件写入结果：{result}")


def test_memory_tools():
    """测试记忆工具"""
    print("\n=== 测试记忆工具 ===")

    # 测试写入记忆
    write_tool = MemoryWriteTool()
    result = write_tool.execute(
        name="test_memory",
        type="user",
        description="测试记忆记录",
        content="这是测试记忆的详细内容。"
    )
    print(f"记忆写入结果：{result}")

    # 测试读取记忆
    read_tool = MemoryReadTool()
    result = read_tool.execute()
    print(f"记忆读取结果：{result[:500]}...")


def test_web_tools():
    """测试网络工具"""
    print("\n=== 测试网络工具 ===")

    # 测试网页抓取
    fetch_tool = WebFetchTool()
    result = fetch_tool.execute(url="https://example.com", extract="text")
    print(f"网页抓取结果：{result}")

    # 测试网页搜索
    search_tool = WebSearchTool()
    result = search_tool.execute(query="Python programming", num_results=3)
    print(f"网页搜索结果：{result}")


def test_tool_registry():
    """测试工具注册表"""
    print("\n=== 测试工具注册表 ===")

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

    # 获取工具 Schema
    schemas = ToolRegistry.get_tool_schemas()
    print(f"工具 Schema 数量：{len(schemas)}")
    for schema in schemas[:3]:
        print(f"  - {schema['name']}: {schema['description'][:50]}...")


if __name__ == "__main__":
    test_bash_tool()
    test_file_tools()
    test_memory_tools()
    test_web_tools()
    test_tool_registry()
    print("\n=== 所有测试完成 ===")
