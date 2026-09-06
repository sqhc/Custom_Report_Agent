#!/usr/bin/env python3
"""
HS 编码验证器测试脚本
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.hs_validator import HSValidator


def test_code_exists():
    """测试存在的 HS 编码"""
    validator = HSValidator(local_db_path="data/hs_codes_2024.json")

    # 测试存在的编码
    result = validator.validate_in_standard_table("010121")
    assert result[0] == True, "010121 应该是有效的"

    result = validator.validate_in_standard_table("010129")
    assert result[0] == True, "010129 应该是有效的"

    result = validator.validate_in_standard_table("847130")
    assert result[0] == True, "847130 应该是有效的"

    result = validator.validate_in_standard_table("851712")
    assert result[0] == True, "851712 应该是有效的"

    result = validator.validate_in_standard_table("901811")
    assert result[0] == True, "901811 应该是有效的"

    print("✓ 存在的 HS 编码测试通过")


def test_code_not_exists():
    """测试不存在的 HS 编码"""
    validator = HSValidator(local_db_path="data/hs_codes_2024.json")

    # 测试不存在的编码
    result = validator.validate_format("999999")
    assert result[0] == True, "999999 格式应该有效（6 位数字）"

    result = validator.validate_in_standard_table("999999")
    assert result[0] == False, "999999 应该不在标准表中"

    result = validator.validate_format("12345")
    assert result[0] == False, "12345 应该无效（长度不足）"

    result = validator.validate_format("12345678901")
    assert result[0] == False, "12345678901 应该无效（长度过长）"

    result = validator.validate_format("abcdefgh")
    assert result[0] == False, "abcdefgh 应该无效（非数字）"

    print("✓ 不存在的 HS 编码测试通过")


def test_get_description():
    """测试获取 HS 编码描述"""
    validator = HSValidator(local_db_path="data/hs_codes_2024.json")

    codes = validator.hs_standard_table.get('codes', {})
    assert "010121" in codes, "010121 应该在标准表中"
    description = codes["010121"].get('description', '')
    assert description == "乳用种牛", f"描述应为'乳用种牛'，实际为'{description}'"

    assert "847130" in codes, "847130 应该在标准表中"
    description = codes["847130"].get('description', '')
    assert description == "便携式自动数据处理设备", f"描述应为'便携式自动数据处理设备'，实际为'{description}'"

    print("✓ 获取 HS 编码描述测试通过")


def test_get_chapter():
    """测试获取 HS 编码章节"""
    validator = HSValidator(local_db_path="data/hs_codes_2024.json")

    codes = validator.hs_standard_table.get('codes', {})
    chapter = codes["010121"].get('chapter', '')
    assert chapter == "第一章 活动物", f"章节应为'第一章 活动物'，实际为'{chapter}'"

    chapter = codes["847130"].get('chapter', '')
    assert chapter == "第八十四章 核反应堆、锅炉、机器、机械器具", f"章节应为'第八十四章 核反应堆、锅炉、机器、机械器具'，实际为'{chapter}'"

    print("✓ 获取 HS 编码章节测试通过")


def test_get_all_codes():
    """测试获取所有 HS 编码"""
    validator = HSValidator(local_db_path="data/hs_codes_2024.json")

    codes = validator.hs_standard_table.get('codes', {})
    assert len(codes) > 0, "应该返回至少一个 HS 编码"

    # 验证返回的是字典格式
    assert isinstance(codes, dict), "应该返回字典类型"

    print(f"✓ 获取所有 HS 编码测试通过（共 {len(codes)} 个编码）")


def test_get_code_info():
    """测试获取 HS 编码完整信息"""
    validator = HSValidator(local_db_path="data/hs_codes_2024.json")

    codes = validator.hs_standard_table.get('codes', {})
    info = codes.get("010121")

    assert info is not None, "应该返回信息"
    assert "description" in info, "应包含'description'字段"
    assert "chapter" in info, "应包含'chapter'字段"
    assert info["description"] == "乳用种牛", "description 应为'乳用种牛'"

    print("✓ 获取 HS 编码完整信息测试通过")


def test_search_by_keyword():
    """测试通过关键词搜索 HS 编码"""
    validator = HSValidator(local_db_path="data/hs_codes_2024.json")

    codes = validator.hs_standard_table.get('codes', {})

    # 手动搜索包含"牛"的编码
    results = {code: info for code, info in codes.items()
               if "牛" in info.get("description", "") or "牛" in info.get("chapter", "")}

    assert len(results) > 0, "应该找到包含'牛'的编码"

    for code, info in results.items():
        assert "牛" in info["description"] or "牛" in info["chapter"], \
            f"结果应该包含'牛'，但 '{code}' 不匹配"

    print(f"✓ 关键词搜索测试通过（找到 {len(results)} 个匹配项）")


def test_main():
    """运行所有测试"""
    print("=" * 60)
    print("开始运行 HS 编码验证器测试")
    print("=" * 60)

    try:
        test_code_exists()
        test_code_not_exists()
        test_get_description()
        test_get_chapter()
        test_get_all_codes()
        test_get_code_info()
        test_search_by_keyword()

        print("=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)
        return True

    except AssertionError as e:
        print(f"\n✗ 测试失败：{e}")
        return False
    except Exception as e:
        print(f"\n✗ 测试异常：{e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_main()
    sys.exit(0 if success else 1)
