"""HS 编码校验模块

提供 HS 编码的校验、纠错功能：
1. 位数检查（6-10 位）
2. 前 6 位标准表校验
3. 智能纠错（取前 3 个候选取交集）
"""

import re
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
import requests

logger = logging.getLogger(__name__)


class HSValidator:
    """HS 编码校验器"""

    def __init__(self, local_db_path: str = None, api_url: str = "https://api.example.com/hs/validate"):
        """
        初始化 HS 编码校验器

        Args:
            local_db_path: 本地 HS 编码表路径（2024 版）
            api_url: 在线校验 API 地址
        """
        self.local_db_path = local_db_path
        self.api_url = api_url
        self.hs_standard_table: Dict[str, Any] = {}
        self._load_local_db()

    def _load_local_db(self) -> bool:
        """
        加载本地 HS 编码标准表

        Returns:
            bool: 加载是否成功
        """
        if not self.local_db_path:
            logger.info("未配置本地 HS 编码表路径，跳过加载")
            return False

        try:
            with open(self.local_db_path, 'r', encoding='utf-8') as f:
                self.hs_standard_table = json.load(f)
            logger.info(f"成功加载本地 HS 编码表，共 {len(self.hs_standard_table.get('codes', {}))} 条记录")
            return True
        except FileNotFoundError:
            logger.warning(f"本地 HS 编码表文件不存在：{self.local_db_path}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"本地 HS 编码表格式错误：{e}")
            return False

    def validate_format(self, hs_code: str) -> Tuple[bool, str]:
        """
        校验 HS 编码格式

        Args:
            hs_code: HS 编码字符串

        Returns:
            Tuple[bool, str]: (是否有效，错误信息)
        """
        if not hs_code:
            return False, "HS 编码不能为空"

        # 移除空格和小数点，只保留数字
        clean_code = re.sub(r'[\s\.\-]', '', str(hs_code))

        if not clean_code.isdigit():
            return False, "HS 编码只能包含数字"

        # HS 编码位数检查：6-10 位
        if len(clean_code) < 6:
            return False, f"HS 编码位数不足，需要至少 6 位，当前 {len(clean_code)} 位"

        if len(clean_code) > 10:
            return False, f"HS 编码位数过多，最多 10 位，当前 {len(clean_code)} 位"

        return True, ""

    def validate_in_standard_table(self, hs_code: str) -> Tuple[bool, str]:
        """
        校验 HS 编码前 6 位是否存在于标准表中

        Args:
            hs_code: HS 编码字符串

        Returns:
            Tuple[bool, str]: (是否有效，错误信息)
        """
        clean_code = re.sub(r'[\s\.\-]', '', str(hs_code))
        prefix_6 = clean_code[:6]

        # 检查本地表
        if self.hs_standard_table:
            codes = self.hs_standard_table.get('codes', {})
            if prefix_6 in codes:
                return True, ""
            else:
                return False, f"前 6 位 '{prefix_6}' 不在本地标准表中"

        # 如果本地表未加载，尝试在线 API
        return self._validate_by_api(hs_code)

    def _validate_by_api(self, hs_code: str) -> Tuple[bool, str]:
        """
        通过在线 API 校验 HS 编码

        Args:
            hs_code: HS 编码字符串

        Returns:
            Tuple[bool, str]: (是否有效，错误信息)
        """
        try:
            response = requests.get(f"{self.api_url}?code={hs_code}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('valid', False):
                    return True, ""
                else:
                    return False, data.get('message', 'HS 编码无效')
            else:
                logger.warning(f"API 返回非 200 状态码：{response.status_code}")
                return False, "API 校验失败"
        except requests.RequestException as e:
            logger.warning(f"API 调用失败：{e}")
            return False, "API 不可用"

    def suggest_corrections(self, hs_code: str, top_n: int = 3) -> List[Dict[str, Any]]:
        """
        为无效的 HS 编码提供纠正建议

        Args:
            hs_code: HS 编码字符串
            top_n: 返回前 N 个候选

        Returns:
            List[Dict[str, Any]]: 候选 HS 编码列表
        """
        clean_code = re.sub(r'[\s\.\-]', '', str(hs_code))
        prefix_6 = clean_code[:6]

        suggestions = []

        # 从本地表查找相似编码
        if self.hs_standard_table:
            codes = self.hs_standard_table.get('codes', {})
            # 使用前缀查找
            for code, info in codes.items():
                if code.startswith(prefix_6[:4]):  # 前 4 位匹配
                    similarity = self._calculate_similarity(prefix_6, code)
                    if similarity > 0.5:  # 相似度大于 0.5
                        suggestions.append({
                            'code': code,
                            'description': info.get('description', ''),
                            'similarity': similarity,
                            'confidence': similarity
                        })

        # 如果本地表没有足够建议，尝试在线 API
        if len(suggestions) < top_n:
            api_suggestions = self._suggest_by_api(hs_code)
            suggestions.extend(api_suggestions)

        # 按置信度排序，取前 N 个
        suggestions.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        return suggestions[:top_n]

    def _suggest_by_api(self, hs_code: str) -> List[Dict[str, Any]]:
        """
        通过在线 API 获取纠正建议

        Args:
            hs_code: HS 编码字符串

        Returns:
            List[Dict[str, Any]]: 候选 HS 编码列表
        """
        try:
            response = requests.get(
                f"{self.api_url}/suggest?code={hs_code}",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                suggestions = []
                for i, item in enumerate(data.get('suggestions', [])[:3]):
                    suggestions.append({
                        'code': item.get('code', ''),
                        'description': item.get('description', ''),
                        'similarity': 1.0 - (i * 0.1),
                        'confidence': 1.0 - (i * 0.1)
                    })
                return suggestions
        except requests.RequestException as e:
            logger.warning(f"API 纠错建议调用失败：{e}")
        return []

    def _calculate_similarity(self, code1: str, code2: str) -> float:
        """
        计算两个 HS 编码的相似度

        Args:
            code1: 第一个编码
            code2: 第二个编码

        Returns:
            float: 相似度 (0-1)
        """
        min_len = min(len(code1), len(code2))
        if min_len == 0:
            return 0.0

        matching_chars = sum(1 for a, b in zip(code1[:min_len], code2[:min_len]) if a == b)
        return matching_chars / min_len

    def correct_by_intersection(self, hs_code: str, candidates: int = 3) -> Dict[str, Any]:
        """
        智能纠错：取置信度最高的前 3 个候选取交集

        Args:
            hs_code: 原始 HS 编码
            candidates: 候选数量

        Returns:
            Dict[str, Any]: 纠错结果
        """
        suggestions = self.suggest_corrections(hs_code, top_n=candidates)

        if not suggestions:
            return {
                'success': False,
                'original': hs_code,
                'corrected': None,
                'reasoning': '无可用候选编码',
                'confidence': 0.0
            }

        # 取前 3 个候选的交集（共同前缀）
        common_prefix = self._find_common_prefix([s['code'] for s in suggestions[:candidates]])

        if common_prefix and len(common_prefix) >= 6:
            return {
                'success': True,
                'original': hs_code,
                'corrected': common_prefix,
                'reasoning': f'取前{len(suggestions)}个候选编码的交集：{", ".join([s["code"] for s in suggestions[:candidates]])}',
                'confidence': min(s['confidence'] for s in suggestions[:candidates]),
                'candidates': suggestions[:candidates]
            }
        else:
            # 如果交集不足 6 位，返回置信度最高的单个候选
            best = suggestions[0]
            return {
                'success': True,
                'original': hs_code,
                'corrected': best['code'],
                'reasoning': f'交集不足 6 位，采用最高置信度候选：{best["code"]}',
                'confidence': best['confidence'],
                'candidates': suggestions[:candidates]
            }

    def _find_common_prefix(self, codes: List[str]) -> str:
        """
        找到多个编码的共同前缀

        Args:
            codes: 编码列表

        Returns:
            str: 共同前缀
        """
        if not codes:
            return ""

        common = ""
        for i in range(min(len(c) for c in codes)):
            chars = [c[i] for c in codes]
            if len(set(chars)) == 1:
                common += chars[0]
            else:
                break
        return common

    def validate_and_correct(self, hs_code: str) -> Dict[str, Any]:
        """
        完整校验并纠错流程

        Args:
            hs_code: HS 编码字符串

        Returns:
            Dict[str, Any]: 校验和纠错结果
        """
        result = {
            'original': hs_code,
            'valid': False,
            'corrected': None,
            'errors': [],
            'reasoning': '',
            'confidence': 0.0
        }

        # 步骤 1: 格式校验
        format_valid, format_error = self.validate_format(hs_code)
        if not format_valid:
            result['errors'].append(format_error)
            result['reasoning'] = f'格式校验失败：{format_error}'
            return result

        # 步骤 2: 标准表校验
        standard_valid, standard_error = self.validate_in_standard_table(hs_code)
        if standard_valid:
            result['valid'] = True
            result['corrected'] = re.sub(r'[\s\.\-]', '', hs_code)
            result['reasoning'] = 'HS 编码格式正确且存在于标准表中'
            result['confidence'] = 1.0
            return result

        result['errors'].append(standard_error)

        # 步骤 3: 尝试纠错
        correction = self.correct_by_intersection(hs_code)
        if correction['success']:
            result['corrected'] = correction['corrected']
            result['reasoning'] = correction['reasoning']
            result['confidence'] = correction['confidence']
            result['candidates'] = correction.get('candidates', [])
        else:
            result['reasoning'] = correction['reasoning']

        return result


def create_hs_validator(local_db_path: str = None, api_url: str = None) -> HSValidator:
    """
    创建 HS 校验器实例

    Args:
        local_db_path: 本地 HS 编码表路径
        api_url: 在线 API 地址

    Returns:
        HSValidator: 校验器实例
    """
    return HSValidator(local_db_path=local_db_path, api_url=api_url)
