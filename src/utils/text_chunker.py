"""
商品描述智能分块处理工具

支持：
1. 语义分割（按标点符号，保持语义完整）
2. 重叠上下文（保留前后文连贯性）
3. 逐块 LLM 处理
4. 结果合并去重
"""
import re
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass


@dataclass
class TextChunk:
    """文本块"""
    content: str
    start_index: int
    end_index: int
    chunk_id: int
    overlap_prefix: str = ""  # 前一块的重叠部分
    overlap_suffix: str = ""  # 后一块的重叠部分


class TextChunker:
    """智能文本分块器"""

    # 中文和英文标点符号分隔符
    SENTENCE_SPLITTERS = re.compile(
        r'[.。！？!?.?]+|'  # 句号/问号/感叹号
        r'\n+|'  # 换行
        r'[;；]+|'  # 分号
        r'[,，]+'  # 逗号
    )

    # 最小分块大小（避免过小的块）
    MIN_CHUNK_SIZE = 100

    # 默认最大分块大小
    DEFAULT_MAX_CHUNK_SIZE = 2000

    # 默认重叠比例
    DEFAULT_OVERLAP_RATIO = 0.1

    def __init__(self,
                 max_chunk_size: int = DEFAULT_MAX_CHUNK_SIZE,
                 overlap_ratio: float = DEFAULT_OVERLAP_RATIO,
                 min_chunk_size: int = MIN_CHUNK_SIZE):
        """
        初始化分块器

        Args:
            max_chunk_size: 最大分块大小
            overlap_ratio: 重叠比例（0.1 表示 10% 重叠）
            min_chunk_size: 最小分块大小
        """
        self.max_chunk_size = max_chunk_size
        self.overlap_ratio = overlap_ratio
        self.min_chunk_size = min_chunk_size

    def split_text(self, text: str) -> List[TextChunk]:
        """
        智能分割文本

        Args:
            text: 待分割的文本

        Returns:
            TextChunk 列表
        """
        if not text or not text.strip():
            return []

        # 如果文本长度小于最大分块大小，直接返回单个块
        if len(text) <= self.max_chunk_size:
            return [TextChunk(
                content=text,
                start_index=0,
                end_index=len(text),
                chunk_id=0
            )]

        # 按标点符号分割句子
        sentences = self._split_into_sentences(text)

        # 合并句子成分块
        chunks = self._merge_sentences_into_chunks(sentences, text)

        # 添加重叠上下文
        chunks = self._add_overlap(chunks)

        return chunks

    def _split_into_sentences(self, text: str) -> List[Tuple[str, int, int]]:
        """
        将文本分割成句子

        Returns:
            (句子内容，起始位置，结束位置) 列表
        """
        sentences = []
        current_pos = 0

        for match in self.SENTENCE_SPLITTERS.finditer(text):
            # 提取匹配前的句子内容
            sentence = text[current_pos:match.start()].strip()

            if sentence:
                sentences.append((sentence, current_pos, match.start()))

            # 提取分隔符
            separator = match.group().strip()
            if separator:
                sentences.append((separator, match.start(), match.end()))

            current_pos = match.end()

        # 添加最后一个句子
        if current_pos < len(text):
            remaining = text[current_pos:].strip()
            if remaining:
                sentences.append((remaining, current_pos, len(text)))

        return sentences

    def _merge_sentences_into_chunks(self,
                                     sentences: List[Tuple[str, int, int]],
                                     original_text: str) -> List[TextChunk]:
        """
        合并句子成分块，确保每个块不超过最大大小

        Args:
            sentences: 句子列表
            original_text: 原始文本（用于索引定位）

        Returns:
            TextChunk 列表
        """
        chunks = []
        current_chunk = []
        current_length = 0
        chunk_start = 0

        for sentence, start, end in sentences:
            sentence_len = len(sentence)

            # 如果添加这个句子会超过最大长度
            if current_length + sentence_len > self.max_chunk_size:
                # 保存当前块
                if current_chunk:
                    chunk_text = ''.join(current_chunk).strip()
                    if len(chunk_text) >= self.min_chunk_size:
                        chunks.append(TextChunk(
                            content=chunk_text,
                            start_index=chunk_start,
                            end_index=start,
                            chunk_id=len(chunks)
                        ))

                    # 开始新块
                    current_chunk = [sentence]
                    current_length = sentence_len
                    chunk_start = start
                else:
                    # 如果当前块为空，直接添加
                    current_chunk = [sentence]
                    current_length = sentence_len
                    chunk_start = start
            else:
                # 添加到当前块
                current_chunk.append(sentence)
                current_length += sentence_len

        # 添加最后一个块
        if current_chunk:
            chunk_text = ''.join(current_chunk).strip()
            if len(chunk_text) >= self.min_chunk_size:
                chunks.append(TextChunk(
                    content=chunk_text,
                    start_index=chunk_start,
                    end_index=len(original_text),
                    chunk_id=len(chunks)
                ))

        return chunks

    def _add_overlap(self, chunks: List[TextChunk]) -> List[TextChunk]:
        """
        为每个块添加重叠上下文

        Args:
            chunks: 分块列表

        Returns:
            添加重叠后的分块列表
        """
        if len(chunks) <= 1:
            return chunks

        overlap_size = int(self.max_chunk_size * self.overlap_ratio)
        result = []

        for i, chunk in enumerate(chunks):
            new_chunk = TextChunk(
                content=chunk.content,
                start_index=chunk.start_index,
                end_index=chunk.end_index,
                chunk_id=chunk.chunk_id,
                overlap_prefix="",
                overlap_suffix=""
            )

            # 添加前缀重叠（从上一块末尾）
            if i > 0:
                prev_chunk = chunks[i - 1]
                overlap_start = max(0, len(prev_chunk.content) - overlap_size)
                new_chunk.overlap_prefix = prev_chunk.content[overlap_start:]

            # 添加后缀重叠（从下一块开头）
            if i < len(chunks) - 1:
                next_chunk = chunks[i + 1]
                new_chunk.overlap_suffix = next_chunk.content[:overlap_size]

            result.append(new_chunk)

        return result

    def get_chunk_with_context(self, chunk: TextChunk) -> str:
        """
        获取包含上下文的完整块内容

        Args:
            chunk: 文本块

        Returns:
            包含前后重叠的完整文本
        """
        return f"{chunk.overlap_prefix}{chunk.content}{chunk.overlap_suffix}"


class DescriptionProcessor:
    """商品描述处理器"""

    def __init__(self,
                 chunker: TextChunker = None,
                 max_chunks: int = 10):
        """
        初始化描述处理器

        Args:
            chunker: 文本分块器
            max_chunks: 最大分块数量（防止过长的描述）
        """
        self.chunker = chunker or TextChunker()
        self.max_chunks = max_chunks

    def process_description(self,
                           description: str,
                           extract_callback: Callable[[str, int], Dict[str, Any]]) -> Dict[str, Any]:
        """
        处理商品描述

        Args:
            description: 商品描述文本
            extract_callback: 提取信息的回调函数，参数为 (文本块，块 ID)

        Returns:
            合并后的提取结果
        """
        if not description or not description.strip():
            return {}

        # 分块
        chunks = self.chunker.split_text(description)

        # 限制最大分块数量
        if len(chunks) > self.max_chunks:
            # 调整分块大小，减少块数量
            new_max_size = int(self.chunker.max_chunk_size * len(chunks) / self.max_chunks)
            adjusted_chunker = TextChunker(
                max_chunk_size=new_max_size,
                overlap_ratio=self.chunker.overlap_ratio
            )
            chunks = adjusted_chunker.split_text(description)[:self.max_chunks]

        if not chunks:
            return {}

        # 逐块处理
        results = []
        for chunk in chunks:
            # 获取包含上下文的完整块
            full_text = self.chunker.get_chunk_with_context(chunk)

            # 调用回调函数提取信息
            result = extract_callback(full_text, chunk.chunk_id)
            results.append({
                'chunk_id': chunk.chunk_id,
                'content': chunk.content,
                'result': result
            })

        # 合并结果
        merged_result = self._merge_results(results)

        return merged_result

    def _merge_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        合并多个块的处理结果

        Args:
            results: 各块的处理结果列表

        Returns:
            合并后的结果
        """
        if not results:
            return {}

        merged = {}

        # 收集所有提取的字段
        for result in results:
            chunk_result = result.get('result', {})
            for key, value in chunk_result.items():
                if key not in merged:
                    merged[key] = []

                # 添加到列表（后续去重）
                if isinstance(value, list):
                    merged[key].extend(value)
                else:
                    merged[key].append(value)

        # 去重和合并
        for key in merged:
            values = merged[key]

            # 如果是列表，去重
            if isinstance(values, list):
                unique_values = []
                seen = set()
                for v in values:
                    v_key = str(v).lower().strip()
                    if v_key and v_key not in seen:
                        seen.add(v_key)
                        unique_values.append(v)
                merged[key] = unique_values if len(unique_values) > 1 else (unique_values[0] if unique_values else None)
            else:
                # 非列表类型，取第一个非空值
                merged[key] = next((v for v in [values] if v), None)

        # 清理 None 值
        merged = {k: v for k, v in merged.items() if v is not None}

        return merged


def split_description(description: str,
                     max_chunk_size: int = 2000,
                     overlap_ratio: float = 0.1) -> List[Dict[str, Any]]:
    """
    便捷函数：分割商品描述

    Args:
        description: 商品描述文本
        max_chunk_size: 最大分块大小
        overlap_ratio: 重叠比例

    Returns:
        分块信息列表
    """
    chunker = TextChunker(
        max_chunk_size=max_chunk_size,
        overlap_ratio=overlap_ratio
    )

    chunks = chunker.split_text(description)

    return [{
        'chunk_id': chunk.chunk_id,
        'content': chunk.content,
        'with_context': chunker.get_chunk_with_context(chunk),
        'start_index': chunk.start_index,
        'end_index': chunk.end_index
    } for chunk in chunks]


def process_description_with_llm(description: str,
                                 llm_callback: Callable[[str], Dict[str, Any]],
                                 max_chunk_size: int = 2000,
                                 overlap_ratio: float = 0.1) -> Dict[str, Any]:
    """
    便捷函数：使用 LLM 处理商品描述

    Args:
        description: 商品描述文本
        llm_callback: LLM 调用回调函数
        max_chunk_size: 最大分块大小
        overlap_ratio: 重叠比例

    Returns:
        合并后的提取结果
    """
    processor = DescriptionProcessor(
        chunker=TextChunker(max_chunk_size=max_chunk_size, overlap_ratio=overlap_ratio)
    )

    def extract_callback(text: str, chunk_id: int) -> Dict[str, Any]:
        """提取回调"""
        return llm_callback(text)

    return processor.process_description(description, extract_callback)
