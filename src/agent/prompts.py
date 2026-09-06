"""提示词管理"""


class Prompts:
    """提示词管理"""

    # 海关报关处理专家系统提示词
    CUSTOMS_EXPERT_SYSTEM = """你是一位专业海关报表处理专家，精通《中华人民共和国海关进出口货物报关单填制规范》。你的任务是根据用户给出的表格内容，准确提取并标准化报关所需信息。"""

    # 海关报关信息提取用户提示词
    CUSTOMS_EXTRACTION = """请从以下海关报表内容中提取关键信息，并以 JSON 格式输出。若某项缺失或不确定，请给出置信度（0-1）并标注"需人工确认"。

报表内容：
{raw_table_text}

提取字段：
- 报关单号（entry_number）
- 项号（item_number）：商品在报关单中的序号，通常为"1、2、3..."或"01、02、03..."
- 关联项号（related_item_number）：如果商品与另一项有关联（如成套商品、配件），记录关联的项号
- 商品序号（product_sequence）：商品在原始报表中的行号/序号，用于保持原始顺序
- 商品名称（product_name）
- HS 编码（hs_code）
- 原产国（origin_country）
- 数量（quantity）及单位
- 单价（unit_price）币种
- 总价（total_price）币种
- 贸易方式（trade_mode）
- 运输方式（transport_mode）

输出 JSON 示例：
{{
  "entry_number": "XXXXX",
  "entry_number_reasoning": "从报表第一行'报关单号'列直接提取",
  "items": [
    {{
      "item_number": "1",
      "item_number_reasoning": "从'项号'列提取，原文为'1'",
      "related_item_number": null,
      "related_item_number_reasoning": "该项无关联项号",
      "product_sequence": 1,
      "product_sequence_reasoning": "该项在原始报表中为第 1 行商品",
      "product_name": "XXX",
      "product_name_reasoning": "从'商品名称'列第 2 行提取原文'XXXX'",
      "hs_code": "XXXX.XX",
      "hs_code_reasoning": "从'HS 编码'列提取，原文为'XXXX.XX'",
      "origin_country": "XXX",
      "origin_country_reasoning": "从'原产国'列提取，原文为'中国'",
      "quantity": 100,
      "quantity_reasoning": "从'数量'列提取数值 100",
      "unit": "千克",
      "unit_reasoning": "从'单位'列提取原文'千克'",
      "unit_price": 5.2,
      "unit_price_reasoning": "从'单价'列提取数值 5.2",
      "currency": "USD",
      "currency_reasoning": "从'币种'列推断为 USD，原文标注'$'",
      "total_price": 520,
      "total_price_reasoning": "由 quantity(100) * unit_price(5.2) 计算得出",
      "confidence": 0.95
    }},
    {{
      "item_number": "2",
      "item_number_reasoning": "从'项号'列提取，原文为'2'",
      "related_item_number": "1",
      "related_item_number_reasoning": "该项为第 1 项的配件，有关联关系",
      "product_sequence": 2,
      "product_sequence_reasoning": "该项在原始报表中为第 2 行商品",
      "product_name": "配件",
      "product_name_reasoning": "从'商品名称'列第 3 行提取原文'配件'",
      "hs_code": "XXXX.XX",
      "hs_code_reasoning": "从'HS 编码'列提取",
      "quantity": 50,
      "quantity_reasoning": "从'数量'列提取数值 50",
      "unit": "件",
      "unit_reasoning": "从'单位'列提取原文'件'",
      "unit_price": 2.0,
      "unit_price_reasoning": "从'单价'列提取数值 2.0",
      "currency": "USD",
      "currency_reasoning": "同报关单币种",
      "total_price": 100,
      "total_price_reasoning": "由 quantity(50) * unit_price(2.0) 计算得出",
      "confidence": 0.92
    }}
  ],
  "flags": []
}}

注意：
1. **项号识别**：
   - 项号通常标识为"项号"、"项目号"、"序号"等列
   - 格式可能为"1"、"01"、"第一项"、"Item 1"等，需标准化为纯数字字符串
   - 如果表单项之间有关联关系（如主商品与配件），记录关联项号

2. **商品序号（product_sequence）**：
   - 记录商品在原始报表中的行号/顺序，从 1 开始计数
   - 用于保持 items 数组与原始报表的顺序一致
   - 即使项号跳号或重复，product_sequence 也应连续递增

3. **items 数组顺序**：
   - items 数组必须严格按照原始报表的行顺序排列
   - 使用 product_sequence 字段标识原始顺序
   - 不要对 items 进行任何排序或重新排列

4. **其他要求**：
   - HS 编码必须为纯数字，如有小数点保留
   - 数量与总价若可推断，请在 reasoning 中说明推断逻辑
   - 每个字段必须有对应的 reasoning 字段
   - 不要添加任何解释性文字，仅输出 JSON"""

    # 数据分析提示词
    ANALYZE_DATA = """你是一位海关报关专家。请分析以下数据：

数据预览：
{data_preview}

列名列表：
{columns}

请分析：
1. 数据的结构是什么？
2. 每列代表什么含义？
3. 是否存在数据质量问题？
4. 应该生成哪种类型的报关单据？

请以 JSON 格式返回分析结果。"""

    # 数据修正建议提示词
    FIX_SUGGESTION = """你是一位海关报关专家。数据存在以下问题：

验证报告：
{validation_report}

请提供详细的修正建议：
1. 每个问题的原因
2. 具体的修正方法
3. 如何避免类似问题

请用简洁清晰的语言回答。"""

    # 模板选择提示词
    SELECT_TEMPLATE = """你是一位海关报关专家。需要根据以下数据生成报关单据：

数据类型：{data_type}
产品数量：{product_count}
出口商：{exporter}
进口商：{importer}

可选单据类型：
- 报关单：正式报关使用
- 装箱单：用于装运
- 发票：用于结算

请分析并推荐最适合的单据类型，并说明理由。"""

    # 智能填充提示词
    SMART_FILL = """你是一位海关报关专家。需要将以下数据填充到{report_type}：

数据：
{data}

请检查：
1. 所有必填字段是否完整
2. 数值计算是否正确
3. 是否需要额外的汇总信息

提供需要补充的信息列表。"""

    # 异常处理提示词
    HANDLE_ANOMALY = """报关过程中发现以下异常：

异常描述：{anomaly_description}
相关数据：{related_data}

请分析：
1. 异常的原因
2. 可能的影响
3. 推荐的解决方案
4. 是否需要人工干预

用简洁的语言回答。"""
