"""测试数据缓存模块"""
import pytest
import pandas as pd
from pathlib import Path
import tempfile
import os

from src.data.loader import DataLoader
from src.data.cache import DataCache, get_cache, clear_global_cache


@pytest.fixture
def sample_data():
    """创建测试数据"""
    data = {
        '出口商': ['公司 A', '公司 A'],
        '进口商': ['公司 B', '公司 B'],
        'HS 编码': ['123456', '789012'],
        '品名': ['产品 1', '产品 2'],
        '数量': [100, 200],
        '单位': ['件', '件'],
        '单价': [10.5, 20.5],
        '重量': [50.0, 100.0],
        '原产地': ['中国', '中国']
    }
    return pd.DataFrame(data)


@pytest.fixture
def temp_excel_file(sample_data):
    """创建临时 Excel 文件"""
    temp_file = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
    sample_data.to_excel(temp_file, index=False, engine='openpyxl')
    temp_file.close()
    yield temp_file.name
    # 清理
    if os.path.exists(temp_file.name):
        os.remove(temp_file.name)


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    yield temp_db.name
    # 清理
    if os.path.exists(temp_db.name):
        os.remove(temp_db.name)


class TestDataCache:
    """测试 DataCache 类"""

    def test_init_db(self, temp_db):
        """测试数据库初始化"""
        cache = DataCache(db_path=temp_db)
        assert cache.conn is not None
        cache.close()

    def test_set_and_get(self, sample_data, temp_db):
        """测试缓存的存储和读取"""
        cache = DataCache(db_path=temp_db)

        schema = {
            'exporter': '出口商',
            'importer': '进口商',
            'hs_code': 'HS 编码'
        }

        parse_result = {
            'exporter': '公司 A',
            'importer': '公司 B',
            'products': [
                {
                    'hs_code': '123456',
                    'product_name': '产品 1',
                    'quantity': 100.0
                }
            ]
        }

        # 存储
        result = cache.set('test.xlsx', sample_data, schema, parse_result)
        assert result is True

        # 读取
        cached = cache.get('test.xlsx', sample_data)
        assert cached is not None
        assert cached['schema']['exporter'] == '出口商'
        assert cached['parse_result']['exporter'] == '公司 A'
        cache.close()

    def test_cache_miss(self, sample_data, temp_db):
        """测试缓存未命中"""
        cache = DataCache(db_path=temp_db)
        result = cache.get('nonexistent.xlsx', sample_data)
        assert result is None
        cache.close()

    def test_cache_hit_count(self, sample_data, temp_db):
        """测试缓存命中次数递增"""
        cache = DataCache(db_path=temp_db)

        schema = {'exporter': '出口商'}
        parse_result = {'exporter': '公司 A'}

        cache.set('test.xlsx', sample_data, schema, parse_result)

        # 第一次读取
        cached1 = cache.get('test.xlsx', sample_data)
        assert cached1['hit_count'] == 1

        # 第二次读取
        cached2 = cache.get('test.xlsx', sample_data)
        assert cached2['hit_count'] == 2
        cache.close()

    def test_clear_cache(self, sample_data, temp_db):
        """测试清理缓存"""
        cache = DataCache(db_path=temp_db)

        # 存储一些数据
        schema = {'exporter': '出口商'}
        parse_result = {'exporter': '公司 A'}
        cache.set('test.xlsx', sample_data, schema, parse_result)

        # 验证存在
        assert cache.get('test.xlsx', sample_data) is not None

        # 清理
        deleted = cache.clear()
        assert deleted == 1

        # 验证不存在
        assert cache.get('test.xlsx', sample_data) is None
        cache.close()

    def test_get_stats(self, sample_data, temp_db):
        """测试获取缓存统计"""
        cache = DataCache(db_path=temp_db)

        schema = {'exporter': '出口商'}
        parse_result = {'exporter': '公司 A'}
        cache.set('test.xlsx', sample_data, schema, parse_result)

        stats = cache.get_stats()
        assert stats['total_records'] == 1
        assert stats['cache_size_kb'] > 0
        cache.close()


class TestDataLoaderWithCache:
    """测试 DataLoader 集成缓存"""

    def test_cache_enabled(self, temp_excel_file):
        """测试缓存启用"""
        loader = DataLoader(enable_cache=True, cache_prefix_rows=2)
        assert loader.enable_cache is True
        assert loader.cache is not None
        loader.load_file(temp_excel_file)

        # 第一次解析
        result1 = loader.parse_to_model()
        assert result1 is not None

        # 第二次解析（应该命中缓存）
        result2 = loader.parse_to_model()
        assert result2 is not None

        # 检查缓存统计
        stats = loader.get_cache_stats()
        assert stats['enabled'] is True
        assert stats['total_records'] >= 1

    def test_cache_disabled(self, temp_excel_file):
        """测试缓存禁用"""
        loader = DataLoader(enable_cache=False)
        assert loader.enable_cache is False
        loader.load_file(temp_excel_file)

        # 统计应该显示未启用
        stats = loader.get_cache_stats()
        assert stats['enabled'] is False

    def test_skip_cache(self, temp_excel_file):
        """测试跳过缓存"""
        loader = DataLoader(enable_cache=True, cache_prefix_rows=2)
        loader.load_file(temp_excel_file)

        # 第一次解析
        result1 = loader.parse_to_model()
        assert result1 is not None

        # 跳过缓存重新解析
        result2 = loader.parse_to_model(skip_cache=True)
        assert result2 is not None

    def test_custom_cache_prefix_rows(self, temp_excel_file):
        """测试自定义缓存前缀行数"""
        loader = DataLoader(enable_cache=True, cache_prefix_rows=5)
        assert loader.cache_prefix_rows == 5


class TestGlobalCache:
    """测试全局缓存实例"""

    def test_get_cache_singleton(self):
        """测试单例模式"""
        cache1 = get_cache()
        cache2 = get_cache()
        assert cache1 is cache2

    def test_clear_global_cache(self):
        """测试清除全局缓存"""
        cache = get_cache()
        old_conn = cache.conn
        clear_global_cache()
        assert cache.conn is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
