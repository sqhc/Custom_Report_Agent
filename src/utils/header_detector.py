"""智能表头检测 - 使用大模型识别表头和数据行"""
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import pandas as pd

from .llm_client import LLMClient, get_llm_client, HeaderDetectionResult
from .logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class ColumnInfo:
    """列信息"""
    original_name: str  # 原始列名
    detected_field: str  # 检测到的字段名
    confidence: float  # 置信度
    row_index: int  # 表头所在行


class HeaderDetector:
    """智能表头检测器"""

    # 海关数据标准字段
    STANDARD_FIELDS = [
        'exporter',           # 出口商
        'importer',           # 进口商
        'hs_code',            # HS 编码
        'product_name',       # 商品名称
        'quantity',           # 数量
        'unit',               # 单位
        'unit_price',         # 单价
        'total_value',        # 总价值
        'weight',             # 重量
        'origin',             # 原产地
        'destination',        # 目的地
        'port_of_loading',    # 装货港
        'port_of_discharge',  # 卸货港
        'declaration_date',   # 申报日期
        'invoice_number',     # 发票号
        'contract_number',    # 合同号
        'trade_mode',         # 贸易方式
        'transport_mode',     # 运输方式
        'currency',           # 币种
        'package_type',       # 包装类型
        'marks',              # 唛头
    ]

    # 表头检测提示词
    HEADER_DETECTION_PROMPT = """你是一位海关报关数据专家。请分析以下表格数据的前几行，识别表头位置和数据起始行，并建立列名到标准字段的映射。

表格预览（前{row_count}行，{col_count}列）：
{table_preview}

标准字段列表：
{fields}

请分析：
1. 哪一行是表头行（包含列名）
2. 数据从哪一行开始
3. 每个列对应的标准字段是什么

请严格以以下 JSON 格式返回，不要包含任何其他文字：
{{
    "header_row": 0,                    // 表头所在行号（从 0 开始）
    "data_start_row": 1,                // 数据开始行号（从 0 开始）
    "column_mapping": {{
        "列名 1": "exporter",           // 原始列名 -> 标准字段
        "列名 2": "product_name"
    }},
    "confidence": 0.95,                 // 整体置信度（0-1）
    "reasoning": "分析说明"             // 判断依据
}}

注意：
- 表头通常包含关键词如"名称"、"数量"、"单价"等
- 数据行通常包含数字或具体的公司名、产品名等
- 如果某列无法匹配标准字段，可以使用自定义字段名"""

    SYSTEM_PROMPT = """你是一位专业的海关数据分析师，能够准确识别各类海关报表的表头和数据行。"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or get_llm_client()

    def detect(
        self,
        data: List[List[Any]],
        max_preview_rows: int = 20
    ) -> Optional[HeaderDetectionResult]:
        """
        检测表头位置并返回列映射

        Args:
            data: 原始数据行
            max_preview_rows: 最多分析的行数

        Returns:
            检测结果，失败返回 None
        """
        if not data:
            logger.error("数据为空")
            return None

        # 限制预览行数
        preview_data = data[:min(max_preview_rows, len(data))]
        row_count = len(preview_data)
        col_count = len(preview_data[0]) if preview_data else 0

        # 生成表格预览文本
        table_preview = self._format_table_preview(preview_data)

        # 准备提示词
        fields_str = '\n'.join(f"- {f}" for f in self.STANDARD_FIELDS)
        prompt = self.HEADER_DETECTION_PROMPT.format(
            row_count=row_count,
            col_count=col_count,
            table_preview=table_preview,
            fields=fields_str
        )

        logger.info(f"开始检测表头，分析{row_count}行{col_count}列数据")
        logger.debug(f"表格预览:\n{table_preview}")

        # 调用 LLM
        response = self.llm_client.call_with_retry(
            prompt=prompt,
            system=self.SYSTEM_PROMPT,
            require_json=True
        )

        if not response:
            logger.error("LLM 调用失败，无法检测表头")
            return None

        # 解析响应
        result_dict = self._parse_response(response)
        if not result_dict:
            logger.error("LLM 返回无法解析")
            return None

        # 转换为数据类
        return HeaderDetectionResult(
            header_row=result_dict.get('header_row', 0),
            data_start_row=result_dict.get('data_start_row', 1),
            column_mapping=result_dict.get('column_mapping', {}),
            confidence=result_dict.get('confidence', 0.0),
            raw_response=response
        )

    def _format_table_preview(self, data: List[List[Any]]) -> str:
        """格式化表格预览"""
        if not data:
            return ""

        # 转换为 DataFrame 以便格式化
        df = pd.DataFrame(data)
        return df.to_csv(index=False, header=False)

    def _parse_response(self, response: str) -> Optional[Dict[str, Any]]:
        """解析 LLM 响应"""
        try:
            # 清理 Markdown 代码块标记
            text = response.strip()
            if text.startswith('```json'):
                text = text[7:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()

            result = json.loads(text)

            # 验证必要字段
            required_fields = ['header_row', 'data_start_row', 'column_mapping']
            for field in required_fields:
                if field not in result:
                    logger.error(f"响应缺少必要字段：{field}")
                    return None

            return result
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败：{e}, 响应：{response[:200]}...")
            return None
        except Exception as e:
            logger.error(f"响应解析异常：{e}")
            return None

    def validate_and_enrich(
        self,
        result: HeaderDetectionResult,
        data: List[List[Any]]
    ) -> HeaderDetectionResult:
        """
        验证并丰富检测结果

        Args:
            result: 检测结果
            data: 原始数据

        Returns:
            验证后的结果
        """
        # 验证行号是否合理
        if result.header_row >= len(data):
            logger.warning(f"表头行号{result.header_row}超出数据范围")
            result.header_row = min(result.header_row, len(data) - 1)

        if result.data_start_row > len(data):
            logger.warning(f"数据起始行{result.data_start_row}超出数据范围")
            result.data_start_row = len(data)

        # 验证列映射
        header_row = data[result.header_row] if result.header_row < len(data) else []
        for col_name in result.column_mapping.keys():
            if col_name not in header_row:
                logger.warning(f"列映射中的列名'{col_name}'不在表头行中")

        return result

    def get_enriched_mapping(
        self,
        result: HeaderDetectionResult,
        header_row: List[Any]
    ) -> Dict[str, Dict[str, Any]]:
        """
        获取丰富的列映射信息

        Returns:
            {标准字段：{original_name: str, index: int, confidence: float}}
        """
        enriched = {}

        for orig_name, std_field in result.column_mapping.items():
            try:
                idx = header_row.index(orig_name)
                enriched[std_field] = {
                    'original_name': orig_name,
                    'index': idx,
                    'confidence': result.confidence
                }
            except (ValueError, TypeError):
                logger.warning(f"列名'{orig_name}'在表头中找不到")

        return enriched


def detect_header_simple(
    data: List[List[Any]],
    max_preview_rows: int = 20
) -> Optional[HeaderDetectionResult]:
    """
    便捷函数：检测表头

    Args:
        data: 原始数据
        max_preview_rows: 最多分析的行数

    Returns:
        检测结果
    """
    detector = HeaderDetector()
    return detector.detect(data, max_preview_rows)
