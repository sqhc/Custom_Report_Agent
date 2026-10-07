"""数据验证器"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import re

from .models import CustomsData, ProductItem
from ..utils.constants import HS_CODE_PATTERN, DECLARATION_REQUIRED_FIELDS
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class ValidationError:
    """验证错误"""
    field: str
    message: str
    severity: str  # 'error', 'warning', 'info'
    suggested_fix: Optional[str] = None


class DataValidator:
    """数据验证器"""

    def __init__(self):
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []

    def reset(self):
        """清空上一次验证留下的错误与警告

        注意：:meth:`validate` 每次调用时也会自动清空状态，
        本方法用于在不执行验证的情况下显式重置。
        """
        self.errors = []
        self.warnings = []

    def validate(self, data: CustomsData) -> bool:
        """
        验证数据
        :param data: CustomsData 对象
        :return: 是否有错误
        """
        self.errors = []
        self.warnings = []

        # 验证必填字段
        self._validate_required_fields(data)

        # 验证 HS 编码
        self._validate_hs_codes(data)

        # 验证数值
        self._validate_numbers(data)

        # 验证逻辑关系
        self._validate_logic(data)

        has_errors = len(self.errors) > 0
        logger.info(f"验证完成：{len(self.errors)} 个错误，{len(self.warnings)} 个警告")
        return not has_errors

    def _validate_required_fields(self, data: CustomsData):
        """验证必填字段"""
        # 验证出口商
        if not data.exporter or not data.exporter.strip():
            self.errors.append(ValidationError(
                field="exporter",
                message="出口商不能为空",
                severity="error",
                suggested_fix="请补充出口商信息"
            ))

        # 验证进口商
        if not data.importer or not data.importer.strip():
            self.errors.append(ValidationError(
                field="importer",
                message="进口商不能为空",
                severity="error",
                suggested_fix="请补充进口商信息"
            ))

        # 验证产品列表
        if not data.products:
            self.errors.append(ValidationError(
                field="products",
                message="产品列表不能为空",
                severity="error",
                suggested_fix="请添加产品信息"
            ))

        # 验证每个产品项
        for i, product in enumerate(data.products):
            if not product.hs_code or not product.hs_code.strip():
                self.errors.append(ValidationError(
                    field=f"products[{i}].hs_code",
                    message=f"第{i+1}个产品的 HS 编码不能为空",
                    severity="error",
                    suggested_fix="请补充 HS 编码"
                ))

            if not product.product_name or not product.product_name.strip():
                self.errors.append(ValidationError(
                    field=f"products[{i}].product_name",
                    message=f"第{i+1}个产品的品名不能为空",
                    severity="error",
                    suggested_fix="请补充产品品名"
                ))

    def _validate_hs_codes(self, data: CustomsData):
        """验证 HS 编码格式"""
        pattern = re.compile(HS_CODE_PATTERN)

        for i, product in enumerate(data.products):
            if product.hs_code:
                if not pattern.match(product.hs_code):
                    self.warnings.append(ValidationError(
                        field=f"products[{i}].hs_code",
                        message=f"第{i+1}个产品的 HS 编码格式可能不正确：{product.hs_code}",
                        severity="warning",
                        suggested_fix="HS 编码应为 6 位或更多数字，如：123456 或 123456-10"
                    ))

    def _validate_numbers(self, data: CustomsData):
        """验证数值"""
        for i, product in enumerate(data.products):
            # 验证数量
            if product.quantity <= 0:
                self.errors.append(ValidationError(
                    field=f"products[{i}].quantity",
                    message=f"第{i+1}个产品的数量必须大于 0",
                    severity="error",
                    suggested_fix="请检查并修正数量"
                ))

            # 验证价格
            if product.unit_price < 0:
                self.errors.append(ValidationError(
                    field=f"products[{i}].unit_price",
                    message=f"第{i+1}个产品的单价不能为负数",
                    severity="error",
                    suggested_fix="请检查单价"
                ))

            # 验证重量
            if product.weight < 0:
                self.errors.append(ValidationError(
                    field=f"products[{i}].weight",
                    message=f"第{i+1}个产品的重量不能为负数",
                    severity="error",
                    suggested_fix="请检查重量"
                ))

            # 计算总价验证
            expected_total = product.quantity * product.unit_price
            if product.total_value > 0:
                if abs(product.total_value - expected_total) / expected_total > 0.01:
                    self.warnings.append(ValidationError(
                        field=f"products[{i}].total_value",
                        message=f"第{i+1}个产品的总价与数量*单价不一致",
                        severity="warning",
                        suggested_fix=f"建议总价：{expected_total:.2f}"
                    ))

    def _validate_logic(self, data: CustomsData):
        """验证逻辑关系"""
        # 检查是否有未填写原产地的产品
        for i, product in enumerate(data.products):
            if not product.origin or not product.origin.strip():
                self.warnings.append(ValidationError(
                    field=f"products[{i}].origin",
                    message=f"第{i+1}个产品缺少原产地信息",
                    severity="warning",
                    suggested_fix="建议补充原产地信息"
                ))

    def get_report(self) -> Dict[str, Any]:
        """获取验证报告"""
        return {
            "valid": len(self.errors) == 0,
            "errors": [
                {
                    "field": e.field,
                    "message": e.message,
                    "suggested_fix": e.suggested_fix
                }
                for e in self.errors
            ],
            "warnings": [
                {
                    "field": w.field,
                    "message": w.message,
                    "suggested_fix": w.suggested_fix
                }
                for w in self.warnings
            ],
            "error_count": len(self.errors),
            "warning_count": len(self.warnings)
        }
