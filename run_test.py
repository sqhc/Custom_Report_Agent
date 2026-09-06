#!/usr/bin/env python3
"""
运行测试脚本
"""
import sys
from pathlib import Path

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent import AgentCoordinator
from src.utils.config import Config

def run_test():
    """运行测试"""
    print("=" * 60)
    print("海关报关智能生成系统 - 测试")
    print("=" * 60)

    # 打印配置
    Config.print_config()

    # 创建测试数据
    test_file = PROJECT_ROOT / "tests" / "sample_data.csv"

    if not test_file.exists():
        print(f"错误：测试文件不存在：{test_file}")
        return False

    # 创建 Agent
    agent = AgentCoordinator()

    # 处理文件
    print(f"\n处理测试文件：{test_file}")
    print("-" * 60)

    def progress_callback(message: str):
        """进度回调"""
        print(f"  [{message}]")

    result = agent.process_file(str(test_file), progress_callback)

    # 打印结果
    print("\n" + "=" * 60)
    print("处理结果:")
    print("=" * 60)

    print(f"  成功：{result['success']}")
    print(f"  输出文件：{result.get('output_file', 'N/A')}")
    print(f"  错误数：{len(result['errors'])}")
    print(f"  警告数：{len(result['warnings'])}")

    if result["errors"]:
        print("\n  错误:")
        for error in result["errors"]:
            print(f"    - {error}")

    if result["warnings"]:
        print("\n  警告:")
        for warning in result["warnings"][:5]:
            print(f"    - {warning}")

    if result.get("ai_suggestion"):
        print("\n  AI 建议:")
        print(f"    {result['ai_suggestion']}")

    print("\n" + "=" * 60)

    return result["success"]


if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)
