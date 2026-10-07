"""Agent 测试"""
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
import tempfile

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent import AgentCoordinator
from src.agent.reasoning import AIReasoner
from src.utils.config import Config
from src.utils.logger import setup_logger

logger = setup_logger("test")


class _OfflineReasoner(AIReasoner):
    """离线推理引擎替身：始终报告 AI 不可用

    单元测试不应依赖本机是否运行 Ollama、也不应触发真实（可能数分钟）的
    大模型调用，因此统一用本替身替代。
    """

    def __init__(self, *args, **kwargs):
        pass

    def is_available(self) -> bool:
        return False


class _FakeReasoner(AIReasoner):
    """模拟一个"可用"的推理引擎，用于覆盖 AI 分支"""

    def __init__(self, *args, **kwargs):
        pass

    def is_available(self) -> bool:
        return True

    def analyze_data(self, data_preview, columns):
        return {"analysis": "ok", "details": "stubbed"}

    def select_template(self, data_type, product_count, exporter, importer):
        return {"recommendation": "报关单", "confidence": "high"}

    def get_fix_suggestion(self, validation_report):
        return "stubbed suggestion"


class TestAgentCoordinator(unittest.TestCase):
    """测试 Agent 协调器"""

    @classmethod
    def setUpClass(cls):
        """创建测试数据

        使用临时目录中的扁平化 CSV：DataLoader 仅支持 csv/xlsx/xls/txt，
        此前的 test_data.json 属于不受支持的格式，必然加载失败。
        """
        cls._temp_dir = tempfile.TemporaryDirectory()
        cls.test_file = Path(cls._temp_dir.name) / "test_data.csv"

        rows = [
            "exporter,importer,invoice_number,contract_number,"
            "port_of_loading,port_of_discharge,currency,"
            "hs_code,product_name,quantity,unit,unit_price,weight,origin",
            "Test Company,Test Importer,INV-TEST-001,CONTRACT-001,"
            "Shanghai,Los Angeles,USD,"
            "85285210,Test Monitor,100,PCS,100.00,5.0,CN",
            "Test Company,Test Importer,INV-TEST-001,CONTRACT-001,"
            "Shanghai,Los Angeles,USD,"
            "84713010,Test Laptop,50,PCS,500.00,2.0,CN",
        ]
        cls.test_file.write_text("\n".join(rows) + "\n", encoding="utf-8")

    def setUp(self):
        """隔离副作用，保证测试不触网、不依赖 Ollama、不污染仓库

        - 用离线替身替换 AIReasoner：避免真实大模型调用
        - 把 Config.OUTPUT_DIR 指向临时目录：报告生成会写 docx，
          否则会不断往仓库的 output/ 目录里堆积文件
        """
        patcher = patch.object(
            sys.modules["src.agent.coordinator"], "AIReasoner", _OfflineReasoner
        )
        self.addCleanup(patcher.stop)
        patcher.start()

        self._orig_output_dir = Config.OUTPUT_DIR
        type(self)._saved_output_dir = self._orig_output_dir
        Config.OUTPUT_DIR = Path(self._temp_dir.name)
        self.addCleanup(self._restore_output_dir)

    @classmethod
    def _restore_output_dir(cls):
        Config.OUTPUT_DIR = cls._saved_output_dir

    @classmethod
    def tearDownClass(cls):
        """清理临时测试数据"""
        cls._temp_dir.cleanup()

    def test_initialization(self):
        """测试初始化"""
        agent = AgentCoordinator()
        self.assertIsNotNone(agent)
        self.assertIsNotNone(agent.loader)
        self.assertIsNotNone(agent.validator)
        self.assertIsNotNone(agent.template_engine)
        self.assertIsNotNone(agent.ai_reasoner)

    def test_process_file(self):
        """测试文件处理"""
        agent = AgentCoordinator()
        result = agent.process_file(str(self.test_file))

        # 检查结果结构
        self.assertIn("success", result)
        self.assertIn("output_file", result)
        self.assertIn("errors", result)
        self.assertIn("warnings", result)
        self.assertIn("steps_completed", result)

        # 使用受支持的 CSV 输入时，完整流程应当成功
        self.assertTrue(result["success"], f"处理失败：{result['errors']}")
        self.assertTrue(result["output_file"])
        self.assertEqual(
            result["steps_completed"],
            ["load_file", "analyze_data", "parse_data",
             "validate_data", "select_template", "generate_report"],
        )

        # AI 不可用（如本地未运行 Ollama）时不应写入 ai_suggestion
        if not agent.ai_reasoner.is_available():
            self.assertNotIn("ai_suggestion", result)

    def test_get_status(self):
        """测试状态获取"""
        agent = AgentCoordinator()
        result = agent.process_file(str(self.test_file))

        status = agent.get_status()

        self.assertIn("has_data", status)
        self.assertIn("product_count", status)
        self.assertIn("ai_available", status)

        if result["success"]:
            self.assertTrue(status["has_data"])
            self.assertEqual(status["product_count"], 2)

    def test_reset(self):
        """测试重置"""
        agent = AgentCoordinator()
        agent.process_file(str(self.test_file))

        # 处理前应该有数据
        self.assertTrue(agent.get_status()["has_data"])

        # 重置后应该没有数据
        agent.reset()
        self.assertFalse(agent.get_status()["has_data"])

    def test_process_file_with_ai_available(self):
        """AI 可用时应写入分析与模板建议（使用替身，不触网）"""
        with patch.object(
            sys.modules["src.agent.coordinator"], "AIReasoner", _FakeReasoner
        ):
            agent = AgentCoordinator()
            self.assertTrue(agent.ai_reasoner.is_available())
            result = agent.process_file(str(self.test_file))

        self.assertTrue(result["success"], f"处理失败：{result['errors']}")
        self.assertEqual(result["template_suggestion"]["recommendation"], "报关单")
        self.assertEqual(agent.get_status()["ai_available"], True)


class TestAIAvailability(unittest.TestCase):
    """测试 AI 可用性"""

    def test_ai_reasoner_available(self):
        """测试 AI 推理引擎"""
        from src.agent import AIReasoner

        reasoner = AIReasoner()
        # 只检查是否可初始化，不实际调用 API
        self.assertIsNotNone(reasoner)

    def test_ollama_import(self):
        """测试 Ollama 导入"""
        try:
            import ollama
            # Ollama 可用
            self.assertTrue(True)
        except ImportError:
            # Ollama 不可用 - 这也是正常的
            self.assertTrue(True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
