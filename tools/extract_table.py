#!/usr/bin/env python3
"""表格提取 CLI 工具 - 提取报表数据并生成 HTML 对比视图"""

import argparse
import json
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.table_extractor import TableExtractor, create_extraction_workflow


def main():
    parser = argparse.ArgumentParser(
        description="表格提取工具 - 支持 PDF/Excel/Word/网页报表",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # Excel 报表提取
  python tools/extract_table.py --input data/report.xlsx --mapping '{"name":"姓名","age":"年龄","city":"城市"}'

  # PDF 报表提取
  python tools/extract_table.py --input report.pdf --mapping '{"column1":"列 1","column2":"列 2"}'

  # 网页表格提取
  python tools/extract_table.py --input https://example.com/table --mapping '{"col":"column"}'

  # 使用 JSON 配置文件
  python tools/extract_table.py --config extraction_config.json
        """
    )

    parser.add_argument("--input", "-i", type=str, help="输入文件路径或 URL")
    parser.add_argument("--output", "-o", type=str, default="output", help="输出目录 (默认：output)")
    parser.add_argument("--mapping", "-m", type=str, help="列映射 JSON，格式：{\"列名\":\"提取规则\"}")
    parser.add_argument("--config", "-c", type=str, help="配置文件路径 (JSON 格式)")
    parser.add_argument("--max-rows", type=int, default=100, help="HTML 中显示的最大行数 (默认：100)")
    parser.add_argument("--open", action="store_true", help="生成后自动打开 HTML 文件")
    parser.add_argument("--quiet", "-q", action="store_true", help="静默模式，仅输出 JSON 结果")

    args = parser.parse_args()

    # 使用配置文件
    if args.config:
        if not os.path.exists(args.config):
            print(f"错误：配置文件不存在：{args.config}")
            sys.exit(1)

        with open(args.config, 'r', encoding='utf-8') as f:
            config = json.load(f)

        input_path = config.get("input")
        column_mapping = config.get("column_mapping", {})
        output_dir = config.get("output_dir", args.output)
        file_type = config.get("file_type")
        max_rows = config.get("max_rows", args.max_rows)
    else:
        if not args.input:
            parser.error("--input 或 --config 参数必选")

        input_path = args.input
        column_mapping = json.loads(args.mapping) if args.mapping else {}
        output_dir = args.output
        file_type = None
        max_rows = args.max_rows

    try:
        # 执行提取
        result = create_extraction_workflow(
            input_path=input_path,
            column_mapping=column_mapping,
            output_dir=output_dir,
            file_type=file_type
        )

        # 输出结果
        if args.quiet:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("\n" + "=" * 60)
            print("📊 表格提取完成")
            print("=" * 60)
            print(f"📁 源文件：{input_path}")
            print(f"📊 总行数：{result['total_rows']}")
            print(f"✅ 匹配行数：{result['matched_rows']}")
            print(f"🎯 准确率：{result['accuracy']:.2%}")
            print(f"📄 HTML 对比视图：{result['html_path']}")
            print("=" * 60 + "\n")

            # 自动打开 HTML
            if args.open and result.get("html_path"):
                try:
                    os.system(f"open {result['html_path']}")
                except Exception as e:
                    print(f"无法自动打开文件：{e}")

        sys.exit(0 if result.get("success") else 1)

    except Exception as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
