"""数据加载器"""
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Any, List
import re

from .models import CustomsData, ProductItem
from .cache import get_cache, DataCache
from ..utils.logger import setup_logger

logger = setup_logger(__name__)

# 默认缓存配置
DEFAULT_CACHE_PREFIX_ROWS = 3  # 使用前 3 行生成缓存键


class DataLoader:
    """数据加载器"""

    def __init__(self, enable_cache: bool = True, cache_prefix_rows: int = DEFAULT_CACHE_PREFIX_ROWS):
        """
        初始化数据加载器

        Args:
            enable_cache: 是否启用缓存
            cache_prefix_rows: 用于生成缓存键的前 N 行数据
        """
        self.raw_data: Optional[pd.DataFrame] = None
        self.metadata: Dict[str, Any] = {}
        self.enable_cache = enable_cache
        self.cache_prefix_rows = cache_prefix_rows
        self.cache: Optional[DataCache] = None

        if enable_cache:
            self.cache = get_cache(prefix_rows=cache_prefix_rows)
            logger.info(f"缓存已启用 (前{cache_prefix_rows}行作为缓存键)")

    def load_file(self, file_path: str) -> bool:
        """
        加载数据文件
        :param file_path: 文件路径
        :return: 是否成功
        """
        try:
            path = Path(file_path)
            if not path.exists():
                logger.error(f"文件不存在：{file_path}")
                return False

            suffix = path.suffix.lower()

            if suffix == '.csv':
                self.raw_data = pd.read_csv(file_path, encoding='utf-8', on_bad_lines='warn')
            elif suffix in ['.xlsx', '.xls']:
                self.raw_data = pd.read_excel(file_path, engine='openpyxl')
            elif suffix == '.txt':
                self.raw_data = pd.read_csv(file_path, sep='\t', encoding='utf-8')
            else:
                logger.error(f"不支持的文件格式：{suffix}")
                return False

            self.metadata = {
                'file_path': str(file_path),
                'shape': self.raw_data.shape,
                'columns': list(self.raw_data.columns),
                'format': suffix
            }

            logger.info(f"成功加载文件：{file_path}, 行数:{self.raw_data.shape[0]}, 列数:{self.raw_data.shape[1]}")
            return True

        except Exception as e:
            logger.error(f"加载文件失败：{e}")
            return False

    def get_preview(self, rows: int = 5) -> pd.DataFrame:
        """获取数据预览"""
        if self.raw_data is None:
            return pd.DataFrame()
        return self.raw_data.head(rows)

    def get_columns(self) -> List[str]:
        """获取列名"""
        if self.raw_data is None:
            return []
        return list(self.raw_data.columns)

    def detect_schema(self) -> Dict[str, Any]:
        """
        智能检测数据模式
        :return: 检测到的 schema 信息
        """
        if self.raw_data is None:
            return {}

        schema = {
            'exporter': None,
            'importer': None,
            'hs_code': None,
            'product_name': None,
            'quantity': None,
            'unit': None,
            'price': None,
            'weight': None,
            'origin': None,
            'date': None
        }

        # 列名映射 (中英文，包含常见变体)
        mappings = {
            'exporter': ['exporter', '出口商', '发货人', '卖方', 'supplier', 'vendor'],
            'importer': ['importer', '进口商', '收货人', '买方', 'consignee'],
            'hs_code': ['hs_code', 'hscode', 'hs code', 'HS 编码', '海关编码', 'tax_code'],
            'product_name': ['product_name', 'product name', '品名', '产品名称', 'description', 'goods'],
            'quantity': ['quantity', '数量', 'qty', 'amount'],
            'unit': ['unit', '单位', 'uom'],
            'price': ['price', '单价', 'unit_price', 'unit price'],
            'weight': ['weight', '重量', 'net_weight', '毛重', 'kg'],
            'origin': ['origin', '原产地', '原产国', 'country_of_origin'],
            'date': ['date', '日期', 'declaration_date', '报关日期']
        }

        # 已匹配的列名，避免重复
        matched_columns = set()

        columns = self.raw_data.columns
        for col in columns:
            col_lower = col.lower().strip()

            for key, patterns in mappings.items():
                # 精确匹配优先
                if col_lower in patterns:
                    if key not in matched_columns:
                        schema[key] = col
                        matched_columns.add(key)
                        break
                # 模糊匹配
                elif any(pattern in col_lower for pattern in patterns):
                    if key not in matched_columns:
                        schema[key] = col
                        matched_columns.add(key)
                        break

        return schema

    def _check_cache(self, file_path: str) -> Optional[Dict[str, Any]]:
        """检查缓存是否命中

        Args:
            file_path: 文件路径

        Returns:
            缓存结果，包含 schema 和 parse_result
        """
        if not self.enable_cache or self.cache is None or self.raw_data is None:
            return None

        return self.cache.get(file_path, self.raw_data)

    def _save_to_cache(self, file_path: str, schema: Dict[str, Any],
                       customs_data: CustomsData) -> bool:
        """保存解析结果到缓存

        Args:
            file_path: 文件路径
            schema: 检测到的 schema
            customs_data: 解析后的数据

        Returns:
            是否成功保存
        """
        if not self.enable_cache or self.cache is None or self.raw_data is None:
            return False

        # 将 CustomsData 转换为字典
        parse_result = {
            'exporter': customs_data.exporter,
            'importer': customs_data.importer,
            'currency': customs_data.currency,
            'products': [
                {
                    'hs_code': p.hs_code,
                    'product_name': p.product_name,
                    'quantity': p.quantity,
                    'unit': p.unit,
                    'unit_price': p.unit_price,
                    'total_value': p.total_value,
                    'weight': p.weight,
                    'origin': p.origin
                }
                for p in customs_data.products
            ]
        }

        return self.cache.set(file_path, self.raw_data, schema, parse_result)

    def _dict_to_customs_data(self, schema: Dict[str, Any],
                              parse_result: Dict[str, Any]) -> CustomsData:
        """将字典转换为 CustomsData 对象

        Args:
            schema: schema 信息
            parse_result: 解析结果字典

        Returns:
            CustomsData 对象
        """
        products = []
        for p in parse_result.get('products', []):
            product = ProductItem(
                hs_code=p.get('hs_code', ''),
                product_name=p.get('product_name', ''),
                quantity=p.get('quantity', 0.0),
                unit=p.get('unit', ''),
                unit_price=p.get('unit_price', 0.0),
                total_value=p.get('total_value', 0.0),
                weight=p.get('weight', 0.0),
                origin=p.get('origin', '')
            )
            products.append(product)

        return CustomsData(
            exporter=parse_result.get('exporter', ''),
            importer=parse_result.get('importer', ''),
            products=products,
            currency=parse_result.get('currency', 'CNY')
        )

    def parse_to_model(self, schema: Optional[Dict[str, Any]] = None,
                       skip_cache: bool = False) -> Optional[CustomsData]:
        """
        解析数据到 CustomsData 模型

        Args:
            schema: 可选的 schema，不传则自动检测
            skip_cache: 是否跳过缓存（强制重新解析）

        Returns:
            CustomsData 对象
        """
        if self.raw_data is None:
            return None

        # 检查缓存（只有在没有传入 schema 时才检查，因为传入了表示需要自定义）
        if not skip_cache and schema is None and 'file_path' in self.metadata:
            cached = self._check_cache(self.metadata['file_path'])
            if cached:
                logger.info(f"使用缓存结果，命中次数：{cached.get('hit_count', 0)}")
                return self._dict_to_customs_data(cached['schema'], cached['parse_result'])

        # 检测或传入 schema
        if schema is None:
            schema = self.detect_schema()

        try:
            products = []

            for _, row in self.raw_data.iterrows():
                quantity = 0.0
                unit_price = 0.0

                if schema.get('quantity'):
                    try:
                        quantity = float(row[schema['quantity']])
                    except (ValueError, TypeError):
                        pass

                if schema.get('price'):
                    try:
                        unit_price = float(row[schema['price']])
                    except (ValueError, TypeError):
                        pass

                product = ProductItem(
                    hs_code=str(row[schema['hs_code']]) if schema.get('hs_code') else "",
                    product_name=str(row[schema['product_name']]) if schema.get('product_name') else "",
                    quantity=quantity,
                    unit=str(row[schema['unit']]) if schema.get('unit') else "",
                    unit_price=unit_price,
                    total_value=quantity * unit_price,
                    weight=float(row[schema['weight']]) if schema.get('weight') else 0.0,
                    origin=str(row[schema['origin']]) if schema.get('origin') else ""
                )
                products.append(product)

            customs_data = CustomsData(
                exporter=str(row[schema.get('exporter', '')]) if schema.get('exporter') else "",
                importer=str(row[schema.get('importer', '')]) if schema.get('importer') else "",
                products=products,
                currency="CNY"
            )

            # 保存到缓存
            if not skip_cache and 'file_path' in self.metadata:
                self._save_to_cache(self.metadata['file_path'], schema, customs_data)

            return customs_data

        except Exception as e:
            logger.error(f"解析数据失败：{e}")
            return None

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息

        Returns:
            缓存统计字典
        """
        if not self.enable_cache or self.cache is None:
            return {'enabled': False}
        stats = self.cache.get_stats()
        stats['enabled'] = True
        return stats
