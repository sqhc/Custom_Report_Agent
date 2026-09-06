"""
商品描述智能信息提取器

结合 text_chunker 实现长文本描述的 LLM 信息提取
"""
import json
import time
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from .llm_client import LLMClient, get_llm_client
from .text_chunker import DescriptionProcessor, TextChunker, process_description_with_llm


# 提取信息的系统提示词
EXTRACTION_SYSTEM_PROMPT = """你是一个专业的商品信息提取助手。请从商品描述中提取以下信息：

需要提取的字段：
1. hs_code - 海关编码（8-10 位数字）
2. product_name - 商品名称
3. brand - 品牌
4. material - 材质
5. color - 颜色
6. size - 尺寸/规格
7. packaging - 包装信息
8. origin - 原产国
9. weight - 重量
10. quantity - 数量
11. features - 商品特性（列表）

要求：
1. 只返回 JSON 格式，不要其他解释
2. 如果没有找到某个字段，该字段设为 null
3. 列表字段如果为空，使用空数组 []
4. 提取的信息必须是原文中明确提到的
5. 不要编造任何信息

JSON 格式示例：
{
    "hs_code": "1234567890",
    "product_name": "商品名称",
    "brand": "品牌名",
    "material": "材质",
    "color": "颜色",
    "size": "规格",
    "packaging": "包装",
    "origin": "原产国",
    "weight": "重量",
    "quantity": "数量",
    "features": ["特性 1", "特性 2"]
}"""


def extract_from_chunk(text: str, llm_client: LLMClient = None) -> Dict[str, Any]:
    """
    从单个文本块中提取商品信息

    Args:
        text: 文本块内容
        llm_client: LLM 客户端

    Returns:
        提取的商品信息字典
    """
    llm_client = llm_client or get_llm_client()

    # 构建提示词
    prompt = f"""请从以下商品描述中提取信息：

商品描述：
{text}

请按 JSON 格式返回提取的信息："""

    # 调用 LLM
    result = llm_client.call_with_retry(prompt, system=EXTRACTION_SYSTEM_PROMPT, require_json=True)

    if not result:
        return {}

    # 解析 JSON
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        # 尝试提取 JSON 部分
        import re
        match = re.search(r'\{[\s\S]*\}', result)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {}


def extract_from_description(description: str,
                             max_chunk_size: int = 2000,
                             overlap_ratio: float = 0.1,
                             llm_client: LLMClient = None) -> Dict[str, Any]:
    """
    从商品描述中提取信息（自动分块处理）

    Args:
        description: 商品描述文本
        max_chunk_size: 最大分块大小
        overlap_ratio: 重叠比例
        llm_client: LLM 客户端

    Returns:
        合并后的商品信息
    """
    processor = DescriptionProcessor(
        chunker=TextChunker(
            max_chunk_size=max_chunk_size,
            overlap_ratio=overlap_ratio
        )
    )

    def extract_callback(text: str, chunk_id: int) -> Dict[str, Any]:
        """提取回调"""
        return extract_from_chunk(text, llm_client)

    return processor.process_description(description, extract_callback)


def extract_in_batches(descriptions: List[str],
                       batch_size: int = 5,
                       max_chunk_size: int = 2000,
                       overlap_ratio: float = 0.1,
                       parallel: bool = False,
                       max_workers: int = 4) -> List[Dict[str, Any]]:
    """
    批量提取多个商品描述的信息

    Args:
        descriptions: 商品描述列表
        batch_size: 每批处理的描述数量
        max_chunk_size: 最大分块大小
        overlap_ratio: 重叠比例
        parallel: 是否使用并行处理
        max_workers: 并行处理的最大工作线程数

    Returns:
        每个描述对应的提取结果列表
    """
    if not descriptions:
        return []

    if parallel:
        return _extract_parallel(
            descriptions=descriptions,
            max_chunk_size=max_chunk_size,
            overlap_ratio=overlap_ratio,
            max_workers=max_workers
        )
    else:
        return _extract_sequential(
            descriptions=descriptions,
            batch_size=batch_size,
            max_chunk_size=max_chunk_size,
            overlap_ratio=overlap_ratio
        )


def _extract_sequential(descriptions: List[str],
                        batch_size: int,
                        max_chunk_size: int,
                        overlap_ratio: float) -> List[Dict[str, Any]]:
    """
    顺序处理多个商品描述

    Args:
        descriptions: 商品描述列表
        batch_size: 每批处理的描述数量
        max_chunk_size: 最大分块大小
        overlap_ratio: 重叠比例

    Returns:
        提取结果列表
    """
    results = []

    for i in range(0, len(descriptions), batch_size):
        batch = descriptions[i:i + batch_size]

        for desc in batch:
            result = extract_from_description(
                description=desc,
                max_chunk_size=max_chunk_size,
                overlap_ratio=overlap_ratio
            )
            results.append(result)

        # 批次处理间隔（避免 API 限流）
        if i + batch_size < len(descriptions):
            time.sleep(1)

    return results


def _extract_parallel(descriptions: List[str],
                      max_chunk_size: int,
                      overlap_ratio: float,
                      max_workers: int) -> List[Dict[str, Any]]:
    """
    并行处理多个商品描述

    Args:
        descriptions: 商品描述列表
        max_chunk_size: 最大分块大小
        overlap_ratio: 重叠比例
        max_workers: 最大工作线程数

    Returns:
        提取结果列表（保持原始顺序）
    """
    results = [None] * len(descriptions)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(
                extract_from_description,
                description=desc,
                max_chunk_size=max_chunk_size,
                overlap_ratio=overlap_ratio
            ): idx
            for idx, desc in enumerate(descriptions)
        }

        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                print(f"Error processing description {idx}: {e}")
                results[idx] = {}

    return results


# 测试代码
if __name__ == "__main__":
    # 示例长描述
    long_description = """
    这款高品质的专业级不锈钢厨房刀具套装，由德国知名品牌 ZWILLING 双立人出品。
    全套包含 15 件刀具，采用德国进口 X50CrMoV15 高级不锈钢材质，经过 1500 次热处理工艺，
    硬度达到 57 度 HRC，刀刃锋利持久，不易生锈。

    刀具规格如下：
    - 主厨刀：20 厘米（8 英寸），刀身宽度 4.5 厘米
    - 面包刀：25 厘米（10 英寸），锯齿刀刃设计
    - 桑刀：15 厘米（6 英寸），适合处理小型食材
    - 剔骨刀：13 厘米（5 英寸），刀尖灵活
    - 水果刀：9 厘米（3.5 英寸），便携设计
    - 削皮刀：7 厘米（2.8 英寸）
    - 厨房剪：19 厘米
    - 剪刀配件：剪骨刀头、剪刀清洁刷

    所有刀具手柄采用黑色 synthetic 合成材料，符合人体工学设计，握持舒适防滑。
    包装盒为高档木制刀座，可容纳全部刀具，便于收纳和展示。

    原产地：德国 Solingen 索林根，世界闻名的刀具制造之都。
    总重量：约 2.5 千克。

    产品特性：
    1. 终身保修服务
    2. 专业级品质，适合家庭和专业厨房使用
    3. 易于清洁维护，可用洗碗机清洗
    4. 符合 FDA 食品接触安全标准
    5. 获得红点设计奖认证

    海关编码：8211.92.00
    品牌：ZWILLING 双立人
    型号：TWIN Signature 系列
    产地：德国
    包装：原木刀座盒装
    数量：1 套（15 件）
    重量：2.5kg
    """

    # 测试分块
    print("=" * 50)
    print("测试 1: 文本分块")
    print("=" * 50)
    from .text_chunker import split_description

    chunks = split_description(long_description, max_chunk_size=800, overlap_ratio=0.1)
    for chunk in chunks:
        print(f"\n块 {chunk['chunk_id']}:")
        print(f"  内容长度：{len(chunk['content'])} 字符")
        print(f"  起始位置：{chunk['start_index']}")
        print(f"  结束位置：{chunk['end_index']}")
        print(f"  前缀重叠：{len(chunk['with_context']) - len(chunk['content']) - len(long_description[chunk['end_index']:chunk['end_index']+50]) if 'with_context' in chunk else 0}")
        print(f"  内容预览：{chunk['content'][:100]}...")

    # 测试信息提取（实际调用 LLM）
    print("\n" + "=" * 50)
    print("测试 2: 信息提取（需要 LLM）")
    print("=" * 50)

    try:
        result = extract_from_description(long_description)
        print("\n提取结果:")
        for key, value in result.items():
            print(f"  {key}: {value}")
    except Exception as e:
        print(f"提取失败：{e}")
        print("请确保 Ollama 服务已启动")

    # 测试批量处理（并行 vs 顺序）
    print("\n" + "=" * 50)
    print("测试 3: 批量处理（需要 LLM）")
    print("=" * 50)

    test_descriptions = [long_description] * 3  # 使用 3 个相同的描述测试

    try:
        # 顺序处理
        print("\n顺序处理...")
        import time
        start = time.time()
        seq_results = extract_in_batches(
            descriptions=test_descriptions,
            batch_size=2,
            parallel=False
        )
        seq_time = time.time() - start
        print(f"顺序处理耗时：{seq_time:.2f} 秒")

        # 并行处理
        print("\n并行处理...")
        start = time.time()
        parallel_results = extract_in_batches(
            descriptions=test_descriptions,
            parallel=True,
            max_workers=3
        )
        parallel_time = time.time() - start
        print(f"并行处理耗时：{parallel_time:.2f} 秒")

        print(f"\n加速比：{seq_time / parallel_time:.2f}x")
    except Exception as e:
        print(f"批量处理失败：{e}")
        print("请确保 Ollama 服务已启动")
