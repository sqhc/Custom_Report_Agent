"""AI Agent 协调器"""
from typing import Optional, Dict, Any, Callable, List
from pathlib import Path
from datetime import datetime

from ..data import DataLoader, DataValidator, CustomsData
from ..template import TemplateEngine
from ..utils.config import Config
from ..utils.llm_errors import LLMConfigError
from ..utils.logger import setup_logger
from .reasoning import AIReasoner

logger = setup_logger(__name__)


class AgentCoordinator:
    """AI Agent 协调器 - 主控制器"""

    def __init__(self):
        """初始化 Agent"""
        self.loader = DataLoader()
        self.validator = DataValidator()
        self.template_engine = TemplateEngine()

        # LLM 配置错误属于启动期错误：记录清晰日志后向上抛出
        try:
            self.ai_reasoner = AIReasoner()
        except LLMConfigError as e:
            logger.error(f"LLM 配置错误，无法初始化 AI 推理引擎：\n{e}")
            raise

        self.current_data: Optional[CustomsData] = None
        self.current_file: Optional[str] = None
        self.output_files: List[str] = []

        logger.info("AI Agent Coordinator initialized")

    def process_file(self, file_path: str, progress_callback: Callable[[str], None] = None) -> Dict[str, Any]:
        """
        处理文件的完整流程
        :param file_path: 输入文件路径
        :param progress_callback: 进度回调函数
        :return: 处理结果
        """
        result = {
            "success": False,
            "output_file": None,
            "errors": [],
            "warnings": [],
            "steps_completed": []
        }

        try:
            # 步骤 1: 加载数据
            if progress_callback:
                progress_callback("正在加载文件...")
            logger.info(f"开始加载文件：{file_path}")

            if not self.loader.load_file(file_path):
                result["errors"].append("加载文件失败")
                return result

            self.current_file = file_path
            result["steps_completed"].append("load_file")

            # 步骤 2: AI 分析数据
            if progress_callback:
                progress_callback("AI 正在分析数据...")
            logger.info("AI 分析数据中...")

            preview = self.loader.get_preview(5)
            columns = self.loader.get_columns()

            if self.ai_reasoner.is_available():
                analysis = self.ai_reasoner.analyze_data(
                    preview.to_string(),
                    columns
                )
                logger.info(f"AI 分析结果：{analysis.get('analysis', 'N/A')}")

            result["steps_completed"].append("analyze_data")

            # 步骤 3: 解析数据
            if progress_callback:
                progress_callback("正在解析数据...")
            logger.info("解析数据中...")

            schema = self.loader.detect_schema()
            self.current_data = self.loader.parse_to_model(schema)

            if not self.current_data:
                result["errors"].append("解析数据失败")
                return result

            result["steps_completed"].append("parse_data")

            # 步骤 4: 验证数据
            if progress_callback:
                progress_callback("正在验证数据...")
            logger.info("验证数据中...")

            is_valid = self.validator.validate(self.current_data)
            validation_report = self.validator.get_report()

            if not is_valid:
                result["errors"].extend([e["message"] for e in validation_report["errors"]])
                result["warnings"].extend([w["message"] for w in validation_report["warnings"]])

                # AI 提供修正建议
                if self.ai_reasoner.is_available():
                    suggestion = self.ai_reasoner.get_fix_suggestion(validation_report)
                    if suggestion:
                        logger.info(f"AI 修正建议：{suggestion[:200]}...")
                        result["ai_suggestion"] = suggestion
                    else:
                        logger.warning("AI 未能提供修正建议")

            result["validation_report"] = validation_report
            result["steps_completed"].append("validate_data")

            # 步骤 5: 智能选择模板
            if progress_callback:
                progress_callback("AI 正在选择模板...")

            if self.ai_reasoner.is_available():
                template_suggestion = self.ai_reasoner.select_template(
                    data_type=self._detect_data_type(),
                    product_count=len(self.current_data.products),
                    exporter=self.current_data.exporter,
                    importer=self.current_data.importer
                )
                logger.info(f"AI 推荐的模板：{template_suggestion.get('recommendation', 'N/A')[:100]}")
                result["template_suggestion"] = template_suggestion

            result["steps_completed"].append("select_template")

            # 步骤 6: 生成报表
            if progress_callback:
                progress_callback("正在生成报表...")
            logger.info("生成报表中...")

            output_file = self._generate_report("declaration")
            if output_file:
                result["success"] = True
                result["output_file"] = output_file
                self.output_files.append(output_file)
                logger.info(f"报表生成成功：{output_file}")

            result["steps_completed"].append("generate_report")

        except Exception as e:
            logger.error(f"处理文件失败：{e}", exc_info=True)
            result["errors"].append(f"处理失败：{str(e)}")

        return result

    def _detect_data_type(self) -> str:
        """检测数据类型"""
        if self.current_data:
            return f"customs_data_{len(self.current_data.products)}_products"
        return "unknown"

    def _generate_report(self, report_type: str = "declaration") -> Optional[str]:
        """生成报表"""
        if not self.current_data:
            return None

        try:
            # 生成输出文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"报关单_{self.current_data.exporter[:10]}_{timestamp}.docx"
            output_path = Config.OUTPUT_DIR / output_filename

            # 生成文档
            self.template_engine.generate_document(
                data=self.current_data,
                output_path=str(output_path),
                report_type=report_type
            )

            return str(output_path)

        except Exception as e:
            logger.error(f"生成报表失败：{e}")
            return None

    def get_status(self) -> Dict[str, Any]:
        """获取 Agent 状态"""
        return {
            "has_data": self.current_data is not None,
            "current_file": self.current_file,
            "product_count": len(self.current_data.products) if self.current_data else 0,
            "output_files": self.output_files,
            "ai_available": self.ai_reasoner.is_available()
        }

    def reset(self):
        """重置 Agent 状态"""
        self.current_data = None
        self.current_file = None
        self.loader.raw_data = None
        logger.info("Agent 已重置")
