"""合规风险检查器"""

import re
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from .constants import (
    RISK_TYPES,
    RISK_LEVELS,
    IMPORT_LICENSE_HSCODE_PREFIXES,
    ANTI_DUMPING_LIST,
    QUOTA_CONTROL_HSCODE_PREFIXES,
    QUALITY_CERT_LIST,
    SANITARY_INSPECTION_HSCODE_PREFIXES,
    TWO_USE_HSCODE_PREFIXES,
    ORIGIN_RESTRICTED_COUNTRY,
)


@dataclass
class RiskInfo:
    """风险信息"""
    risk_type: str
    risk_level: str
    description: str
    details: str = ""

    def to_dict(self) -> Dict:
        return {
            'risk_type': self.risk_type,
            'risk_level': self.risk_level,
            'description': self.description,
            'details': self.details
        }


@dataclass
class ComplianceCheckResult:
    """合规检查结果"""
    hs_code: str
    product_name: str
    origin_country: str
    risks: List[RiskInfo] = field(default_factory=list)
    max_risk_level: str = "LOW"
    is_compliant: bool = True

    def add_risk(self, risk_info: RiskInfo):
        """添加风险"""
        self.risks.append(risk_info)

        # 更新最高风险等级
        current_level_idx = RISK_LEVELS.index(self.max_risk_level) if self.max_risk_level in RISK_LEVELS else 0
        new_level_idx = RISK_LEVELS.index(risk_info.risk_level) if risk_info.risk_level in RISK_LEVELS else 0

        if new_level_idx > current_level_idx:
            self.max_risk_level = risk_info.risk_level

        # 如果存在 HIGH 或 CRITICAL 风险，则不合规
        if risk_info.risk_level in ['HIGH', 'CRITICAL']:
            self.is_compliant = False

    def to_dict(self) -> Dict:
        return {
            'hs_code': self.hs_code,
            'product_name': self.product_name,
            'origin_country': self.origin_country,
            'risks': [risk.to_dict() for risk in self.risks],
            'max_risk_level': self.max_risk_level,
            'is_compliant': self.is_compliant
        }


class ComplianceChecker:
    """合规风险检查器"""

    def __init__(self):
        """初始化"""
        pass

    def check(self, hs_code: str, product_name: str, origin_country: str) -> ComplianceCheckResult:
        """
        检查合规风险

        Args:
            hs_code: HS 编码
            product_name: 商品名称
            origin_country: 原产国

        Returns:
            ComplianceCheckResult: 检查结果
        """
        result = ComplianceCheckResult(
            hs_code=hs_code,
            product_name=product_name,
            origin_country=origin_country
        )

        # 检查进口许可证
        self._check_import_license(hs_code, result)

        # 检查反倾销税
        self._check_anti_dumping(hs_code, origin_country, product_name, result)

        # 检查配额管制
        self._check_quota_control(hs_code, result)

        # 检查质量认证
        self._check_quality_cert(hs_code, product_name, result)

        # 检查检验检疫
        self._check_sanitary_inspection(hs_code, product_name, result)

        # 检查两用物项
        self._check_two_use(hs_code, product_name, result)

        # 检查原产地限制
        self._check_origin_restriction(origin_country, hs_code, product_name, result)

        return result

    def _hs_code_starts_with(self, hs_code: str, prefixes: List[str]) -> bool:
        """检查 HS 编码是否以某个前缀开头"""
        hs_code = str(hs_code).lstrip('0')  # 去除前导零
        for prefix in prefixes:
            if hs_code.startswith(str(prefix).lstrip('0')):
                return True
        return False

    def _check_import_license(self, hs_code: str, result: ComplianceCheckResult):
        """检查进口许可证"""
        if self._hs_code_starts_with(hs_code, IMPORT_LICENSE_HSCODE_PREFIXES):
            risk = RiskInfo(
                risk_type=RISK_TYPES['IMPORT_LICENSE']['code'],
                risk_level=RISK_TYPES['IMPORT_LICENSE']['severity'],
                description=RISK_TYPES['IMPORT_LICENSE']['description'],
                details=f"HS 编码 {hs_code} 属于需要进口许可证的商品范围"
            )
            result.add_risk(risk)

    def _check_anti_dumping(self, hs_code: str, origin_country: str, product_name: str, result: ComplianceCheckResult):
        """检查反倾销税"""
        for item in ANTI_DUMPING_LIST:
            if hs_code.startswith(item['hs_code_prefix']):
                # 检查原产国
                for origin in item['origins']:
                    if origin_country == origin or origin_country.lower() in origin.lower() or origin.lower() in origin_country.lower():
                        risk = RiskInfo(
                            risk_type=RISK_TYPES['ANTI_DUMPING']['code'],
                            risk_level=RISK_TYPES['ANTI_DUMPING']['severity'],
                            description=RISK_TYPES['ANTI_DUMPING']['description'],
                            details=f"原产国 {origin_country} 的{item['product']}（HS 编码 {item['hs_code_prefix']} 开头）可能受反倾销措施影响"
                        )
                        result.add_risk(risk)
                        break

    def _check_quota_control(self, hs_code: str, result: ComplianceCheckResult):
        """检查配额管制"""
        if self._hs_code_starts_with(hs_code, QUOTA_CONTROL_HSCODE_PREFIXES):
            risk = RiskInfo(
                risk_type=RISK_TYPES['QUOTA_CONTROL']['code'],
                risk_level=RISK_TYPES['QUOTA_CONTROL']['severity'],
                description=RISK_TYPES['QUOTA_CONTROL']['description'],
                details=f"HS 编码 {hs_code} 属于需要进口配额的商品范围"
            )
            result.add_risk(risk)

    def _check_quality_cert(self, hs_code: str, product_name: str, result: ComplianceCheckResult):
        """检查质量认证"""
        for item in QUALITY_CERT_LIST:
            if hs_code.startswith(item['hs_code_prefix']):
                risk = RiskInfo(
                    risk_type=RISK_TYPES['QUALITY_CERT']['code'],
                    risk_level=RISK_TYPES['QUALITY_CERT']['severity'],
                    description=RISK_TYPES['QUALITY_CERT']['description'],
                    details=f"{item['product']}（HS 编码 {item['hs_code_prefix']} 开头）需要{item['cert']}质量认证"
                )
                result.add_risk(risk)
                break

    def _check_sanitary_inspection(self, hs_code: str, product_name: str, result: ComplianceCheckResult):
        """检查检验检疫"""
        if self._hs_code_starts_with(hs_code, SANITARY_INSPECTION_HSCODE_PREFIXES):
            risk = RiskInfo(
                risk_type=RISK_TYPES['SANITARY_INSPECTION']['code'],
                risk_level=RISK_TYPES['SANITARY_INSPECTION']['severity'],
                description=RISK_TYPES['SANITARY_INSPECTION']['description'],
                details=f"HS 编码 {hs_code} 属于需要检验检疫的商品范围"
            )
            result.add_risk(risk)

    def _check_two_use(self, hs_code: str, product_name: str, result: ComplianceCheckResult):
        """检查两用物项"""
        if self._hs_code_starts_with(hs_code, TWO_USE_HSCODE_PREFIXES):
            risk = RiskInfo(
                risk_type=RISK_TYPES['TWO_USE']['code'],
                risk_level=RISK_TYPES['TWO_USE']['severity'],
                description=RISK_TYPES['TWO_USE']['description'],
                details=f"HS 编码 {hs_code} 可能属于军民两用物项管制范围，需进一步核实"
            )
            result.add_risk(risk)

    def _check_origin_restriction(self, origin_country: str, hs_code: str, product_name: str, result: ComplianceCheckResult):
        """检查原产地限制"""
        for country, info in ORIGIN_RESTRICTED_COUNTRY.items():
            if country == origin_country:
                # 检查 HS 编码是否在限制列表中
                if '*' in info['hs_code_prefixes'] or any(hs_code.startswith(prefix) for prefix in info['hs_code_prefixes']):
                    risk = RiskInfo(
                        risk_type=RISK_TYPES['ORIGIN_RESTRICT']['code'],
                        risk_level=info['risk_level'],
                        description=RISK_TYPES['ORIGIN_RESTRICT']['description'],
                        details=f"原产国 {country} 的{product_name}受{info['reason']}限制"
                    )
                    result.add_risk(risk)
                break


def check_compliance(hs_code: str, product_name: str, origin_country: str) -> ComplianceCheckResult:
    """
    便捷函数：检查单个商品的合规风险

    Args:
        hs_code: HS 编码
        product_name: 商品名称
        origin_country: 原产国

    Returns:
        ComplianceCheckResult: 检查结果
    """
    checker = ComplianceChecker()
    return checker.check(hs_code, product_name, origin_country)


def check_products_compliance(products: List[Dict]) -> List[ComplianceCheckResult]:
    """
    检查多个商品的合规风险

    Args:
        products: 商品列表，每个商品包含 hs_code, product_name, origin_country

    Returns:
        List[ComplianceCheckResult]: 检查结果列表
    """
    checker = ComplianceChecker()
    results = []

    for product in products:
        hs_code = product.get('hs_code', '')
        product_name = product.get('product_name', '')
        origin_country = product.get('origin_country', '')

        result = checker.check(hs_code, product_name, origin_country)
        results.append(result)

    return results


if __name__ == '__main__':
    # 测试
    checker = ComplianceChecker()

    # 测试用例 1：无风险商品
    result = checker.check('85171200', '手机', '日本')
    print(f"测试 1: {result.product_name} ({result.origin_country})")
    print(f"  HS 编码：{result.hs_code}")
    print(f"  合规状态：{'合规' if result.is_compliant else '存在风险'}")
    print(f"  最高风险等级：{result.max_risk_level}")
    for risk in result.risks:
        print(f"  风险：{risk.description}")
        print(f"    详情：{risk.details}")
    print()

    # 测试用例 2：受反倾销税影响
    result = checker.check('72072000', '热轧钢坯', '韩国')
    print(f"测试 2: {result.product_name} ({result.origin_country})")
    print(f"  HS 编码：{result.hs_code}")
    print(f"  合规状态：{'合规' if result.is_compliant else '存在风险'}")
    print(f"  最高风险等级：{result.max_risk_level}")
    for risk in result.risks:
        print(f"  风险：{risk.description}")
        print(f"    详情：{risk.details}")
    print()

    # 测试用例 3：需要检验检疫
    result = checker.check('02013000', '鲜冻牛肉', '美国')
    print(f"测试 3: {result.product_name} ({result.origin_country})")
    print(f"  HS 编码：{result.hs_code}")
    print(f"  合规状态：{'合规' if result.is_compliant else '存在风险'}")
    print(f"  最高风险等级：{result.max_risk_level}")
    for risk in result.risks:
        print(f"  风险：{risk.description}")
        print(f"    详情：{risk.details}")
    print()

    # 测试用例 4：需要 CCC 认证
    result = checker.check('84151010', '空调', '德国')
    print(f"测试 4: {result.product_name} ({result.origin_country})")
    print(f"  HS 编码：{result.hs_code}")
    print(f"  合规状态：{'合规' if result.is_compliant else '存在风险'}")
    print(f"  最高风险等级：{result.max_risk_level}")
    for risk in result.risks:
        print(f"  风险：{risk.description}")
        print(f"    详情：{risk.details}")
    print()

    # 测试用例 5：受原产地限制（朝鲜）
    result = checker.check('85171200', '手机', '朝鲜')
    print(f"测试 5: {result.product_name} ({result.origin_country})")
    print(f"  HS 编码：{result.hs_code}")
    print(f"  合规状态：{'合规' if result.is_compliant else '存在风险'}")
    print(f"  最高风险等级：{result.max_risk_level}")
    for risk in result.risks:
        print(f"  风险：{risk.description}")
        print(f"    详情：{risk.details}")
    print()
