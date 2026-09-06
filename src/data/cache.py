"""数据解析缓存模块 - 使用 SQLite 存储解析结果"""
import sqlite3
import hashlib
import json
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class DataCache:
    """数据解析缓存管理器

    缓存策略：
    1. 基于原始数据的前 N 行生成哈希作为缓存键
    2. 存储解析后的 schema 和 CustomsData
    3. 支持缓存命中统计和清理
    """

    def __init__(self, db_path: Optional[str] = None, cache_prefix_rows: int = 3):
        """
        初始化缓存

        Args:
            db_path: SQLite 数据库路径，默认为项目目录下的.data_cache.db
            cache_prefix_rows: 用于生成缓存键的前 N 行数据
        """
        if db_path is None:
            base_dir = Path(__file__).parent.parent.parent
            db_path = base_dir / ".data_cache.db"

        self.db_path = Path(db_path)
        self.cache_prefix_rows = cache_prefix_rows
        self.conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self):
        """初始化数据库和表"""
        self.conn = sqlite3.connect(str(self.db_path), timeout=30)
        self.conn.row_factory = sqlite3.Row

        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS parse_cache (
                cache_key TEXT PRIMARY KEY,
                file_path TEXT,
                raw_data_hash TEXT,
                raw_data_sample TEXT,
                schema_result TEXT,
                parse_result TEXT,
                created_at TIMESTAMP,
                accessed_at TIMESTAMP,
                hit_count INTEGER DEFAULT 0
            )
        ''')

        # 创建索引以加速查询
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_file_path
            ON parse_cache(file_path)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_created_at
            ON parse_cache(created_at)
        ''')

        self.conn.commit()
        logger.info(f"数据缓存已初始化：{self.db_path}")

    def _generate_cache_key(self, file_path: str, data_sample: str) -> str:
        """生成缓存键

        Args:
            file_path: 文件路径
            data_sample: 数据样本（前 N 行）

        Returns:
            MD5 哈希值作为缓存键
        """
        cache_str = f"{file_path}:{data_sample}"
        return hashlib.md5(cache_str.encode()).hexdigest()

    def _get_data_sample(self, df: pd.DataFrame, rows: int) -> str:
        """获取数据样本用于生成缓存键

        Args:
            df: 数据框
            rows: 取前 N 行

        Returns:
            序列化后的数据样本字符串
        """
        sample = df.head(rows)
        # 转换为字典列表，排除可能的非序列化对象
        data_dict = sample.to_dict('records')
        # 确保所有值都是可序列化的
        def make_serializable(obj):
            if isinstance(obj, dict):
                return {k: make_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [make_serializable(i) for i in obj]
            elif hasattr(obj, 'isoformat'):  # datetime 等
                return str(obj)
            else:
                return obj

        data_dict = make_serializable(data_dict)
        # 使用 sort_keys 确保相同数据生成相同 hash
        return json.dumps(data_dict, sort_keys=True, ensure_ascii=False)

    def get(self, file_path: str, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        从缓存获取解析结果

        Args:
            file_path: 文件路径
            df: 数据框（用于生成缓存键）

        Returns:
            缓存的解析结果，包含 schema 和 parse_result，未命中则返回 None
        """
        try:
            data_sample = self._get_data_sample(df, self.cache_prefix_rows)
            cache_key = self._generate_cache_key(file_path, data_sample)

            cursor = self.conn.cursor()
            cursor.execute(
                'SELECT * FROM parse_cache WHERE cache_key = ?',
                (cache_key,)
            )
            row = cursor.fetchone()

            if row:
                # 更新访问时间和命中次数
                cursor.execute(
                    '''UPDATE parse_cache
                       SET accessed_at = ?, hit_count = hit_count + 1
                       WHERE cache_key = ?''',
                    (datetime.now(), cache_key)
                )
                self.conn.commit()

                # 获取更新后的 hit_count
                cursor.execute(
                    'SELECT hit_count FROM parse_cache WHERE cache_key = ?',
                    (cache_key,)
                )
                updated_row = cursor.fetchone()

                result = {
                    'schema': json.loads(row['schema_result']),
                    'parse_result': json.loads(row['parse_result']),
                    'hit_count': updated_row['hit_count']
                }
                logger.info(f"缓存命中：{file_path}, 命中次数：{updated_row['hit_count']}")
                return result

            logger.debug(f"缓存未命中：{file_path}")
            return None

        except Exception as e:
            logger.error(f"读取缓存失败：{e}")
            return None

    def set(self, file_path: str, df: pd.DataFrame,
            schema: Dict[str, Any], parse_result: Dict[str, Any]) -> bool:
        """
        存储解析结果到缓存

        Args:
            file_path: 文件路径
            df: 数据框
            schema: 检测到的 schema
            parse_result: 解析结果

        Returns:
            是否成功存储
        """
        try:
            data_sample = self._get_data_sample(df, self.cache_prefix_rows)
            cache_key = self._generate_cache_key(file_path, data_sample)
            data_hash = hashlib.md5(data_sample.encode()).hexdigest()

            cursor = self.conn.cursor()

            # 使用 INSERT OR REPLACE 来处理重复键
            cursor.execute('''
                INSERT OR REPLACE INTO parse_cache
                (cache_key, file_path, raw_data_hash, raw_data_sample,
                 schema_result, parse_result, created_at, accessed_at, hit_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            ''', (
                cache_key,
                file_path,
                data_hash,
                data_sample,
                json.dumps(schema, ensure_ascii=False),
                json.dumps(parse_result, ensure_ascii=False),
                datetime.now(),
                datetime.now()
            ))

            self.conn.commit()
            logger.debug(f"缓存已存储：{file_path}, key: {cache_key[:8]}...")
            return True

        except Exception as e:
            logger.error(f"存储缓存失败：{e}")
            return False

    def clear(self, older_than_days: Optional[int] = None) -> int:
        """
        清理缓存

        Args:
            older_than_days: 只清理 N 天之前的缓存，None 则清理全部

        Returns:
            删除的缓存数量
        """
        try:
            cursor = self.conn.cursor()

            if older_than_days:
                threshold = datetime.now()
                from datetime import timedelta
                threshold = threshold - timedelta(days=older_than_days)
                cursor.execute(
                    'DELETE FROM parse_cache WHERE created_at < ?',
                    (threshold,)
                )
            else:
                cursor.execute('DELETE FROM parse_cache')

            deleted_count = cursor.rowcount
            self.conn.commit()
            logger.info(f"缓存已清理，删除 {deleted_count} 条记录")
            return deleted_count

        except Exception as e:
            logger.error(f"清理缓存失败：{e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        try:
            cursor = self.conn.cursor()

            # 总记录数
            cursor.execute('SELECT COUNT(*) as count FROM parse_cache')
            total_records = cursor.fetchone()['count']

            # 总命中次数
            cursor.execute('SELECT SUM(hit_count) as total_hits FROM parse_cache')
            total_hits = cursor.fetchone()['total_hits'] or 0

            # 缓存大小（字节）
            cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
            cache_size = cursor.fetchone()['size']

            # 最早的缓存
            cursor.execute('SELECT MIN(created_at) as earliest FROM parse_cache')
            earliest = cursor.fetchone()['earliest']

            # 最新的缓存
            cursor.execute('SELECT MAX(accessed_at) as latest FROM parse_cache')
            latest = cursor.fetchone()['latest']

            return {
                'total_records': total_records,
                'total_hits': total_hits,
                'cache_size_bytes': cache_size,
                'cache_size_kb': round(cache_size / 1024, 2),
                'earliest_entry': earliest,
                'latest_access': latest
            }

        except Exception as e:
            logger.error(f"获取缓存统计失败：{e}")
            return {}

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.debug("缓存连接已关闭")


# 全局缓存实例（单例模式）
_global_cache: Optional[DataCache] = None


def get_cache(db_path: Optional[str] = None, prefix_rows: int = 3) -> DataCache:
    """获取全局缓存实例

    Args:
        db_path: 自定义数据库路径
        prefix_rows: 用于生成缓存键的前 N 行数

    Returns:
        DataCache 实例
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = DataCache(db_path=db_path, cache_prefix_rows=prefix_rows)
    return _global_cache


def clear_global_cache():
    """清除全局缓存实例"""
    global _global_cache
    if _global_cache:
        _global_cache.close()
        _global_cache = None
