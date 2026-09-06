"""TableExtractor - 报表提取与对比视图生成器

支持 PDF、Excel、Word、网页等多种报表格式的提取，并生成 HTML 对比视图。
"""

import os
import json
import html
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class TableColumn:
    """表列定义"""
    name: str
    index: int
    data_type: str = "text"


@dataclass
class TableRow:
    """表行数据"""
    original_values: Dict[str, str]
    extracted_values: Dict[str, str]
    match_status: Dict[str, str]  # "match", "partial", "mismatch", "missing"


@dataclass
class ExtractionResult:
    """提取结果"""
    source_file: str
    table_name: str
    columns: List[TableColumn]
    rows: List[TableRow]
    total_rows: int
    matched_rows: int
    accuracy: float
    extraction_time: str


class TableExtractor:
    """表格提取器"""

    def __init__(self):
        self.results: List[ExtractionResult] = []

    def extract_from_pdf(self, file_path: str, column_mapping: Dict[str, str]) -> ExtractionResult:
        """
        从 PDF 提取表格

        Args:
            file_path: PDF 文件路径
            column_mapping: 列映射 {列名：提取规则/位置}

        Returns:
            提取结果
        """
        # 这里需要集成 PDF 解析库，如 PyPDF2、pdfplumber 等
        # 当前实现为框架，实际使用时需要填充 PDF 解析逻辑
        return self._create_result(file_path, "PDF", column_mapping, [])

    def extract_from_excel(self, file_path: str, column_mapping: Dict[str, str], sheet_name: str = None) -> ExtractionResult:
        """
        从 Excel 提取表格

        Args:
            file_path: Excel 文件路径
            column_mapping: 列映射
            sheet_name: 工作表名称

        Returns:
            提取结果
        """
        import pandas as pd

        try:
            # sheet_name=None 返回 dict，需要处理
            if sheet_name is None:
                # 读取第一个工作表
                excel_file = pd.ExcelFile(file_path)
                sheet_name = excel_file.sheet_names[0] if excel_file.sheet_names else None
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            else:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            columns = [TableColumn(name=name, index=i) for i, name in enumerate(df.columns)]
            rows = []

            for _, row in df.iterrows():
                original = {col.name: str(row[col.name]) for col in columns}
                extracted = self._apply_mapping(original, column_mapping)
                match_status = self._compare_values(original, extracted)
                rows.append(TableRow(original, extracted, match_status))

            matched = sum(1 for r in rows if all(v == "match" for v in r.match_status.values()))
            result = ExtractionResult(
                source_file=file_path,
                table_name=os.path.basename(file_path),
                columns=columns,
                rows=rows,
                total_rows=len(rows),
                matched_rows=matched,
                accuracy=matched / len(rows) if rows else 0,
                extraction_time=datetime.now().isoformat()
            )
            self.results.append(result)
            return result

        except Exception as e:
            return self._create_error_result(file_path, str(e))

    def extract_from_word(self, file_path: str, column_mapping: Dict[str, str]) -> ExtractionResult:
        """
        从 Word 提取表格

        Args:
            file_path: Word 文件路径
            column_mapping: 列映射

        Returns:
            提取结果
        """
        # 需要集成 python-docx 库
        return self._create_result(file_path, "Word", column_mapping, [])

    def extract_from_web(self, url: str, column_mapping: Dict[str, str], css_selector: str = "table") -> ExtractionResult:
        """
        从网页提取表格

        Args:
            url: 网页 URL
            column_mapping: 列映射
            css_selector: 表格 CSS 选择器

        Returns:
            提取结果
        """
        try:
            import requests
            from bs4 import BeautifulSoup

            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            tables = soup.select(css_selector)

            if not tables:
                raise ValueError(f"No tables found with selector '{css_selector}'")

            table = tables[0]
            headers = [th.get_text(strip=True) for th in table.find_all('th')]
            if not headers:
                headers = [f"Column_{i}" for i in range(len(table.find_all('td')))]

            columns = [TableColumn(name=name, index=i) for i, name in enumerate(headers)]
            rows = []

            for tr in table.find_all('tr')[1:]:
                cells = tr.find_all('td')
                original = {col.name: cells[i].get_text(strip=True) if i < len(cells) else "" for col in columns}
                extracted = self._apply_mapping(original, column_mapping)
                match_status = self._compare_values(original, extracted)
                rows.append(TableRow(original, extracted, match_status))

            matched = sum(1 for r in rows if all(v == "match" for v in r.match_status.values()))
            result = ExtractionResult(
                source_file=url,
                table_name=os.path.basename(url),
                columns=columns,
                rows=rows,
                total_rows=len(rows),
                matched_rows=matched,
                accuracy=matched / len(rows) if rows else 0,
                extraction_time=datetime.now().isoformat()
            )
            self.results.append(result)
            return result

        except Exception as e:
            return self._create_error_result(url, str(e))

    def _apply_mapping(self, original: Dict[str, str], mapping: Dict[str, str]) -> Dict[str, str]:
        """应用列映射规则"""
        extracted = {}
        for col_name, rule in mapping.items():
            if col_name in original:
                value = original[col_name]
                # 这里可以根据 rule 进行各种转换
                extracted[col_name] = value
            else:
                extracted[col_name] = ""
        return extracted

    def _compare_values(self, original: Dict[str, str], extracted: Dict[str, str]) -> Dict[str, str]:
        """比较原始值和提取值"""
        status = {}
        for key in original.keys():
            orig = original.get(key, "").strip().lower()
            ext = extracted.get(key, "").strip().lower()

            if not orig and not ext:
                status[key] = "match"
            elif orig == ext:
                status[key] = "match"
            elif orig in ext or ext in orig:
                status[key] = "partial"
            else:
                status[key] = "mismatch"
        return status

    def _create_result(self, file_path: str, file_type: str, mapping: Dict[str, str], rows: List) -> ExtractionResult:
        """创建空结果"""
        return ExtractionResult(
            source_file=file_path,
            table_name=f"{file_type}_table",
            columns=[],
            rows=[],
            total_rows=0,
            matched_rows=0,
            accuracy=0,
            extraction_time=datetime.now().isoformat()
        )

    def _create_error_result(self, file_path: str, error: str) -> ExtractionResult:
        """创建错误结果"""
        return ExtractionResult(
            source_file=file_path,
            table_name="error",
            columns=[],
            rows=[TableRow(
                original_values={"error": error},
                extracted_values={},
                match_status={"error": "mismatch"}
            )],
            total_rows=0,
            matched_rows=0,
            accuracy=0,
            extraction_time=datetime.now().isoformat()
        )

    def generate_comparison_html(self, result: ExtractionResult, output_path: str, max_rows: int = 100) -> str:
        """
        生成 HTML 对比视图

        Args:
            result: 提取结果
            output_path: 输出文件路径
            max_rows: 最大显示行数

        Returns:
            HTML 文件路径
        """
        html_content = self._build_comparison_html(result, max_rows)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return output_path

    def _build_comparison_html(self, result: ExtractionResult, max_rows: int) -> str:
        """构建 HTML 对比视图"""
        columns = result.columns
        rows = result.rows[:max_rows]

        # 构建列头
        headers_html = ""
        for col in columns:
            headers_html += f'''
            <th class="header-left">{html.escape(col.name)}<br><small>(原始)</small></th>
            <th class="header-right">{html.escape(col.name)}<br><small>(提取)</small></th>
            '''

        # 构建数据行
        rows_html = ""
        for row in rows:
            row_class = "match" if all(v == "match" for v in row.match_status.values()) else "mismatch"
            cells_html = ""
            for col in columns:
                orig_val = html.escape(row.original_values.get(col.name, ""))
                ext_val = html.escape(row.extracted_values.get(col.name, ""))
                status = row.match_status.get(col.name, "unknown")

                orig_class = "match" if status == "match" else ("partial" if status == "partial" else "mismatch")
                ext_class = orig_class

                cells_html += f'''
                <td class="cell-left {orig_class}">{orig_val or '&nbsp;'}</td>
                <td class="cell-right {ext_class}">{ext_val or '&nbsp;'}</td>
                '''
            rows_html += f'<tr class="{row_class}">{cells_html}</tr>'

        # 统计信息
        match_rate = result.accuracy * 100
        stats_html = f'''
        <div class="stats">
            <div class="stat-item">
                <span class="stat-label">总行数</span>
                <span class="stat-value">{result.total_rows}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">匹配行数</span>
                <span class="stat-value match">{result.matched_rows}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">准确率</span>
                <span class="stat-value" style="color: {'#22c55e' if match_rate >= 90 else '#eab308' if match_rate >= 70 else '#ef4444'}">{match_rate:.1f}%</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">文件</span>
                <span class="stat-value">{html.escape(result.source_file)}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">提取时间</span>
                <span class="stat-value">{result.extraction_time}</span>
            </div>
        </div>
        '''

        html_template = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>表格提取对比视图 - {html.escape(result.table_name)}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }}
        .container {{
            max-width: 100%;
            margin: 0 auto;
            padding: 20px;
            overflow-x: auto;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
        }}
        .header h1 {{
            font-size: 24px;
            margin-bottom: 10px;
        }}
        .stats {{
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            margin-top: 15px;
        }}
        .stat-item {{
            background: rgba(255,255,255,0.2);
            padding: 10px 20px;
            border-radius: 6px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .stat-label {{
            font-size: 14px;
            opacity: 0.9;
        }}
        .stat-value {{
            font-size: 18px;
            font-weight: bold;
        }}
        .table-wrapper {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th {{
            background: #f8f9fa;
            padding: 12px 10px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #e9ecef;
            white-space: nowrap;
        }}
        th small {{
            font-size: 12px;
            color: #6c757d;
            font-weight: normal;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #e9ecef;
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .header-left {{
            background: #e3f2fd;
            border-right: 2px solid #2196f3;
        }}
        .header-right {{
            background: #f3e5f5;
        }}
        .cell-left {{
            background: #fafafa;
        }}
        .cell-right {{
            background: #ffffff;
        }}
        .match {{
            background: #d1e7dd !important;
        }}
        .partial {{
            background: #fff3cd !important;
        }}
        .mismatch {{
            background: #f8d7da !important;
        }}
        .row-number {{
            position: sticky;
            left: 0;
            background: #f8f9fa;
            padding: 10px 15px;
            font-weight: bold;
            color: #6c757d;
            border-right: 2px solid #dee2e6;
            text-align: center;
            min-width: 50px;
        }}
        .legend {{
            display: flex;
            gap: 20px;
            margin-bottom: 15px;
            padding: 10px;
            background: white;
            border-radius: 6px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .legend-color {{
            width: 20px;
            height: 20px;
            border-radius: 4px;
        }}
        .legend-color.match {{
            background: #d1e7dd;
        }}
        .legend-color.partial {{
            background: #fff3cd;
        }}
        .legend-color.mismatch {{
            background: #f8d7da;
        }}
        .toolbar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding: 10px;
            background: white;
            border-radius: 6px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .filter-btn {{
            background: #667eea;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }}
        .filter-btn:hover {{
            background: #5568d3;
        }}
        .filter-btn.secondary {{
            background: #6c757d;
        }}
        .filter-btn.secondary:hover {{
            background: #5a6268;
        }}
        @media print {{
            body {{
                background: white;
            }}
            .container {{
                padding: 0;
            }}
            .table-wrapper {{
                box-shadow: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 表格提取对比视图</h1>
            {stats_html}
        </div>

        <div class="legend">
            <div class="legend-item">
                <div class="legend-color match"></div>
                <span>完全匹配</span>
            </div>
            <div class="legend-item">
                <div class="legend-color partial"></div>
                <span>部分匹配</span>
            </div>
            <div class="legend-item">
                <div class="legend-color mismatch"></div>
                <span>不匹配/缺失</span>
            </div>
        </div>

        <div class="toolbar">
            <div>
                <button class="filter-btn" onclick="filterRows('all')">显示全部 ({len(rows)} 行)</button>
                <button class="filter-btn secondary" onclick="filterRows('mismatch')">仅显示异常</button>
            </div>
            <div>
                <button class="filter-btn" onclick="window.print()">🖨️ 打印</button>
            </div>
        </div>

        <div class="table-wrapper">
            <table>
                <thead>
                    <tr>
                        <th class="row-number">#</th>
                        {headers_html}
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        function filterRows(type) {{
            const rows = document.querySelectorAll('tbody tr');
            rows.forEach(row => {{
                if (type === 'all') {{
                    row.style.display = '';
                }} else if (type === 'mismatch') {{
                    row.style.display = row.classList.contains('mismatch') ? '' : 'none';
                }}
            }});
        }}
    </script>
</body>
</html>'''

        return html_template


def create_extraction_workflow(
    input_path: str,
    column_mapping: Dict[str, str],
    output_dir: str = "extraction_results",
    file_type: str = None
) -> Dict[str, Any]:
    """
    创建提取工作流

    Args:
        input_path: 输入文件路径或 URL
        column_mapping: 列映射配置
        output_dir: 输出目录
        file_type: 文件类型 (pdf, excel, word, web)

    Returns:
        提取结果和 HTML 路径
    """
    extractor = TableExtractor()

    # 自动检测文件类型
    if not file_type:
        if input_path.endswith('.pdf'):
            file_type = 'pdf'
        elif input_path.endswith(('.xls', '.xlsx')):
            file_type = 'excel'
        elif input_path.endswith(('.doc', '.docx')):
            file_type = 'word'
        elif input_path.startswith('http'):
            file_type = 'web'
        else:
            raise ValueError(f"Unsupported file type: {input_path}")

    # 执行提取
    if file_type == 'pdf':
        result = extractor.extract_from_pdf(input_path, column_mapping)
    elif file_type == 'excel':
        result = extractor.extract_from_excel(input_path, column_mapping)
    elif file_type == 'word':
        result = extractor.extract_from_word(input_path, column_mapping)
    elif file_type == 'web':
        result = extractor.extract_from_web(input_path, column_mapping)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

    # 生成 HTML 对比视图
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{os.path.basename(input_path)}_comparison.html")
    html_path = extractor.generate_comparison_html(result, output_file)

    return {
        "success": True,
        "result": asdict(result) if hasattr(result, '__dict__') else result,
        "html_path": html_path,
        "accuracy": result.accuracy,
        "total_rows": result.total_rows,
        "matched_rows": result.matched_rows
    }


if __name__ == "__main__":
    # 示例用法
    import tempfile
    import pandas as pd

    # 创建测试 Excel 文件
    test_data = {
        "姓名": ["张三", "李四", "王五"],
        "年龄": ["25", "30", "35"],
        "城市": ["北京", "上海", "广州"]
    }

    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
        test_file = f.name

    df = pd.DataFrame(test_data)
    df.to_excel(test_file, index=False)

    # 执行提取
    column_mapping = {
        "姓名": "姓名",
        "年龄": "年龄",
        "城市": "城市"
    }

    result = create_extraction_workflow(
        input_path=test_file,
        column_mapping=column_mapping,
        output_dir="output"
    )

    print(f"提取完成！")
    print(f"总行数：{result['total_rows']}")
    print(f"匹配行数：{result['matched_rows']}")
    print(f"准确率：{result['accuracy']:.2%}")
    print(f"HTML 对比视图：{result['html_path']}")

    # 清理测试文件
    os.remove(test_file)
