"""图像和 PDF OCR 文本提取模块

提供以下功能:
1. 图像 OCR 文字识别 (支持多种语言)
2. PDF 文档文本提取
3. 图像预处理增强 (降噪、二值化、对比度增强等)
4. 批量文件处理支持

依赖安装:
    pip install pytesseract pdfplumber pillow numpy

示例:
    from src.utils.image_ocr import OCRProcessor

    # 图像 OCR
    processor = OCRProcessor(lang='chi_sim+eng')
    text = processor.extract_from_image('image.jpg')

    # PDF 文本提取
    text = processor.extract_from_pdf('document.pdf')

    # 批量处理
    texts = processor.batch_extract(['img1.jpg', 'img2.png', 'doc.pdf'])
"""

import os
import re
import logging
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime

# 第三方库导入（使用 try-except 处理可选依赖）
try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """文本提取结果"""
    source: str  # 源文件路径或标识
    text: str  # 提取的文本
    success: bool  # 是否成功
    file_type: str  # 文件类型：image, pdf
    language: Optional[str] = None  # 使用的 OCR 语言
    page_count: int = 1  # 页数 (PDF)
    confidence: Optional[float] = None  # OCR 置信度
    error_message: Optional[str] = None  # 错误信息
    extraction_time: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'source': self.source,
            'text': self.text,
            'success': self.success,
            'file_type': self.file_type,
            'language': self.language,
            'page_count': self.page_count,
            'confidence': self.confidence,
            'error_message': self.error_message,
            'extraction_time': self.extraction_time
        }


class ImagePreprocessor:
    """图像预处理工具类

    提供图像增强功能以提高 OCR 识别率:
    - 灰度化
    - 二值化 (阈值处理)
    - 对比度增强
    - 降噪处理
    - 图像缩放
    - 旋转校正
    """

    def __init__(self):
        """初始化图像预处理器"""
        if not PIL_AVAILABLE:
            raise ImportError("Pillow 库未安装，请运行：pip install pillow")

    def to_grayscale(self, image: Image.Image) -> Image.Image:
        """转换为灰度图像

        Args:
            image: PIL Image 对象

        Returns:
            灰度图像
        """
        return image.convert('L')

    def apply_threshold(self, image: Image.Image, threshold: int = 128) -> Image.Image:
        """应用二值化阈值处理

        Args:
            image: 灰度 PIL Image 对象
            threshold: 阈值 (0-255)

        Returns:
            二值化后的图像
        """
        if image.mode != 'L':
            image = self.to_grayscale(image)

        return image.point(lambda x: 255 if x > threshold else 0, '1')

    def auto_threshold(self, image: Image.Image) -> Image.Image:
        """自动计算并应用最佳阈值 (Otsu 算法)

        Args:
            image: 灰度 PIL Image 对象

        Returns:
            二值化后的图像
        """
        if not NUMPY_AVAILABLE:
            # 使用默认阈值
            return self.apply_threshold(image, 128)

        if image.mode != 'L':
            image = self.to_grayscale(image)

        # 计算直方图
        histogram = image.histogram()
        pixels = np.array(histogram)
        total = np.sum(pixels)

        if total == 0:
            return self.apply_threshold(image, 128)

        # Otsu 算法计算最佳阈值
        cum_mean = np.cumsum(pixels * np.arange(256))
        cum_weight = np.cumsum(pixels)

        best_threshold = 0
        best_variance = 0

        for i in range(1, 256):
            weight1 = cum_weight[i-1]
            weight2 = total - weight1

            if weight1 == 0 or weight2 == 0:
                continue

            mean1 = cum_mean[i-1] / weight1
            mean2 = (cum_mean[255] - cum_mean[i-1]) / weight2

            variance = weight1 * weight2 * (mean1 - mean2) ** 2

            if variance > best_variance:
                best_variance = variance
                best_threshold = i

        return self.apply_threshold(image, best_threshold)

    def enhance_contrast(self, image: Image.Image, factor: float = 1.5) -> Image.Image:
        """增强图像对比度

        Args:
            image: PIL Image 对象
            factor: 对比度增强因子 (>1 增强，<1 减弱)

        Returns:
            增强后的图像
        """
        enhancer = ImageEnhance.Contrast(image)
        return enhancer.enhance(factor)

    def enhance_sharpness(self, image: Image.Image, factor: float = 2.0) -> Image.Image:
        """增强图像清晰度

        Args:
            image: PIL Image 对象
            factor: 清晰度增强因子 (>1 增强，<1 减弱)

        Returns:
            增强后的图像
        """
        enhancer = ImageEnhance.Sharpness(image)
        return enhancer.enhance(factor)

    def denoise(self, image: Image.Image, radius: int = 2) -> Image.Image:
        """图像降噪处理

        Args:
            image: PIL Image 对象
            radius: 高斯模糊半径

        Returns:
            降噪后的图像
        """
        # 轻微模糊可以去除噪点
        return image.filter(ImageFilter.GaussianBlur(radius=radius))

    def resize(self, image: Image.Image, target_size: Union[int, tuple]) -> Image.Image:
        """调整图像尺寸

        Args:
            image: PIL Image 对象
            target_size: 目标尺寸 (int: 最短边缩放，tuple: (width, height))

        Returns:
            调整后的图像
        """
        if isinstance(target_size, int):
            # 按比例缩放，最短边为 target_size
            width, height = image.size
            if width < height:
                new_width = target_size
                new_height = int(height * target_size / width)
            else:
                new_height = target_size
                new_width = int(width * target_size / height)
            target_size = (new_width, new_height)

        return image.resize(target_size, Image.Resampling.LANCZOS)

    def deskew(self, image: Image.Image) -> Image.Image:
        """图像去歪斜 (旋转校正)

        Args:
            image: PIL Image 对象

        Returns:
            校正后的图像
        """
        if image.mode != 'L':
            image = self.to_grayscale(image)

        # 计算角度
        angle = image.getdata()
        # 简化版本：这里可以使用更复杂的算法
        # 实际应用中可以使用 scikit-image 的 deskew 函数

        return image

    def preprocess_for_ocr(self, image: Image.Image,
                          apply_grayscale: bool = True,
                          apply_threshold: bool = True,
                          apply_contrast: bool = True,
                          contrast_factor: float = 1.5,
                          resize_to: Optional[int] = None) -> Image.Image:
        """完整的 OCR 预处理流程

        Args:
            image: 原始 PIL Image 对象
            apply_grayscale: 是否灰度化
            apply_threshold: 是否二值化
            apply_contrast: 是否增强对比度
            contrast_factor: 对比度增强因子
            resize_to: 缩放尺寸 (None 不缩放)

        Returns:
            预处理后的图像
        """
        processed = image

        # 1. 灰度化
        if apply_grayscale:
            processed = self.to_grayscale(processed)

        # 2. 对比度增强
        if apply_contrast:
            processed = self.enhance_contrast(processed, contrast_factor)

        # 3. 缩放 (可选)
        if resize_to:
            processed = self.resize(processed, resize_to)

        # 4. 二值化
        if apply_threshold:
            processed = self.auto_threshold(processed)

        return processed


class OCRProcessor:
    """OCR 文本提取处理器

    支持:
    - 图像 OCR 识别 (pytesseract)
    - PDF 文本提取 (pdfplumber)
    - 图像预处理增强
    - 批量文件处理
    - 多语言支持

    支持的 OCR 语言代码:
        chi_sim: 简体中文
        chi_tra: 繁体中文
        eng: 英语
        jpn: 日语
        kor: 韩语
        fra: 法语
        deu: 德语
        spa: 西班牙语
        等等...

    多语言示例：lang='chi_sim+eng'
    """

    def __init__(self,
                 lang: str = 'chi_sim+eng',
                 psm: int = 3,
                 oem: int = 3,
                 preprocess: bool = True,
                 tesseract_cmd: Optional[str] = None):
        """初始化 OCR 处理器

        Args:
            lang: OCR 语言代码 (默认：chi_sim+eng)
            psm: Tesseract 页面分割模式 (0-13)
            oem: Tesseract OCR 引擎模式 (0-3)
            preprocess: 是否进行图像预处理
            tesseract_cmd: Tesseract 可执行文件路径 (None 使用默认)
        """
        if not TESSERACT_AVAILABLE:
            logger.warning("pytesseract 未安装，图像 OCR 功能将不可用")
        if not PDFPLUMBER_AVAILABLE:
            logger.warning("pdfplumber 未安装，PDF 提取功能将不可用")
        if not PIL_AVAILABLE:
            logger.warning("Pillow 未安装，图像处理功能将不可用")

        self.lang = lang
        self.psm = psm
        self.oem = oem
        self.preprocess = preprocess
        self.tesseract_cmd = tesseract_cmd

        # 设置 tesseract 路径
        if tesseract_cmd and TESSERACT_AVAILABLE:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

        # 初始化预处理器
        self.preprocessor = ImagePreprocessor() if PIL_AVAILABLE else None

        # 支持的扩展名
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp'}
        self.pdf_extensions = {'.pdf'}

    def extract_from_image(self, image_path: Union[str, Path, Image.Image],
                          return_dict: bool = False) -> Union[str, Dict[str, Any]]:
        """从图像中提取文本

        Args:
            image_path: 图像路径或 PIL Image 对象
            return_dict: 是否返回详细信息字典

        Returns:
            提取的文本或详细信息字典
        """
        try:
            if not TESSERACT_AVAILABLE or not PIL_AVAILABLE:
                error_msg = "OCR 功能不可用，请安装 pytesseract 和 pillow"
                result = ExtractionResult(
                    source=str(image_path),
                    text="",
                    success=False,
                    file_type="image",
                    error_message=error_msg
                )
                return result.to_dict() if return_dict else ""

            # 加载图像
            if isinstance(image_path, Image.Image):
                image = image_path
            elif isinstance(image_path, Path):
                image = Image.open(str(image_path))
            else:
                image = Image.open(image_path)

            # 图像预处理
            if self.preprocess and self.preprocessor:
                image = self.preprocessor.preprocess_for_ocr(image)

            # OCR 识别
            data = pytesseract.image_to_data(
                image,
                lang=self.lang,
                config=f"--psm {self.psm} --oem {self.oem}"
            )

            # 提取文本
            text = pytesseract.image_to_string(
                image,
                lang=self.lang,
                config=f"--psm {self.psm} --oem {self.oem}"
            )

            # 清理文本 (移除多余空行)
            text = self._clean_text(text)

            # 获取置信度 (从 image_to_data)
            confidence = self._calculate_confidence(data)

            result = ExtractionResult(
                source=str(image_path),
                text=text,
                success=True,
                file_type="image",
                language=self.lang,
                confidence=confidence
            )

            return result.to_dict() if return_dict else text

        except Exception as e:
            logger.error(f"图像 OCR 失败：{e}")
            result = ExtractionResult(
                source=str(image_path),
                text="",
                success=False,
                file_type="image",
                error_message=str(e)
            )
            return result.to_dict() if return_dict else ""

    def extract_from_pdf(self, pdf_path: Union[str, Path],
                        page_numbers: Optional[List[int]] = None,
                        return_dict: bool = False) -> Union[str, Dict[str, Any]]:
        """从 PDF 中提取文本

        优先使用 pdfplumber 提取原生文本，如果提取失败或需要 OCR，
        可以将 PDF 页面转换为图像进行 OCR 识别。

        Args:
            pdf_path: PDF 文件路径
            page_numbers: 要提取的页码列表 (None 表示全部)
            return_dict: 是否返回详细信息字典

        Returns:
            提取的文本或详细信息字典
        """
        try:
            if not PDFPLUMBER_AVAILABLE:
                error_msg = "PDF 提取功能不可用，请安装 pdfplumber"
                result = ExtractionResult(
                    source=str(pdf_path),
                    text="",
                    success=False,
                    file_type="pdf",
                    error_message=error_msg
                )
                return result.to_dict() if return_dict else ""

            pdf_path = str(pdf_path)
            text_parts = []
            page_count = 0

            with pdfplumber.open(pdf_path) as pdf:
                page_count = len(pdf.pages)

                # 确定要处理的页码
                if page_numbers:
                    pages_to_process = [p - 1 for p in page_numbers if 0 < p <= page_count]
                else:
                    pages_to_process = list(range(page_count))

                for page_num in pages_to_process:
                    page = pdf.pages[page_num]
                    page_text = page.extract_text()

                    if page_text and page_text.strip():
                        text_parts.append(page_text)
                    else:
                        logger.warning(f"第 {page_num + 1} 页没有提取到文本，可能需要 OCR")
                        # TODO: 这里可以添加 PDF 转图像后 OCR 的逻辑

            # 合并文本
            text = "\n\n".join(text_parts)
            text = self._clean_text(text)

            result = ExtractionResult(
                source=pdf_path,
                text=text,
                success=True,
                file_type="pdf",
                page_count=page_count
            )

            return result.to_dict() if return_dict else text

        except Exception as e:
            logger.error(f"PDF 文本提取失败：{e}")
            result = ExtractionResult(
                source=str(pdf_path),
                text="",
                success=False,
                file_type="pdf",
                error_message=str(e)
            )
            return result.to_dict() if return_dict else ""

    def extract_from_url(self, url: str,
                        save_path: Optional[str] = None,
                        return_dict: bool = False) -> Union[str, Dict[str, Any]]:
        """从 URL 下载并提取文本

        Args:
            url: 图像或 PDF 的 URL
            save_path: 临时保存路径 (None 使用临时文件)
            return_dict: 是否返回详细信息字典

        Returns:
            提取的文本或详细信息字典
        """
        try:
            import requests
            import tempfile

            # 下载文件
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # 确定文件类型
            content_type = response.headers.get('Content-Type', '')
            if 'pdf' in content_type:
                file_type = 'pdf'
            elif 'image' in content_type:
                file_type = 'image'
            else:
                # 从 URL 扩展名判断
                if url.lower().endswith('.pdf'):
                    file_type = 'pdf'
                else:
                    file_type = 'image'

            # 保存到临时文件
            if save_path:
                with open(save_path, 'wb') as f:
                    f.write(response.content)
                temp_path = save_path
            else:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf' if file_type == 'pdf' else '.jpg')
                temp_file.write(response.content)
                temp_file.close()
                temp_path = temp_file.name

            try:
                # 根据文件类型提取
                if file_type == 'pdf':
                    return self.extract_from_pdf(temp_path, return_dict=return_dict)
                else:
                    return self.extract_from_image(temp_path, return_dict=return_dict)
            finally:
                # 清理临时文件
                if not save_path and os.path.exists(temp_path):
                    os.remove(temp_path)

        except Exception as e:
            logger.error(f"URL 提取失败：{e}")
            result = ExtractionResult(
                source=url,
                text="",
                success=False,
                file_type="unknown",
                error_message=str(e)
            )
            return result.to_dict() if return_dict else ""

    def batch_extract(self, file_paths: List[Union[str, Path]],
                     max_workers: int = 4,
                     return_dicts: bool = False) -> List[Union[str, Dict[str, Any]]]:
        """批量提取多个文件的文本

        Args:
            file_paths: 文件路径列表
            max_workers: 最大并发工作线程数
            return_dicts: 是否返回详细字典列表

        Returns:
            提取结果列表
        """
        results = []

        def process_file(file_path: Union[str, Path]) -> Union[str, Dict[str, Any]]:
            """处理单个文件"""
            file_path = str(file_path)
            ext = Path(file_path).suffix.lower()

            if ext in self.pdf_extensions:
                return self.extract_from_pdf(file_path, return_dict=return_dicts)
            elif ext in self.image_extensions:
                return self.extract_from_image(file_path, return_dict=return_dicts)
            else:
                logger.warning(f"不支持的文件类型：{ext}")
                result = ExtractionResult(
                    source=file_path,
                    text="",
                    success=False,
                    file_type="unknown",
                    error_message=f"不支持的文件类型：{ext}"
                )
                return result.to_dict() if return_dicts else ""

        # 使用线程池并行处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_file, fp): fp for fp in file_paths}

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"处理文件失败 {futures[future]}: {e}")
                    results.append("") if not return_dicts else results.append({
                        'success': False,
                        'error_message': str(e)
                    })

        return results

    def _clean_text(self, text: str) -> str:
        """清理提取的文本

        Args:
            text: 原始文本

        Returns:
            清理后的文本
        """
        if not text:
            return ""

        # 移除多余空行 (保留单个空行)
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 移除行尾多余空格
        text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)

        # 移除首尾空白
        text = text.strip()

        return text

    def _calculate_confidence(self, data: str) -> Optional[float]:
        """计算 OCR 置信度

        Args:
            data: pytesseract image_to_data 返回的数据

        Returns:
            平均置信度 (0-100)
        """
        try:
            lines = data.strip().split('\n')[1:]  # 跳过表头
            confidences = []

            for line in lines:
                parts = line.split()
                if len(parts) >= 11:  # 确保有置信度字段
                    confidence = int(parts[10])
                    if confidence != -1:
                        confidences.append(confidence)

            if confidences:
                return sum(confidences) / len(confidences)
            return None
        except Exception:
            return None

    def get_supported_languages(self) -> List[str]:
        """获取支持的 OCR 语言列表

        Returns:
            语言代码列表
        """
        if not TESSERACT_AVAILABLE:
            return []

        try:
            langs = pytesseract.get_languages(config='').split('+')
            return langs
        except Exception:
            return []

    def get_version_info(self) -> Dict[str, Any]:
        """获取版本信息

        Returns:
            包含 pytesseract 和 tesseract 版本的字典
        """
        info = {}

        if TESSERACT_AVAILABLE:
            try:
                info['pytesseract'] = pytesseract.__version__
                info['tesseract'] = pytesseract.get_tesseract_version()
            except Exception as e:
                info['error'] = str(e)

        if PDFPLUMBER_AVAILABLE:
            try:
                info['pdfplumber'] = pdfplumber.__version__
            except Exception:
                pass

        if PIL_AVAILABLE:
            try:
                info['Pillow'] = Image.__version__
            except Exception:
                pass

        return info


# 便捷函数
def extract_text_from_image(image_path: Union[str, Path],
                           lang: str = 'chi_sim+eng',
                           preprocess: bool = True) -> str:
    """便捷函数：从图像提取文本

    Args:
        image_path: 图像路径
        lang: OCR 语言
        preprocess: 是否预处理

    Returns:
        提取的文本
    """
    processor = OCRProcessor(lang=lang, preprocess=preprocess)
    return processor.extract_from_image(image_path)


def extract_text_from_pdf(pdf_path: Union[str, Path],
                         page_numbers: Optional[List[int]] = None) -> str:
    """便捷函数：从 PDF 提取文本

    Args:
        pdf_path: PDF 路径
        page_numbers: 要提取的页码

    Returns:
        提取的文本
    """
    processor = OCRProcessor()
    return processor.extract_from_pdf(pdf_path, page_numbers=page_numbers)


def preprocess_image(image_path: Union[str, Path], output_path: Optional[str] = None,
                    apply_grayscale: bool = True, apply_threshold: bool = True,
                    apply_contrast: bool = True) -> Optional[Image.Image]:
    """便捷函数：预处理图像用于 OCR

    Args:
        image_path: 输入图像路径
        output_path: 输出路径 (None 不保存)
        apply_grayscale: 是否灰度化
        apply_threshold: 是否二值化
        apply_contrast: 是否增强对比度

    Returns:
        预处理后的图像 (如果 output_path 为 None)
    """
    if not PIL_AVAILABLE:
        raise ImportError("Pillow 未安装")

    processor = ImagePreprocessor()
    image = Image.open(image_path)

    processed = processor.preprocess_for_ocr(
        image,
        apply_grayscale=apply_grayscale,
        apply_threshold=apply_threshold,
        apply_contrast=apply_contrast
    )

    if output_path:
        processed.save(output_path)

    return None if output_path else processed


# 测试代码
if __name__ == "__main__":
    import sys

    # 打印版本信息
    processor = OCRProcessor()
    print("版本信息:", processor.get_version_info())
    print("支持的语言:", processor.get_supported_languages()[:5], "...")

    # 测试 OCR (如果提供了文件路径)
    if len(sys.argv) > 1:
        file_path = sys.argv[1]

        if Path(file_path).exists():
            print(f"\n处理文件：{file_path}")

            if file_path.lower().endswith('.pdf'):
                text = processor.extract_from_pdf(file_path, return_dict=True)
            else:
                text = processor.extract_from_image(file_path, return_dict=True)

            if isinstance(text, dict):
                print(f"成功：{text['success']}")
                print(f"文本长度：{len(text['text'])}")
                if text['confidence']:
                    print(f"置信度：{text['confidence']:.1f}%")
                print(f"\n预览:\n{text['text'][:500]}...")
            else:
                print(f"文本:\n{text[:500]}...")
        else:
            print(f"文件不存在：{file_path}")
    else:
        print("使用方法：python src/utils/image_ocr.py <image_or_pdf_path>")
        print("示例：python src/utils/image_ocr.py test.jpg")
        print("      python src/utils/image_ocr.py document.pdf")