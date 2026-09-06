"""MemoryTool - 记忆管理工具"""

from typing import Optional, Dict, List, Any
import json
import os
from dataclasses import dataclass, asdict
from agents.tools.base_tool import BaseTool, ToolParameter, ToolResult


@dataclass
class MemoryRecord:
    """记忆记录"""
    name: str
    description: str
    type: str  # "user", "feedback", "project", "reference"
    content: str
    created_at: str = ""
    updated_at: str = ""


class MemoryReadTool(BaseTool):
    """
    记忆读取工具

    读取记忆系统中的记录。
    """

    name = "memory_read"
    description = "读取记忆系统中的记录，支持按名称或类型过滤"
    parameters = [
        ToolParameter(
            name="name",
            description="记忆记录名称（可选，留空则读取所有）",
            param_type="string",
            required=False,
            default=""
        ),
        ToolParameter(
            name="type",
            description="记忆类型：user, feedback, project, reference",
            param_type="string",
            required=False,
            default=""
        )
    ]

    def execute(self, name: str = "", type: str = "") -> str:
        """
        读取记忆

        Args:
            name: 记忆名称
            type: 记忆类型

        Returns:
            记忆记录
        """
        try:
            # 读取 MEMORY.md 索引
            memory_records = self._read_memory_index()

            # 过滤记录
            filtered = memory_records
            if name:
                filtered = [r for r in filtered if name in r['name'] or name in r['description']]
            if type:
                filtered = [r for r in filtered if r['type'] == type]

            return json.dumps({
                "success": True,
                "count": len(filtered),
                "records": filtered
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False, indent=2)

    def _read_memory_index(self) -> List[Dict]:
        """读取记忆索引"""
        memory_path = "MEMORY.md"

        if not os.path.exists(memory_path):
            return []

        records = []
        with open(memory_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('- ['):
                    # 解析索引行：- [Title](file.md) — description
                    parts = line.split(' — ', 1)
                    title_part = parts[0][3:].strip()  # 去掉 "- ["
                    title = title_part.split(']')[0].strip('[')
                    file = title_part.split(']')[1].strip('(').strip(')')
                    description = parts[1] if len(parts) > 1 else ""

                    # 读取实际文件内容
                    content = self._read_memory_file(file)
                    if content:
                        records.append({
                            "name": title,
                            "description": description,
                            "type": content.get("type", "unknown"),
                            "content": content.get("content", ""),
                            "file": file
                        })

        return records

    def _read_memory_file(self, file_path: str) -> Dict:
        """读取记忆文件内容"""
        try:
            full_path = os.path.join("memory", file_path)
            if not os.path.exists(full_path):
                return {}

            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 解析 YAML frontmatter
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    metadata_part = parts[1]
                    body_part = parts[2]

                    metadata = {}
                    for line in metadata_part.split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            metadata[key.strip()] = value.strip()

                    return {
                        "metadata": metadata,
                        "content": body_part.strip()
                    }

            return {"content": content.strip()}

        except Exception:
            return {}


class MemoryWriteTool(BaseTool):
    """
    记忆写入工具

    写入新的记忆记录或更新现有记录。
    """

    name = "memory_write"
    description = "写入新的记忆记录或更新现有记录"
    parameters = [
        ToolParameter(
            name="name",
            description="记忆记录名称（简短的 slug 格式）",
            param_type="string",
            required=True
        ),
        ToolParameter(
            name="type",
            description="记忆类型：user, feedback, project, reference",
            param_type="string",
            required=True
        ),
        ToolParameter(
            name="description",
            description="记忆描述（一句话摘要）",
            param_type="string",
            required=True
        ),
        ToolParameter(
            name="content",
            description="记忆内容详情",
            param_type="string",
            required=True
        )
    ]

    def execute(
        self,
        name: str,
        type: str,
        description: str,
        content: str
    ) -> str:
        """
        写入记忆

        Args:
            name: 记忆名称
            type: 记忆类型
            description: 描述
            content: 内容

        Returns:
            操作结果
        """
        try:
            # 生成文件名
            file_name = f"{name}.md"
            file_path = os.path.join("memory", file_name)

            # 确保目录存在
            os.makedirs("memory", exist_ok=True)

            # 写入文件
            file_content = f"""---
name: {name}
description: {description}
metadata:
  type: {type}
---

{content}
"""

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(file_content)

            # 更新 MEMORY.md 索引
            self._update_memory_index(name, description, file_name)

            return json.dumps({
                "success": True,
                "message": f"Memory '{name}' written successfully",
                "file": file_path
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False, indent=2)

    def _update_memory_index(self, name: str, description: str, file_name: str):
        """更新记忆索引"""
        index_path = "MEMORY.md"

        # 读取现有索引
        existing_content = ""
        if os.path.exists(index_path):
            with open(index_path, 'r', encoding='utf-8') as f:
                existing_content = f.read().strip()

        # 检查是否已存在
        if file_name in existing_content:
            return  # 已存在，不更新

        # 追加新条目
        new_entry = f"- [{name}]({file_name}) — {description}"

        if existing_content:
            with open(index_path, 'a', encoding='utf-8') as f:
                f.write("\n" + new_entry)
        else:
            with open(index_path, 'w', encoding='utf-8') as f:
                f.write(new_entry)
