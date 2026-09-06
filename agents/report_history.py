"""ReportHistory - 报表历史存储与统计分析

支持 SQLite 和 CSV 两种存储方式，提供贸易量趋势、主要贸易伙伴、商品类别分布等统计图表。
"""

import os
import json
import sqlite3
import csv
from typing import Dict, List, Any, Optional
from datetime import datetime, date
from dataclasses import dataclass, asdict
import base64
from io import BytesIO


@dataclass
class ReportRecord:
    """报表记录"""
    id: int
    source_file: str
    table_name: str
    extraction_time: str
    total_rows: int
    matched_rows: int
    accuracy: float
    trade_volume: float  # 贸易量
    trade_partner: str  # 贸易伙伴
    product_category: str  # 商品类别
    country: str  # 国家/地区
    value: float  # 贸易额


class ReportHistory:
    """报表历史记录管理器"""

    def __init__(self, db_path: str = "report_history.db"):
        """
        初始化历史记录管理器

        Args:
            db_path: SQLite 数据库文件路径
        """
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 创建报表历史表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS report_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT NOT NULL,
                table_name TEXT NOT NULL,
                extraction_time TEXT NOT NULL,
                total_rows INTEGER DEFAULT 0,
                matched_rows INTEGER DEFAULT 0,
                accuracy REAL DEFAULT 0,
                trade_volume REAL DEFAULT 0,
                trade_partner TEXT,
                product_category TEXT,
                country TEXT,
                value REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_extraction_time
            ON report_history(extraction_time)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_trade_partner
            ON report_history(trade_partner)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_product_category
            ON report_history(product_category)
        ''')

        conn.commit()
        conn.close()

    def save_record(self, record: Dict[str, Any]) -> int:
        """
        保存报表记录

        Args:
            record: 报表记录字典

        Returns:
            记录 ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO report_history
            (source_file, table_name, extraction_time, total_rows, matched_rows,
             accuracy, trade_volume, trade_partner, product_category, country, value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record.get('source_file', ''),
            record.get('table_name', ''),
            record.get('extraction_time', datetime.now().isoformat()),
            record.get('total_rows', 0),
            record.get('matched_rows', 0),
            record.get('accuracy', 0),
            record.get('trade_volume', 0),
            record.get('trade_partner', ''),
            record.get('product_category', ''),
            record.get('country', ''),
            record.get('value', 0)
        ))

        record_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return record_id

    def save_multiple_records(self, records: List[Dict[str, Any]]) -> List[int]:
        """
        批量保存报表记录

        Args:
            records: 报表记录列表

        Returns:
            记录 ID 列表
        """
        record_ids = []
        for record in records:
            record_id = self.save_record(record)
            record_ids.append(record_id)
        return record_ids

    def get_all_records(self) -> List[ReportRecord]:
        """获取所有记录"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM report_history ORDER BY extraction_time DESC')
        rows = cursor.fetchall()

        records = []
        for row in rows:
            record = ReportRecord(
                id=row['id'],
                source_file=row['source_file'],
                table_name=row['table_name'],
                extraction_time=row['extraction_time'],
                total_rows=row['total_rows'],
                matched_rows=row['matched_rows'],
                accuracy=row['accuracy'],
                trade_volume=row['trade_volume'],
                trade_partner=row['trade_partner'],
                product_category=row['product_category'],
                country=row['country'],
                value=row['value']
            )
            records.append(record)

        conn.close()
        return records

    def get_records_by_date_range(self, start_date: str, end_date: str) -> List[ReportRecord]:
        """
        按日期范围获取记录

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            记录列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM report_history
            WHERE date(extraction_time) BETWEEN ? AND ?
            ORDER BY extraction_time DESC
        ''', (start_date, end_date))
        rows = cursor.fetchall()

        records = []
        for row in rows:
            record = ReportRecord(
                id=row['id'],
                source_file=row['source_file'],
                table_name=row['table_name'],
                extraction_time=row['extraction_time'],
                total_rows=row['total_rows'],
                matched_rows=row['matched_rows'],
                accuracy=row['accuracy'],
                trade_volume=row['trade_volume'],
                trade_partner=row['trade_partner'],
                product_category=row['product_category'],
                country=row['country'],
                value=row['value']
            )
            records.append(record)

        conn.close()
        return records

    def export_to_csv(self, output_path: str) -> str:
        """
        导出历史记录到 CSV 文件

        Args:
            output_path: 输出文件路径

        Returns:
            输出文件路径
        """
        records = self.get_all_records()

        if not records:
            print("没有数据可导出")
            return output_path

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # 写入表头
            writer.writerow([
                'ID', '源文件', '表名', '提取时间', '总行数', '匹配行数',
                '准确率', '贸易量', '贸易伙伴', '商品类别', '国家/地区', '贸易额'
            ])
            # 写入数据
            for record in records:
                writer.writerow([
                    record.id, record.source_file, record.table_name,
                    record.extraction_time, record.total_rows, record.matched_rows,
                    f"{record.accuracy:.2%}", record.trade_volume, record.trade_partner,
                    record.product_category, record.country, record.value
                ])

        return output_path

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}

        # 总记录数
        cursor.execute('SELECT COUNT(*) as count FROM report_history')
        stats['total_records'] = cursor.fetchone()['count']

        # 总贸易量
        cursor.execute('SELECT SUM(trade_volume) as total FROM report_history')
        stats['total_trade_volume'] = cursor.fetchone()['total'] or 0

        # 总贸易额
        cursor.execute('SELECT SUM(value) as total FROM report_history')
        stats['total_value'] = cursor.fetchone()['total'] or 0

        # 平均准确率
        cursor.execute('SELECT AVG(accuracy) as avg FROM report_history')
        stats['avg_accuracy'] = cursor.fetchone()['avg'] or 0

        conn.close()
        return stats

    def get_trade_partners_stats(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        获取贸易伙伴统计

        Args:
            top_n: 返回前 N 个贸易伙伴

        Returns:
            贸易伙伴统计列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT trade_partner,
                   SUM(trade_volume) as total_volume,
                   SUM(value) as total_value,
                   COUNT(*) as record_count
            FROM report_history
            WHERE trade_partner IS NOT NULL AND trade_partner != ''
            GROUP BY trade_partner
            ORDER BY total_volume DESC
            LIMIT ?
        ''', (top_n,))

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                'partner': row[0],
                'total_volume': row[1],
                'total_value': row[2],
                'record_count': row[3]
            }
            for row in rows
        ]

    def get_product_category_stats(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        获取商品类别统计

        Args:
            top_n: 返回前 N 个商品类别

        Returns:
            商品类别统计列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT product_category,
                   SUM(trade_volume) as total_volume,
                   SUM(value) as total_value,
                   COUNT(*) as record_count
            FROM report_history
            WHERE product_category IS NOT NULL AND product_category != ''
            GROUP BY product_category
            ORDER BY total_volume DESC
            LIMIT ?
        ''', (top_n,))

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                'category': row[0],
                'total_volume': row[1],
                'total_value': row[2],
                'record_count': row[3]
            }
            for row in rows
        ]

    def get_trade_volume_trend(self, group_by: str = 'month') -> List[Dict[str, Any]]:
        """
        获取贸易量趋势数据

        Args:
            group_by: 分组方式 ('day', 'week', 'month', 'year')

        Returns:
            趋势数据列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if group_by == 'day':
            date_expr = 'date(extraction_time)'
        elif group_by == 'week':
            date_expr = 'strftime("%Y-%W", extraction_time)'
        elif group_by == 'month':
            date_expr = 'strftime("%Y-%m", extraction_time)'
        elif group_by == 'year':
            date_expr = 'strftime("%Y", extraction_time)'
        else:
            date_expr = 'date(extraction_time)'

        cursor.execute(f'''
            SELECT {date_expr} as period,
                   SUM(trade_volume) as total_volume,
                   SUM(value) as total_value,
                   COUNT(*) as record_count
            FROM report_history
            GROUP BY period
            ORDER BY period
        ''')

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                'period': row[0],
                'total_volume': row[1],
                'total_value': row[2],
                'record_count': row[3]
            }
            for row in rows
        ]

    def clear_all_records(self):
        """清空所有记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM report_history')
        conn.commit()
        conn.close()


class ReportChartGenerator:
    """报表图表生成器"""

    def __init__(self, history: ReportHistory):
        """
        初始化图表生成器

        Args:
            history: 报表历史记录管理器
        """
        self.history = history
        self.charts: List[Dict[str, Any]] = []

    def _setup_matplotlib(self):
        """配置 matplotlib 中文字体支持"""
        import matplotlib.pyplot as plt

        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False

    def _save_chart(self, fig, output_dir: str, filename: str) -> str:
        """
        保存图表

        Args:
            fig: matplotlib 图形对象
            output_dir: 输出目录
            filename: 文件名

        Returns:
            保存的文件路径
        """
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, filename)
        fig.savefig(output_path, dpi=150, bbox_inches='tight')
        return output_path

    def _chart_to_base64(self, fig) -> str:
        """
        将图表转换为 Base64 编码

        Args:
            fig: matplotlib 图形对象

        Returns:
            Base64 编码字符串
        """
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        buf.close()
        return img_base64

    def generate_trade_volume_trend_chart(
        self,
        output_dir: str = "charts",
        group_by: str = 'month',
        title: str = "贸易量趋势"
    ) -> Dict[str, Any]:
        """
        生成贸易量趋势图

        Args:
            output_dir: 输出目录
            group_by: 分组方式 ('day', 'week', 'month', 'year')
            title: 图表标题

        Returns:
            图表信息字典
        """
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from datetime import datetime

        self._setup_matplotlib()

        trend_data = self.history.get_trade_volume_trend(group_by)

        if not trend_data:
            return {'error': '没有足够的数据生成趋势图'}

        fig, ax = plt.subplots(figsize=(12, 6))

        periods = [item['period'] for item in trend_data]
        volumes = [item['total_volume'] for item in trend_data]

        # 创建柱状图
        bars = ax.bar(range(len(periods)), volumes, color='#667eea', alpha=0.7)

        # 添加数值标签
        for i, (bar, volume) in enumerate(zip(bars, volumes)):
            height = bar.get_height()
            ax.annotate(f'{volume:.1f}',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3),
                       textcoords="offset points",
                       ha='center', va='bottom', fontsize=9)

        ax.set_xlabel('时间', fontsize=11)
        ax.set_ylabel('贸易量', fontsize=11)
        ax.set_title(title, fontsize=14, fontweight='bold')

        # 设置 X 轴标签
        ax.set_xticks(range(len(periods)))
        ax.set_xticklabels(periods, rotation=45, ha='right')

        ax.grid(axis='y', alpha=0.3, linestyle='--')
        plt.tight_layout()

        filename = f"trade_volume_trend_{group_by}.png"
        output_path = self._save_chart(fig, output_dir, filename)

        plt.close(fig)

        chart_info = {
            'type': 'trade_volume_trend',
            'title': title,
            'output_path': output_path,
            'data': trend_data
        }
        self.charts.append(chart_info)

        return chart_info

    def generate_trade_partner_chart(
        self,
        output_dir: str = "charts",
        top_n: int = 10,
        title: str = "主要贸易伙伴",
        chart_type: str = 'bar'
    ) -> Dict[str, Any]:
        """
        生成主要贸易伙伴图

        Args:
            output_dir: 输出目录
            top_n: 显示前 N 个贸易伙伴
            title: 图表标题
            chart_type: 图表类型 ('bar', 'pie', 'horizontal_bar')

        Returns:
            图表信息字典
        """
        import matplotlib.pyplot as plt

        self._setup_matplotlib()

        partner_data = self.history.get_trade_partners_stats(top_n)

        if not partner_data:
            return {'error': '没有足够的数据生成贸易伙伴图'}

        partners = [item['partner'] for item in partner_data]
        volumes = [item['total_volume'] for item in partner_data]

        fig, ax = plt.subplots(figsize=(12, 6))

        if chart_type == 'pie':
            # 饼图
            colors = plt.cm.Set3(range(len(partners)))
            wedges, texts, autotexts = ax.pie(
                volumes,
                labels=partners,
                autopct='%1.1f%%',
                colors=colors,
                startangle=90
            )
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')
                autotext.set_fontsize(9)
            ax.set_title(title, fontsize=14, fontweight='bold')

        elif chart_type == 'horizontal_bar':
            # 横向柱状图
            y_pos = range(len(partners))
            bars = ax.barh(y_pos, volumes, color='#764ba2', alpha=0.7)

            for bar, volume in zip(bars, volumes):
                width = bar.get_width()
                ax.annotate(f'{volume:.1f}',
                           xy=(width, bar.get_y() + bar.get_height() / 2),
                           xytext=(5, 0),
                           textcoords="offset points",
                           ha='left', va='center', fontsize=9)

            ax.set_yticks(y_pos)
            ax.set_yticklabels(partners)
            ax.set_xlabel('贸易量', fontsize=11)
            ax.set_title(title, fontsize=14, fontweight='bold')
            ax.grid(axis='x', alpha=0.3, linestyle='--')

        else:  # bar
            # 纵向柱状图
            bars = ax.bar(range(len(partners)), volumes, color='#667eea', alpha=0.7)

            for bar, volume in zip(bars, volumes):
                height = bar.get_height()
                ax.annotate(f'{volume:.1f}',
                           xy=(bar.get_x() + bar.get_width() / 2, height),
                           xytext=(0, 3),
                           textcoords="offset points",
                           ha='center', va='bottom', fontsize=9)

            ax.set_xlabel('贸易伙伴', fontsize=11)
            ax.set_ylabel('贸易量', fontsize=11)
            ax.set_title(title, fontsize=14, fontweight='bold')
            ax.set_xticks(range(len(partners)))
            ax.set_xticklabels(partners, rotation=45, ha='right')
            ax.grid(axis='y', alpha=0.3, linestyle='--')

        plt.tight_layout()

        filename = f"trade_partner_{chart_type}.png"
        output_path = self._save_chart(fig, output_dir, filename)

        plt.close(fig)

        chart_info = {
            'type': 'trade_partner',
            'title': title,
            'output_path': output_path,
            'data': partner_data
        }
        self.charts.append(chart_info)

        return chart_info

    def generate_product_category_chart(
        self,
        output_dir: str = "charts",
        top_n: int = 10,
        title: str = "商品类别分布",
        chart_type: str = 'pie'
    ) -> Dict[str, Any]:
        """
        生成商品类别分布图

        Args:
            output_dir: 输出目录
            top_n: 显示前 N 个商品类别
            title: 图表标题
            chart_type: 图表类型 ('pie', 'bar', 'doughnut')

        Returns:
            图表信息字典
        """
        import matplotlib.pyplot as plt

        self._setup_matplotlib()

        category_data = self.history.get_product_category_stats(top_n)

        if not category_data:
            return {'error': '没有足够的数据生成商品类别图'}

        categories = [item['category'] for item in category_data]
        volumes = [item['total_volume'] for item in category_data]

        fig, ax = plt.subplots(figsize=(12, 6))

        colors = plt.cm.Set2(range(len(categories)))

        if chart_type == 'doughnut':
            # 环形图
            wedges, texts, autotexts = ax.pie(
                volumes,
                labels=categories,
                autopct='%1.1f%%',
                colors=colors,
                startangle=90,
                wedgeprops=dict(width=0.3)
            )
        elif chart_type == 'pie':
            # 饼图
            wedges, texts, autotexts = ax.pie(
                volumes,
                labels=categories,
                autopct='%1.1f%%',
                colors=colors,
                startangle=90
            )
        else:  # bar
            # 柱状图
            bars = ax.bar(range(len(categories)), volumes, color=colors, alpha=0.7)

            for bar, volume in zip(bars, volumes):
                height = bar.get_height()
                ax.annotate(f'{volume:.1f}',
                           xy=(bar.get_x() + bar.get_width() / 2, height),
                           xytext=(0, 3),
                           textcoords="offset points",
                           ha='center', va='bottom', fontsize=9)

            ax.set_xlabel('商品类别', fontsize=11)
            ax.set_ylabel('贸易量', fontsize=11)
            ax.set_xticks(range(len(categories)))
            ax.set_xticklabels(categories, rotation=45, ha='right')
            ax.grid(axis='y', alpha=0.3, linestyle='--')

        if chart_type in ['pie', 'doughnut']:
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')
                autotext.set_fontsize(9)

        ax.set_title(title, fontsize=14, fontweight='bold')
        plt.tight_layout()

        filename = f"product_category_{chart_type}.png"
        output_path = self._save_chart(fig, output_dir, filename)

        plt.close(fig)

        chart_info = {
            'type': 'product_category',
            'title': title,
            'output_path': output_path,
            'data': category_data
        }
        self.charts.append(chart_info)

        return chart_info

    def generate_summary_report_html(
        self,
        output_dir: str = "charts",
        title: str = "贸易数据分析报告"
    ) -> str:
        """
        生成包含所有图表的 HTML 报告

        Args:
            output_dir: 输出目录
            title: 报告标题

        Returns:
            HTML 文件路径
        """
        # 获取统计信息
        stats = self.history.get_statistics()
        trend_data = self.history.get_trade_volume_trend('month')
        partner_data = self.history.get_trade_partners_stats(10)
        category_data = self.history.get_product_category_stats(10)

        html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            line-height: 1.6;
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .header {{
            background: white;
            color: #333;
            padding: 30px;
            margin-bottom: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }}
        .header h1 {{
            font-size: 28px;
            margin-bottom: 10px;
            color: #667eea;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }}
        .stat-card .label {{
            font-size: 14px;
            opacity: 0.9;
            margin-bottom: 8px;
        }}
        .stat-card .value {{
            font-size: 24px;
            font-weight: bold;
        }}
        .chart-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .chart-card {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }}
        .chart-card h2 {{
            font-size: 18px;
            color: #667eea;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #eee;
        }}
        .chart-card img {{
            width: 100%;
            height: auto;
        }}
        .full-width {{
            grid-column: 1 / -1;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: white;
            opacity: 0.8;
        }}
        @media (max-width: 768px) {{
            .chart-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 {title}</h1>
            <p>生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="label">总记录数</div>
                    <div class="value">{stats.get('total_records', 0)}</div>
                </div>
                <div class="stat-card">
                    <div class="label">总贸易量</div>
                    <div class="value">{stats.get('total_trade_volume', 0):,.1f}</div>
                </div>
                <div class="stat-card">
                    <div class="label">总贸易额</div>
                    <div class="value">¥{stats.get('total_value', 0):,.2f}</div>
                </div>
                <div class="stat-card">
                    <div class="label">平均准确率</div>
                    <div class="value">{stats.get('avg_accuracy', 0):.2%}</div>
                </div>
            </div>
        </div>

        <div class="chart-grid">
            <div class="chart-card full-width">
                <h2>📈 贸易量趋势（按月）</h2>
                {self._generate_trend_chart_svg(trend_data)}
            </div>
            <div class="chart-card">
                <h2>🤝 主要贸易伙伴</h2>
                {self._generate_partner_chart_svg(partner_data)}
            </div>
            <div class="chart-card">
                <h2>📦 商品类别分布</h2>
                {self._generate_category_chart_svg(category_data)}
            </div>
        </div>

        <div class="footer">
            <p>报表历史存储与统计分析系统 | Report History & Analytics</p>
        </div>
    </div>
</body>
</html>'''

        output_path = os.path.join(output_dir, "summary_report.html")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return output_path

    def _generate_trend_chart_svg(self, data: List[Dict]) -> str:
        """生成趋势图 SVG（简化版）"""
        if not data:
            return '<p style="text-align:center;color:#999;">暂无数据</p>'

        periods = [d['period'] for d in data]
        volumes = [d['total_volume'] for d in data]
        max_vol = max(volumes) if volumes else 1

        # 创建简单的柱状图 SVG
        width = 800
        height = 300
        padding = 50
        bar_width = (width - 2 * padding - len(periods) * 10) / len(periods)

        svg = f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
            <rect width="{width}" height="{height}" fill="white"/>
'''

        # 绘制柱状图
        for i, (period, volume) in enumerate(zip(periods, volumes)):
            x = padding + i * (bar_width + 10)
            bar_height = (volume / max_vol) * (height - 2 * padding)
            y = height - padding - bar_height

            color = '#667eea'
            svg += f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" fill="{color}" opacity="0.7"/>\n'
            svg += f'<text x="{x + bar_width/2}" y="{height - 15}" font-size="10" text-anchor="middle" fill="#666">{period}</text>\n'
            svg += f'<text x="{x + bar_width/2}" y="{y - 5}" font-size="10" text-anchor="middle" fill="#333">{volume:.1f}</text>\n'

        svg += '</svg>'
        return svg

    def _generate_partner_chart_svg(self, data: List[Dict]) -> str:
        """生成贸易伙伴图 SVG（简化版）"""
        if not data:
            return '<p style="text-align:center;color:#999;">暂无数据</p>'

        partners = [d['partner'] for d in data]
        volumes = [d['total_volume'] for d in data]
        max_vol = max(volumes) if volumes else 1

        width = 500
        height = len(partners) * 35 + 40

        svg = f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
            <rect width="{width}" height="{height}" fill="white"/>
'''

        colors = ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#00f2fe', '#43e97b', '#38f9d7', '#fa709a', '#fee140']

        for i, (partner, volume) in enumerate(zip(partners, volumes)):
            bar_width = (volume / max_vol) * (width - 100)
            y = 20 + i * 35

            color = colors[i % len(colors)]
            svg += f'<text x="10" y="{y + 12}" font-size="11" fill="#333">{partner}</text>\n'
            svg += f'<rect x="120" y="{y}" width="{bar_width}" height="18" fill="{color}" opacity="0.7"/>\n'
            svg += f'<text x="{120 + bar_width + 5}" y="{y + 12}" font-size="10" fill="#666">{volume:.1f}</text>\n'

        svg += '</svg>'
        return svg

    def _generate_category_chart_svg(self, data: List[Dict]) -> str:
        """生成商品类别图 SVG（简化版）"""
        if not data:
            return '<p style="text-align:center;color:#999;">暂无数据</p>'

        categories = [d['category'] for d in data]
        volumes = [d['total_volume'] for d in data]
        total = sum(volumes)

        width = 400
        height = 400
        center_x = width / 2
        center_y = height / 2 + 20
        radius = 150

        svg = f'''<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
            <rect width="{width}" height="{height}" fill="white"/>
'''

        colors = ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#00f2fe', '#43e97b', '#38f9d7', '#fa709a', '#fee140']
        start_angle = -90

        for i, (category, volume) in enumerate(zip(categories, volumes)):
            angle = (volume / total) * 360
            color = colors[i % len(colors)]

            # 绘制扇形
            large_arc = 1 if angle > 180 else 0

            # 计算终点坐标
            import math
            end_rad = math.radians(start_angle + angle)
            end_x = center_x + radius * math.cos(end_rad)
            end_y = center_y - radius * math.sin(end_rad)

            svg += f'''<path d="M {center_x} {center_y} L {center_x + radius} {center_y} A {radius} {radius} 0 {large_arc} 1 {end_x} {end_y} Z" fill="{color}" opacity="0.8"/>\n'''

            # 添加标签
            label_angle = start_angle + angle / 2
            label_rad = math.radians(label_angle)
            label_x = center_x + (radius + 30) * math.cos(label_rad)
            label_y = center_y - (radius + 30) * math.sin(label_rad)

            svg += f'<text x="{label_x}" y="{label_y}" font-size="10" text-anchor="middle" alignment-baseline="middle" fill="#333">{category}</text>\n'
            svg += f'<text x="{label_x}" y="{label_y + 12}" font-size="9" text-anchor="middle" alignment-baseline="middle" fill="#666">{(volume/total)*100:.1f}%</text>\n'

            start_angle += angle

        svg += '</svg>'
        return svg

    def generate_all_charts(self, output_dir: str = "charts") -> List[str]:
        """
        生成所有图表

        Args:
            output_dir: 输出目录

        Returns:
            生成的文件路径列表
        """
        output_files = []

        # 生成贸易量趋势图
        trend_chart = self.generate_trade_volume_trend_chart(output_dir=output_dir, group_by='month')
        if 'output_path' in trend_chart:
            output_files.append(trend_chart['output_path'])

        # 生成贸易伙伴图
        partner_chart = self.generate_trade_partner_chart(output_dir=output_dir, chart_type='horizontal_bar')
        if 'output_path' in partner_chart:
            output_files.append(partner_chart['output_path'])

        # 生成商品类别图
        category_chart = self.generate_product_category_chart(output_dir=output_dir, chart_type='doughnut')
        if 'output_path' in category_chart:
            output_files.append(category_chart['output_path'])

        # 生成 HTML 报告
        html_report = self.generate_summary_report_html(output_dir=output_dir)
        output_files.append(html_report)

        return output_files


def create_report_workflow(
    input_path: str,
    column_mapping: Dict[str, str],
    history_db: str = "report_history.db",
    output_dir: str = "charts"
) -> Dict[str, Any]:
    """
    创建报表工作流：提取、存储、分析、生成图表

    Args:
        input_path: 输入文件路径
        column_mapping: 列映射配置
        history_db: 历史记录数据库路径
        output_dir: 图表输出目录

    Returns:
        工作流结果
    """
    from agents.table_extractor import TableExtractor

    # 1. 执行报表提取
    extractor = TableExtractor()
    result = extractor.extract_from_excel(input_path, column_mapping)

    # 2. 保存到历史记录
    history = ReportHistory(history_db)

    # 从提取结果中创建历史记录
    records = []
    for row in result.rows:
        record = {
            'source_file': result.source_file,
            'table_name': result.table_name,
            'extraction_time': result.extraction_time,
            'total_rows': result.total_rows,
            'matched_rows': result.matched_rows,
            'accuracy': result.accuracy,
            'trade_volume': float(row.extracted_values.get('贸易量', 0) or 0),
            'trade_partner': row.extracted_values.get('贸易伙伴', '') or row.extracted_values.get('国家', ''),
            'product_category': row.extracted_values.get('商品类别', '其他'),
            'country': row.extracted_values.get('国家', '') or row.extracted_values.get('贸易伙伴', ''),
            'value': float(row.extracted_values.get('贸易额', 0) or 0)
        }
        records.append(record)

    history.save_multiple_records(records)

    # 3. 生成图表
    chart_generator = ReportChartGenerator(history)
    output_files = chart_generator.generate_all_charts(output_dir=output_dir)

    return {
        'success': True,
        'extraction_result': {
            'total_rows': result.total_rows,
            'matched_rows': result.matched_rows,
            'accuracy': result.accuracy
        },
        'records_saved': len(records),
        'charts_generated': output_files,
        'statistics': history.get_statistics()
    }


if __name__ == "__main__":
    import tempfile
    import pandas as pd
    import os

    # 创建测试数据
    test_data = {
        "国家": ["美国", "中国", "日本", "德国", "法国", "英国", "加拿大", "澳大利亚", "韩国", "意大利"],
        "贸易量": [1500, 2300, 800, 1200, 950, 1100, 750, 600, 500, 850],
        "贸易额": [150000, 230000, 80000, 120000, 95000, 110000, 75000, 60000, 50000, 85000],
        "商品类别": ["电子产品", "机械设备", "化工产品", "纺织品", "农产品", "医药产品", "电子产品", "矿产资源", "机械设备", "化工产品"]
    }

    # 创建临时 Excel 文件
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
        test_file = f.name

    df = pd.DataFrame(test_data)
    df.to_excel(test_file, index=False)

    # 列映射（需要包含贸易量、贸易伙伴、商品类别等字段）
    column_mapping = {
        "国家": "国家",
        "贸易量": "贸易量",
        "贸易额": "贸易额",
        "商品类别": "商品类别"
    }

    # 执行工作流
    print("🚀 开始执行报表分析工作流...")
    result = create_report_workflow(
        input_path=test_file,
        column_mapping=column_mapping,
        history_db="report_history.db",
        output_dir="charts"
    )

    print(f"\n✅ 工作流完成！")
    print(f"📊 提取行数：{result['extraction_result']['total_rows']}")
    print(f"📊 匹配行数：{result['extraction_result']['matched_rows']}")
    print(f"📊 准确率：{result['extraction_result']['accuracy']:.2%}")
    print(f"💾 保存记录数：{result['records_saved']}")
    print(f"\n📈 生成的图表：")
    for chart in result['charts_generated']:
        print(f"  - {chart}")

    # 显示统计信息
    stats = result['statistics']
    print(f"\n📊 统计信息：")
    print(f"  - 总记录数：{stats['total_records']}")
    print(f"  - 总贸易量：{stats['total_trade_volume']:.1f}")
    print(f"  - 总贸易额：{stats['total_value']:.2f}")
    print(f"  - 平均准确率：{stats['avg_accuracy']:.2%}")

    # 清理测试文件
    os.remove(test_file)

    print(f"\n📄 打开 HTML 报告查看完整分析：charts/summary_report.html")
