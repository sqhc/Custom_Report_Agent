"""SearchTool - 搜索工具"""

from typing import List, Dict, Any, Optional
import json

from agents.tools.base_tool import BaseTool, ToolParameter, ToolResult


class SearchTool(BaseTool):
    """
    搜索工具

    提供网络搜索能力，可以搜索互联网信息。
    """

    name = "search"
    description = "搜索互联网信息，返回搜索结果列表"
    parameters = [
        ToolParameter(
            name="query",
            description="搜索关键词",
            param_type="string",
            required=True
        ),
        ToolParameter(
            name="num_results",
            description="返回结果数量",
            param_type="number",
            required=False,
            default=5
        )
    ]

    def __init__(self, search_engine: Optional[Any] = None):
        """
        初始化搜索工具

        Args:
            search_engine: 搜索引擎实例（如 duckduckgo）
        """
        super().__init__()
        self.search_engine = search_engine

    def execute(self, query: str, num_results: int = 5) -> str:
        """
        执行搜索

        Args:
            query: 搜索关键词
            num_results: 返回结果数量

        Returns:
            搜索结果（JSON 格式）
        """
        if self.search_engine:
            try:
                results = self.search_engine.search(query, num_results=num_results)
                return json.dumps(results, ensure_ascii=False, indent=2)
            except Exception as e:
                return f"Search error: {str(e)}"
        else:
            # 模拟搜索结果（演示用）
            mock_results = [
                {
                    "title": f"搜索结果 1 - {query}",
                    "url": f"https://example.com/result/1",
                    "snippet": f"这是关于 {query} 的搜索结果摘要..."
                },
                {
                    "title": f"搜索结果 2 - {query}",
                    "url": f"https://example.com/result/2",
                    "snippet": f"更多有关 {query} 的信息..."
                }
            ][:num_results]
            return json.dumps(mock_results, ensure_ascii=False, indent=2)


class SearchSuggestionsTool(BaseTool):
    """
    搜索建议工具

    提供搜索建议和相关查询。
    """

    name = "search_suggestions"
    description = "获取搜索建议和相关查询"
    parameters = [
        ToolParameter(
            name="query",
            description="搜索关键词",
            param_type="string",
            required=True
        )
    ]

    def execute(self, query: str) -> str:
        """
        获取搜索建议

        Args:
            query: 搜索关键词

        Returns:
            搜索建议列表（JSON 格式）
        """
        suggestions = [
            f"{query} tutorial",
            f"{query} examples",
            f"best {query}",
            f"{query} vs alternatives",
            f"how to use {query}"
        ]
        return json.dumps(suggestions, ensure_ascii=False, indent=2)
