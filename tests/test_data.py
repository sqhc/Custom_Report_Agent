"""数据模块测试"""
import unittest
import pandas as pd
from pathlib import Path
import sys
import json
import tempfile

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data import DataLoader, DataValidator, CustomsData, ProductItem
from src.utils.logger import setup_logger

logger = setup_logger("test")


class TestDataLoader(unittest.TestCase):
    """测试数据加载器"""

    def setUp(self):
        """准备测试数据"""
        self.loader = DataLoader()

        # 使用临时文件，避免覆盖 / 删除仓库中被跟踪的 tests/sample_data.csv
        # （该文件供 run_test.py 使用，内容与本测试生成的不同）
        self._temp_dir = tempfile.TemporaryDirectory()
        self.sample_csv = Path(self._temp_dir.name) / "sample_data.csv"

        # 创建测试 CSV
        self._create_sample_csv()

    def tearDown(self):
        """清理（只清理本测试创建的临时文件）"""
        self._temp_dir.cleanup()

    def _create_sample_csv(self):
        """创建样本 CSV 文件"""
        data = {
            "Exporter": ["Test Company"],
            "Importer": ["Test Importer"],
            "Invoice No": ["INV-001"],
            "HS Code": ["85285210"],
            "Product Name": ["Test Monitor"],
            "Quantity": [100],
            "Unit": ["PCS"],
            "Unit Price": [100.0],
            "Weight": [5.0],
            "Origin": ["CN"]
        }
        df = pd.DataFrame(data)
        df.to_csv(self.sample_csv, index=False)

    def test_load_csv(self):
        """测试 CSV 加载"""
        result = self.loader.load_file(str(self.sample_csv))
        self.assertTrue(result)
        self.assertIsNotNone(self.loader.raw_data)

    def test_detect_schema(self):
        """测试 schema 检测"""
        self.loader.load_file(str(self.sample_csv))
        schema = self.loader.detect_schema()
        self.assertIsNotNone(schema)

    def test_parse_to_model(self):
        """测试解析到模型"""
        self.loader.load_file(str(self.sample_csv))
        schema = self.loader.detect_schema()
        data = self.loader.parse_to_model(schema)
        self.assertIsNotNone(data)


class TestDataValidator(unittest.TestCase):
    """测试数据验证器"""

    def setUp(self):
        """准备测试数据"""
        self.validator = DataValidator()

        # 创建有效的数据
        self.valid_data = CustomsData(
            exporter="Test Company",
            importer="Test Importer",
            invoice_number="INV-001",
            currency="USD",
            products=[
                ProductItem(
                    hs_code="85285210",
                    product_name="Test Monitor",
                    quantity=100,
                    unit="PCS",
                    unit_price=100.0,
                    total_value=10000.0,
                    weight=5.0,
                    origin="CN"
                )
            ]
        )

        # 创建无效的数据
        self.invalid_data = CustomsData(
            exporter="",  # 缺少出口商
            importer="Test Importer",
            invoice_number="INV-001",
            currency="USD",
            products=[
                ProductItem(
                    hs_code="INVALID",  # 无效的 HS 编码
                    product_name="Test",
                    quantity=-1,  # 负数数量
                    unit="PCS",
                    unit_price=100.0,
                    total_value=-100.0,
                    weight=5.0,
                    origin="CN"
                )
            ]
        )

    def test_validate_valid_data(self):
        """测试验证有效数据"""
        self.validator.reset()
        is_valid = self.validator.validate(self.valid_data)
        self.assertTrue(is_valid)

    def test_validate_invalid_data(self):
        """测试验证无效数据"""
        self.validator.reset()
        is_valid = self.validator.validate(self.invalid_data)
        self.assertFalse(is_valid)

    def test_get_report(self):
        """测试获取报告"""
        self.validator.reset()
        self.validator.validate(self.invalid_data)
        report = self.validator.get_report()

        self.assertIn("errors", report)
        self.assertIn("warnings", report)
        self.assertTrue(len(report["errors"]) > 0)


class TestCustomsData(unittest.TestCase):
    """测试 CustomsData 模型"""

    def test_calculate_totals(self):
        """测试总计计算"""
        products = [
            ProductItem(
                hs_code="85285210",
                product_name="Monitor",
                quantity=100,
                unit="PCS",
                unit_price=100.0,
                total_value=10000.0,
                weight=5.0,
                origin="CN"
            ),
            ProductItem(
                hs_code="84713010",
                product_name="Laptop",
                quantity=50,
                unit="PCS",
                unit_price=500.0,
                total_value=25000.0,
                weight=2.0,
                origin="CN"
            )
        ]

        data = CustomsData(
            exporter="Test Company",
            importer="Test Importer",
            invoice_number="INV-001",
            currency="USD",
            products=products
        )

        # 检查总计
        self.assertEqual(data.total_weight, 5200.0)  # (100*5) + (50*2)
        self.assertEqual(data.total_value, 35000.0)  # 10000 + 25000

    def test_invalid_hs_code(self):
        """测试 HS 编码格式"""
        product = ProductItem(
            hs_code="INVALID",
            product_name="Test",
            quantity=100,
            unit="PCS",
            unit_price=100.0,
            total_value=10000.0,
            weight=5.0,
            origin="CN"
        )

        self.assertFalse(product.hs_code_validation)


if __name__ == '__main__':
    unittest.main(verbosity=2)
