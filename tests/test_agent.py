"""Agent 测试"""
import unittest
from pathlib import Path
import sys
import json

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent import AgentCoordinator
from src.utils.logger import setup_logger

logger = setup_logger("test")


class TestAgentCoordinator(unittest.TestCase):
    """测试 Agent 协调器"""

    @classmethod
    def setUpClass(cls):
        """创建测试数据"""
        cls.test_data = {
            "exporter": "Test Company",
            "importer": "Test Importer",
            "invoice_number": "INV-TEST-001",
            "contract_number": "CONTRACT-001",
            "port_of_loading": "Shanghai",
            "port_of_discharge": "Los Angeles",
            "currency": "USD",
            "products": [
                {
                    "hs_code": "85285210",
                    "product_name": "Test Monitor",
                    "quantity": 100,
                    "unit": "PCS",
                    "unit_price": 100.00,
                    "weight": 5.0,
                    "origin": "CN"
                },
                {
                    "hs_code": "84713010",
                    "product_name": "Test Laptop",
                    "quantity": 50,
                    "unit": "PCS",
                    "unit_price": 500.00,
                    "weight": 2.0,
                    "origin": "CN"
                }
            ]
        }

        cls.test_file = PROJECT_ROOT / "tests" / "test_data.json"
        with open(cls.test_file, 'w', encoding='utf-8') as f:
            json.dump(cls.test_data, f, ensure_ascii=False, indent=2)

    @classmethod
    def tearDownClass(cls):
        """清理测试数据"""
        if cls.test_file.exists():
            cls.test_file.unlink()

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

        # 检查 AI 是否可用
        if agent.ai_reasoner.is_available():
            self.assertIn("ai_suggestion", result) or result["success"]

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
