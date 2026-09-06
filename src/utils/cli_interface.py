"""
CLI 交互界面模块 - 基于 rich 库增强 CLI 用户体验
"""
from pathlib import Path
from typing import Optional
from datetime import datetime

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm
from rich import box


# 创建全局 Console 实例
console = Console()


class RichCLI:
    """Rich CLI 界面管理器"""

    def __init__(self, verbose: bool = False):
        """
        初始化 RichCLI

        Args:
            verbose: 是否显示详细信息
        """
        self.verbose = verbose
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "warnings": 0,
        }
        self.results = []
        self.errors = []
        self.current_progress = None

    def show_header(self, title: str = "海关报关智能生成系统"):
        """显示应用标题"""
        console.print(Panel(
            f"[bold cyan]{title}[/bold cyan]\n[dim]智能处理 · 自动生成[/dim]",
            box=box.DOUBLE,
            padding=(1, 2)
        ))

    def show_processing_start(self, total_files: int):
        """显示处理开始"""
        self.stats["total"] = total_files
        console.print(f"\n[bold]即将处理 [cyan]{total_files}[/cyan] 个文件[/bold]\n")

    def start_file_processing(self, file_path: str):
        """开始处理单个文件"""
        filename = Path(file_path).name
        self.current_progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            TextColumn("[progress.percentage]{task.percentage:>3.1f}%"),
            console=console,
            transient=False
        )
        self.current_progress.start()
        task_id = self.current_progress.add_task(
            f"[cyan]处理：{filename}[/cyan]",
            total=100,
            description=f"处理：{filename}"
        )
        return task_id

    def update_file_progress(self, task_id: int, message: str, percentage: int = None):
        """更新文件处理进度"""
        if self.current_progress and task_id in self.current_progress.tasks:
            self.current_progress.update(
                task_id,
                description=f"[dim]{message}[/dim]",
                advance=percentage if percentage else 10
            )

    def finish_file_processing(self, task_id: int, success: bool):
        """完成文件处理"""
        if self.current_progress:
            self.current_progress.stop()
            if success:
                self.stats["success"] += 1
            else:
                self.stats["failed"] += 1

    def show_file_result(self, file_path: str, success: bool, result: dict):
        """显示单个文件处理结果"""
        filename = Path(file_path).name

        if success:
            console.print(f"\n[green]✓[/green] [bold]处理成功[/bold]: [cyan]{filename}[/cyan]")
            if result.get("output_file"):
                console.print(f"  [dim]输出文件:[/dim] {result['output_file']}")
        else:
            console.print(f"\n[red]✗[/red] [bold]处理失败[/bold]: [cyan]{filename}[/cyan]")
            if result.get("errors"):
                self._show_errors(result["errors"])

        # 记录结果
        self.results.append({
            "file": filename,
            "path": file_path,
            "success": success,
            "output_file": result.get("output_file"),
            "errors": result.get("errors", []),
            "warnings": result.get("warnings", []),
            "timestamp": datetime.now().isoformat()
        })

        # 更新警告统计
        if result.get("warnings"):
            warning_count = len(result["warnings"])
            self.stats["warnings"] += warning_count
            console.print(f"  [yellow]警告:[/yellow] {warning_count} 个")

        # 显示 AI 建议
        if result.get("ai_suggestion"):
            suggestion = result["ai_suggestion"][:150] + "..." if len(result["ai_suggestion"]) > 150 else result["ai_suggestion"]
            console.print(f"  [blue]AI 建议:[/blue] {suggestion}")

    def _show_errors(self, errors: list):
        """显示错误列表"""
        console.print("  [red]错误:[/red]")
        for i, error in enumerate(errors[:5], 1):
            console.print(f"    [dim]{i}.[/dim] {error}")
            self.errors.append(error)
        if len(errors) > 5:
            console.print(f"    [dim]... 还有 {len(errors) - 5} 个错误[/dim]")

    def show_summary(self):
        """显示处理摘要"""
        console.print("\n" + "=" * 60)

        # 创建统计表格
        summary_table = Table(
            title="处理结果统计",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta"
        )
        summary_table.add_column("指标", style="cyan")
        summary_table.add_column("数量", style="green", justify="right")

        summary_table.add_row("总文件数", str(self.stats["total"]))
        summary_table.add_row("处理成功", f"[green]{self.stats['success']}[/green]")
        summary_table.add_row("处理失败", f"[red]{self.stats['failed']}[/red]")
        summary_table.add_row("警告数量", f"[yellow]{self.stats['warnings']}[/yellow]")

        success_rate = (self.stats["success"] / self.stats["total"] * 100) if self.stats["total"] > 0 else 0
        summary_table.add_row("成功率", f"[bold]{success_rate:.1f}%[/bold]")

        console.print(summary_table)

        # 显示处理建议
        if self.stats["failed"] > 0:
            console.print(Panel(
                "[yellow]建议:[/yellow] 检查失败文件的格式和数据内容",
                border_style="yellow"
            ))

    def show_results_table(self):
        """显示处理结果表格"""
        if not self.results:
            return

        results_table = Table(
            title="文件处理详情",
            box=box.SIMPLE,
            show_header=True,
            header_style="bold white"
        )
        results_table.add_column("文件名", style="cyan")
        results_table.add_column("状态", style="green")
        results_table.add_column("输出文件", style="dim")

        for result in self.results:
            status = "[green]✓ 成功[/green]" if result["success"] else "[red]✗ 失败[/red]"
            output_file = Path(result.get("output_file", "")).name if result.get("output_file") else ""
            results_table.add_row(result["file"], status, output_file)

        console.print(results_table)

    def ask_export_report(self) -> bool:
        """询问是否导出详细报告"""
        if self.verbose:
            return Confirm.ask(
                "[bold]是否导出详细处理报告？[/bold]",
                default=False
            )
        return False

    def export_report(self, output_path: str):
        """导出详细处理报告"""
        try:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w", encoding="utf-8") as f:
                f.write("=" * 60 + "\n")
                f.write("海关报关智能生成系统 - 处理报告\n")
                f.write("=" * 60 + "\n\n")

                f.write(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                # 统计信息
                f.write("处理统计\n")
                f.write("-" * 40 + "\n")
                f.write(f"总文件数：{self.stats['total']}\n")
                f.write(f"处理成功：{self.stats['success']}\n")
                f.write(f"处理失败：{self.stats['failed']}\n")
                f.write(f"警告数量：{self.stats['warnings']}\n\n")

                # 文件详情
                f.write("文件处理详情\n")
                f.write("-" * 40 + "\n")
                for result in self.results:
                    status = "成功" if result["success"] else "失败"
                    f.write(f"\n文件：{result['file']}\n")
                    f.write(f"状态：{status}\n")
                    f.write(f"时间：{result['timestamp']}\n")
                    if result.get("output_file"):
                        f.write(f"输出：{result['output_file']}\n")
                    if result.get("errors"):
                        f.write("错误:\n")
                        for error in result["errors"]:
                            f.write(f"  - {error}\n")
                    if result.get("warnings"):
                        f.write("警告:\n")
                        for warning in result["warnings"]:
                            f.write(f"  - {warning}\n")

                console.print(f"[green]✓[/green] 报告已导出：[cyan]{output_path}[/cyan]")
                return True
        except Exception as e:
            console.print(f"[red]✗[/red] 导出报告失败：{e}")
            return False


def show_version():
    """显示版本信息"""
    from importlib.metadata import version, PackageNotFoundError

    try:
        ver = version("customs-agent")
    except PackageNotFoundError:
        ver = "0.1.0"

    console.print(Panel(
        f"[bold cyan]海关报关智能生成系统[/bold cyan]\n"
        f"版本：[yellow]{ver}[/yellow]\n"
        f"Python: [dim]{__import__('sys').version}[/dim]",
        box=box.DOUBLE,
        padding=(1, 2)
    ))
