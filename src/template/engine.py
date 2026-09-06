"""模板引擎"""
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

try:
    from docx import Document
    from docx.shared import Inches, Pt, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from ..data.models import CustomsData
from ..utils.config import Config
from ..utils.logger import setup_logger
from ..utils.constants import CURRENCY_SYMBOLS

logger = setup_logger(__name__)


class TemplateEngine:
    """报表模板引擎"""

    def __init__(self):
        self.template_dir = Config.TEMPLATE_DIR

    def generate_document(self, data: CustomsData, output_path: str,
                         report_type: str = "declaration") -> bool:
        """
        生成 Word 文档
        :param data: 数据对象
        :param output_path: 输出路径
        :param report_type: 报表类型
        :return: 是否成功
        """
        if not DOCX_AVAILABLE:
            logger.error("python-docx 库不可用")
            return False

        try:
            doc = Document()

            # 设置中文字体支持
            doc.styles['Normal'].font.name = 'SimSun'
            doc.styles['Normal']._element.rPr.rFonts.set(
                r'{http://schemas.openxmlformats.org/wordprocessingml/2006/main}ascii', 'Calibri')

            # 添加标题
            self._add_title(doc, report_type, data)

            # 添加基本信息
            self._add_header_section(doc, data)

            # 添加产品表格
            self._add_product_table(doc, data)

            # 添加汇总信息
            self._add_summary_section(doc, data)

            # 添加页脚
            self._add_footer(doc)

            # 保存文档
            doc.save(output_path)
            logger.info(f"文档保存成功：{output_path}")
            return True

        except Exception as e:
            logger.error(f"生成文档失败：{e}", exc_info=True)
            return False

    def _add_title(self, doc, report_type: str, data: CustomsData):
        """添加标题"""
        title = doc.add_paragraph()
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_run = title.add_run(f"{'报关单' if report_type == 'declaration' else report_type}")
        title_run.bold = True
        title_run.font.size = Pt(18)

    def _add_header_section(self, doc, data: CustomsData):
        """添加基本信息部分"""
        # 创建基本信息表格
        table = doc.add_table(rows=4, cols=4)
        table.style = 'Table Grid'
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        # 填充基本信息
        header_items = [
            ("出口商", data.exporter, "进口商", data.importer),
            ("发票号", data.invoice_number or "N/A", "合同号", data.contract_number or "N/A"),
            ("装货港", data.port_of_loading or "N/A", "卸货港", data.port_of_discharge or "N/A"),
            ("币种", data.currency, "申报日期", data.declaration_date.strftime("%Y-%m-%d") if data.declaration_date else datetime.now().strftime("%Y-%m-%d")),
        ]

        for i, (label1, value1, label2, value2) in enumerate(header_items):
            table.rows[i].cells[0].text = label1
            table.rows[i].cells[1].text = value1
            table.rows[i].cells[2].text = label2
            table.rows[i].cells[3].text = value2

            # 设置字体
            for cell in table.rows[i].cells:
                cell.paragraphs[0].runs[0].font.size = Pt(10)

    def _add_product_table(self, doc, data: CustomsData):
        """添加产品明细表格"""
        p = doc.add_paragraph("\n\n")
        p.add_run("商品明细").bold = True

        # 创建产品表格
        table = doc.add_table(
            rows=len(data.products) + 1,
            cols=8
        )
        table.style = 'Table Grid'

        # 设置表头
        headers = ["序号", "HS 编码", "商品名称", "数量", "单位", "单价", "总价", "重量 (KG)"]
        for i, header in enumerate(headers):
            table.rows[0].cells[i].text = header
            table.rows[0].cells[i].paragraphs[0].runs[0].bold = True

        # 填充数据
        currency_symbol = CURRENCY_SYMBOLS.get(data.currency, "¥")

        for i, product in enumerate(data.products):
            row = table.rows[i + 1]
            row.cells[0].text = str(i + 1)
            row.cells[1].text = product.hs_code
            row.cells[2].text = product.product_name
            row.cells[3].text = f"{product.quantity:.3f}"
            row.cells[4].text = product.unit
            row.cells[5].text = f"{currency_symbol}{product.unit_price:.2f}"
            row.cells[6].text = f"{currency_symbol}{product.quantity * product.unit_price:.2f}"
            row.cells[7].text = f"{product.weight:.3f}"

    def _add_summary_section(self, doc, data: CustomsData):
        """添加汇总信息"""
        p = doc.add_paragraph("\n\n")
        p.add_run("汇总信息").bold = True

        currency_symbol = CURRENCY_SYMBOLS.get(data.currency, "¥")

        summary_text = (
            f"商品项数：{len(data.products)}\n"
            f"总重量：{data.total_weight:.3f} KG\n"
            f"总价值：{currency_symbol}{data.total_value:.2f}"
        )

        p = doc.add_paragraph(summary_text)
        p.paragraph_format.left_indent = Cm(2)

    def _add_footer(self, doc):
        """添加页脚"""
        section = doc.sections[0]
        footer = section.footer

        footer_p = footer.paragraphs[0]
        footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER

        footer_text = f"本单据于 {datetime.now().strftime('%Y-%m-%d')} 生成 | 海关报关系统"
        footer_p.add_run(footer_text).font.size = Pt(8)

    def generate_excel(self, data: CustomsData, output_path: str) -> bool:
        """
        生成 Excel 文件
        :param data: 数据对象
        :param output_path: 输出路径
        :return: 是否成功
        """
        if not PANDAS_AVAILABLE:
            logger.error("pandas 库不可用")
            return False

        try:
            # 准备数据
            products_data = []
            for i, product in enumerate(data.products, 1):
                products_data.append({
                    "序号": i,
                    "HS 编码": product.hs_code,
                    "商品名称": product.product_name,
                    "数量": product.quantity,
                    "单位": product.unit,
                    "单价": product.unit_price,
                    "总价": product.quantity * product.unit_price,
                    "重量 (KG)": product.weight,
                    "原产地": product.origin
                })

            df = pd.DataFrame(products_data)

            # 写入 Excel
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='报关单明细')

                # 添加基本信息
                worksheet = writer.sheets['报关单明细']
                worksheet['A1'] = "报关单基本信息"
                worksheet['A3'] = "出口商:"
                worksheet['B3'] = data.exporter
                worksheet['A4'] = "进口商:"
                worksheet['B4'] = data.importer
                worksheet['A5'] = "币种:"
                worksheet['B5'] = data.currency

            logger.info(f"Excel 文件保存成功：{output_path}")
            return True

        except Exception as e:
            logger.error(f"生成 Excel 失败：{e}", exc_info=True)
            return False
