"""币种标准化模块

提供币种名称到 ISO 4217 三位代码的转换功能。
"""

import json
from pathlib import Path
from typing import Optional, Tuple


class CurrencyNormalizer:
    """币种标准化器

    将各种币种名称、符号统一转换为 ISO 4217 三位代码。

    示例：
        normalizer = CurrencyNormalizer()
        code, confidence = normalizer.normalize("美金")
        print(code)  # 输出：USD
        print(confidence)  # 输出：1.0
    """

    def __init__(self, mapping_path: Optional[str] = None):
        """初始化币种标准化器

        Args:
            mapping_path: 币种映射配置文件路径。如果为 None，使用默认路径。
        """
        self.mappings: dict = {}
        self.iso_codes: dict = {}

        if mapping_path:
            mapping_file = Path(mapping_path)
        else:
            # 默认配置文件路径
            mapping_file = Path(__file__).parent.parent / "config" / "currency_mapping.json"

        self._load_mappings(mapping_file)

    def _load_mappings(self, mapping_file: Path) -> None:
        """加载币种映射配置文件

        Args:
            mapping_file: 配置文件路径

        Raises:
            FileNotFoundError: 配置文件不存在时抛出
            json.JSONDecodeError: 配置文件格式错误时抛出
        """
        if not mapping_file.exists():
            # 使用默认映射
            self.mappings = self._get_default_mappings()
            self.iso_codes = self._get_default_iso_codes()
            return

        with open(mapping_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.mappings = data.get('mappings', {})
        self.iso_codes = data.get('iso_4217_codes', {})

    def _get_default_mappings(self) -> dict:
        """获取默认币种映射"""
        return {
            '美元': 'USD', '美金': 'USD', 'USD': 'USD', '$': 'USD',
            '人民币': 'CNY', 'CNY': 'CNY', '¥': 'CNY', 'RMB': 'CNY', '元': 'CNY',
            '欧元': 'EUR', 'EUR': 'EUR', '€': 'EUR',
            '日元': 'JPY', 'JPY': 'JPY',
            '英镑': 'GBP', 'GBP': 'GBP', '£': 'GBP',
            '港元': 'HKD', 'HKD': 'HKD', 'HK$': 'HKD',
            '新元': 'SGD', 'SGD': 'SGD', 'S$': 'SGD',
        }

    def _get_default_iso_codes(self) -> dict:
        """获取默认 ISO 4217 代码信息"""
        return {
            'USD': {'name': 'United States Dollar', 'symbol': '$', 'Chinese': '美元'},
            'CNY': {'name': 'Chinese Yuan', 'symbol': '¥', 'Chinese': '人民币'},
            'EUR': {'name': 'Euro', 'symbol': '€', 'Chinese': '欧元'},
        }

    def normalize(self, currency: str) -> Tuple[Optional[str], float, Optional[str]]:
        """标准化币种名称

        Args:
            currency: 币种名称或符号，如"美金"、"USD"、"$"等

        Returns:
            tuple: (标准化的 ISO 4217 代码，置信度，原始映射值)
                   如果无法识别，返回 (None, 0.0, None)
        """
        if not currency or not isinstance(currency, str):
            return None, 0.0, None

        currency_str = currency.strip()

        if not currency_str:
            return None, 0.0, None

        # 精确匹配
        if currency_str in self.mappings:
            return self.mappings[currency_str], 1.0, currency_str

        # 去除空格后匹配
        currency_no_space = currency_str.replace(' ', '')
        if currency_no_space in self.mappings:
            return self.mappings[currency_no_space], 0.95, currency_no_space

        # 大写后匹配
        currency_upper = currency_str.upper()
        if currency_upper in self.mappings:
            return self.mappings[currency_upper], 0.95, currency_upper

        # 模糊匹配（部分匹配）
        for key, code in self.mappings.items():
            if currency_str in key or key in currency_str:
                return code, 0.8, key

        # 返回 None 表示无法识别
        return None, 0.0, None

    def normalize_batch(self, currencies: list) -> list:
        """批量标准化币种列表

        Args:
            currencies: 币种名称或符号列表

        Returns:
            list: 标准化结果列表，每个元素为 (代码，置信度，原始值) 元组
        """
        return [self.normalize(c) for c in currencies]

    def get_currency_info(self, code: str) -> Optional[dict]:
        """获取币种信息

        Args:
            code: ISO 4217 三位代码

        Returns:
            dict: 币种信息，包含 name、symbol、Chinese 等字段
                  如果代码不存在，返回 None
        """
        return self.iso_codes.get(code.upper())

    def is_valid_code(self, code: str) -> bool:
        """验证 ISO 4217 代码是否有效

        Args:
            code: 待验证的代码

        Returns:
            bool: 代码是否有效
        """
        if not code or not isinstance(code, str):
            return False

        # 检查是否为 3 位大写字母
        if len(code) != 3 or not code.isalpha():
            return False

        return code.upper() in self.iso_codes

    def get_all_codes(self) -> list:
        """获取所有支持的 ISO 4217 代码列表

        Returns:
            list: ISO 4217 代码列表
        """
        return list(self.iso_codes.keys())

    def get_alias_for_code(self, code: str) -> list:
        """获取某个 ISO 4217 代码的所有别名

        Args:
            code: ISO 4217 三位代码

        Returns:
            list: 所有映射到该代码的别名列表
        """
        return [key for key, value in self.mappings.items() if value == code.upper()]


# 创建全局实例
_default_normalizer: Optional[CurrencyNormalizer] = None


def get_currency_normalizer() -> CurrencyNormalizer:
    """获取全局币种标准化器实例

    Returns:
        CurrencyNormalizer: 全局标准化器实例
    """
    global _default_normalizer
    if _default_normalizer is None:
        _default_normalizer = CurrencyNormalizer()
    return _default_normalizer


def normalize_currency(currency: str) -> Tuple[Optional[str], float, Optional[str]]:
    """便捷函数：标准化币种名称

    Args:
        currency: 币种名称或符号

    Returns:
        tuple: (标准化的 ISO 4217 代码，置信度，原始映射值)
    """
    return get_currency_normalizer().normalize(currency)
