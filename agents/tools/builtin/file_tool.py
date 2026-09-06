"""FileTool - 文件读写工具"""

from typing import Optional, Dict, List
import json
import os
from agents.tools.base_tool import BaseTool, ToolParameter, ToolResult


class FileReadTool(BaseTool):
    """
    文件读取工具

    读取文件内容，支持按行读取和全文读取。
    """

    name = "file_read"
    description = "读取文件内容，支持全文读取和按行范围读取"
    parameters = [
        ToolParameter(
            name="path",
            description="文件路径",
            param_type="string",
            required=True
        ),
        ToolParameter(
            name="start_line",
            description="开始行号（从 1 开始）",
            param_type="number",
            required=False,
            default=1
        ),
        ToolParameter(
            name="end_line",
            description="结束行号（-1 表示读到最后）",
            param_type="number",
            required=False,
            default=-1
        ),
        ToolParameter(
            name="encoding",
            description="文件编码",
            param_type="string",
            required=False,
            default="utf-8"
        )
    ]

    def execute(
        self,
        path: str,
        start_line: int = 1,
        end_line: int = -1,
        encoding: str = "utf-8"
    ) -> str:
        """
        读取文件

        Args:
            path: 文件路径
            start_line: 开始行号
            end_line: 结束行号
            encoding: 文件编码

        Returns:
            文件内容
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(path):
                return f"Error: File not found: {path}"

            # 检查是否是文件
            if not os.path.isfile(path):
                return f"Error: Not a file: {path}"

            # 读取文件
            with open(path, 'r', encoding=encoding) as f:
                lines = f.readlines()

            # 计算实际行数
            total_lines = len(lines)

            # 调整行号（从 1 开始）
            start_idx = max(0, start_line - 1)
            end_idx = total_lines if end_line == -1 else min(end_line, total_lines)

            # 切片读取
            if start_idx >= total_lines:
                return f"Error: start_line ({start_line}) exceeds file lines ({total_lines})"

            selected_lines = lines[start_idx:end_idx]

            # 格式化输出（带行号）
            output_lines = []
            for i, line in enumerate(selected_lines, start=start_idx + 1):
                output_lines.append(f"{i:6d} | {line.rstrip()}")

            return "\n".join(output_lines)

        except UnicodeDecodeError as e:
            return f"Error: Encoding error. Try a different encoding. Details: {str(e)}"
        except Exception as e:
            return f"Error: {str(e)}"


class FileWriteTool(BaseTool):
    """
    文件写入工具

    写入文件内容，支持覆盖和追加模式。
    """

    name = "file_write"
    description = "写入文件内容，支持覆盖和追加模式"
    parameters = [
        ToolParameter(
            name="path",
            description="文件路径",
            param_type="string",
            required=True
        ),
        ToolParameter(
            name="content",
            description="要写入的内容",
            param_type="string",
            required=True
        ),
        ToolParameter(
            name="mode",
            description="写入模式：overwrite（覆盖）或 append（追加）",
            param_type="string",
            required=False,
            default="overwrite"
        ),
        ToolParameter(
            name="encoding",
            description="文件编码",
            param_type="string",
            required=False,
            default="utf-8"
        )
    ]

    def execute(
        self,
        path: str,
        content: str,
        mode: str = "overwrite",
        encoding: str = "utf-8"
    ) -> str:
        """
        写入文件

        Args:
            path: 文件路径
            content: 内容
            mode: 写入模式
            encoding: 文件编码

        Returns:
            操作结果
        """
        try:
            # 确定写入模式
            write_mode = 'a' if mode == 'append' else 'w'

            # 确保目录存在
            directory = os.path.dirname(path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)

            # 写入文件
            with open(path, write_mode, encoding=encoding) as f:
                f.write(content)

            return json.dumps({
                "success": True,
                "message": f"File written successfully",
                "path": path,
                "mode": mode,
                "bytes_written": len(content.encode(encoding))
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False, indent=2)


class FileListTool(BaseTool):
    """
    文件列表工具

    列出目录内容和搜索文件。
    """

    name = "file_list"
    description = "列出目录内容或搜索文件"
    parameters = [
        ToolParameter(
            name="path",
            description="目录路径",
            param_type="string",
            required=True
        ),
        ToolParameter(
            name="pattern",
            description="搜索模式（如 *.py）",
            param_type="string",
            required=False,
            default="*"
        ),
        ToolParameter(
            name="recursive",
            description="是否递归搜索子目录",
            param_type="boolean",
            required=False,
            default=False
        )
    ]

    def execute(
        self,
        path: str,
        pattern: str = "*",
        recursive: bool = False
    ) -> str:
        """
        列出文件

        Args:
            path: 目录路径
            pattern: 搜索模式
            recursive: 是否递归

        Returns:
            文件列表
        """
        try:
            import fnmatch

            if not os.path.exists(path):
                return f"Error: Path not found: {path}"

            if not os.path.isdir(path):
                return f"Error: Not a directory: {path}"

            files = []

            if recursive:
                for root, dirs, filenames in os.walk(path):
                    for filename in filenames:
                        if fnmatch.fnmatch(filename, pattern):
                            full_path = os.path.join(root, filename)
                            rel_path = os.path.relpath(full_path, path)
                            files.append(rel_path)
            else:
                for item in os.listdir(path):
                    if fnmatch.fnmatch(item, pattern):
                        full_path = os.path.join(path, item)
                        item_type = "dir" if os.path.isdir(full_path) else "file"
                        files.append(f"{item} [{item_type}]")

            return json.dumps({
                "success": True,
                "path": path,
                "pattern": pattern,
                "recursive": recursive,
                "count": len(files),
                "items": files
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False, indent=2)
