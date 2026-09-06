#!/usr/bin/env python3
"""
海关报关智能生成系统 - CLI 入口
"""
import argparse
import sys
from pathlib import Path

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent import AgentCoordinator
from src.utils.config import Config
from src.utils.logger import setup_logger
from src.utils.cli_interface import RichCLI, show_version, console

logger = setup_logger("cli")


def process_file(file_path: str, output_dir: str = None, cli: RichCLI = None):
    """处理单个文件"""
    agent = AgentCoordinator()

    if output_dir:
        Config.set_output_dir(output_dir)

    def progress_callback(message: str):
        """进度回调"""
        if cli:
            cli.update_file_progress(current_task_id, message)

    if cli:
        current_task_id = cli.start_file_processing(file_path)
    else:
        current_task_id = None

    result = agent.process_file(file_path, progress_callback)

    if cli:
        cli.update_file_progress(current_task_id, "完成", 100)
        cli.finish_file_processing(current_task_id, result["success"])
        cli.show_file_result(file_path, result["success"], result)
    else:
        if result["success"]:
            print(f"\n✓ 处理成功！")
            print(f"  输出文件：{result['output_file']}")
        else:
            print(f"\n✗ 处理失败!")
            if result["errors"]:
                print("  错误:")
                for error in result["errors"]:
                    print(f"    - {error}")
        if result.get("warnings"):
            print(f"  警告：{len(result['warnings'])} 个")
        if result.get("ai_suggestion"):
            suggestion = result["ai_suggestion"][:150] + "..." if len(result["ai_suggestion"]) > 150 else result["ai_suggestion"]
            print(f"  AI 建议：{suggestion}")

    return result["success"]


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="海关报关智能生成系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 处理单个文件
  python cli.py --input data/sample.csv

  # 处理多个文件
  python cli.py --input data/file1.csv data/file2.csv

  # 自定义输出目录
  python cli.py --input data/sample.csv --output my_output/

  # 配置 Ollama 模型
  export OLLAMA_MODEL=qwen3.5:27b
  python cli.py --input data/sample.csv
        """
    )

    parser.add_argument(
        "--input", "-i",
        nargs="+",
        required=False,
        help="输入文件路径 (支持 CSV, XLSX, XLS)"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="输出目录 (默认：./output)"
    )
    parser.add_argument(
        "--config", "-c",
        default=None,
        help="配置文件路径"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细信息"
    )
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="打印当前配置"
    )
    parser.add_argument(
        "--batch", "-b",
        action="store_true",
        help="批量处理模式"
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="显示版本信息"
    )

    args = parser.parse_args()

    # 显示版本
    if args.version:
        show_version()
        return 0

    # 打印配置
    if args.print_config:
        if not args.input:
            Config.print_config()
            return 0

    # 设置日志级别
    if args.verbose:
        logger.setLevel("DEBUG")

    # 初始化 RichCLI
    cli = RichCLI(verbose=args.verbose)
    cli.show_header()

    if not args.input:
        parser.print_help()
        console.print("\n[yellow]提示:[/yellow] 请至少指定一个输入文件")
        return 1

    # 显示处理开始
    cli.show_processing_start(len(args.input))

    # 处理文件
    valid_files = []
    for file_path in args.input:
        path = Path(file_path)
        if not path.exists():
            console.print(f"[red]✗[/red] 文件不存在：[cyan]{file_path}[/cyan]")
            continue
        valid_files.append(str(path))

    if not valid_files:
        console.print("\n[red]没有有效的文件可处理[/red]")
        return 1

    for file_path in valid_files:
        process_file(file_path, args.output, cli)

    # 显示结果汇总
    cli.show_summary()
    cli.show_results_table()

    # 询问是否导出报告
    if cli.ask_export_report():
        report_path = Path(args.output or "./output") / "processing_report.txt"
        cli.export_report(str(report_path))

    return 0 if cli.stats["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
