"""常量定义"""

# 货币符号映射
CURRENCY_SYMBOLS = {
    'CNY': '¥',
    'USD': '$',
    'EUR': '€',
    'JPY': '¥',
    'GBP': '£',
    'HKD': 'HK$',
    'SGD': 'S$',
    'KRW': '₩',
    'THB': '฿',
}

# 默认单位
DEFAULT_UNIT = "PCS"

# 常用单位
COMMON_UNITS = [
    "PCS",    # 件
    "KG",     # 千克
    "L",      # 升
    "M",      # 米
    "M2",     # 平方米
    "M3",     # 立方米
    "SET",    # 套
    "BOX",    # 箱
    "PAIR",   # 对
    "ROLL",   # 卷
]

# 海关代码格式
HS_CODE_PATTERN = r'^\d{6}(\d{2}){0,2}$'  # HS 编码格式：6 位或 10 位数字

# 币种代码
CURRENCY_CODES = [
    'CNY', 'USD', 'EUR', 'JPY', 'GBP',
    'HKD', 'SGD', 'KRW', 'THB', 'CAD',
    'AUD', 'CHF', 'INR', 'MXN', 'BRL',
]

# 报关单类型
REPORT_TYPES = {
    'declaration': '报关单',
    'packing_list': '装箱单',
    'invoice': '发票',
    'certificate': '原产地证书',
}

# 验证错误类型
VALIDATION_ERROR_TYPES = {
    'MISSING_FIELD': '缺少字段',
    'INVALID_FORMAT': '格式无效',
    'INVALID_VALUE': '值无效',
    'CALCULATION_ERROR': '计算错误',
    'CONSISTENCY_ERROR': '一致性错误',
}

# 文件类型
FILE_TYPES = {
    'csv': 'CSV 文件',
    'xlsx': 'Excel 文件 (.xlsx)',
    'xls': 'Excel 文件 (.xls)',
}

# 报关单必填字段
DECLARATION_REQUIRED_FIELDS = [
    'exporter',
    'importer',
    'invoice_number',
    'products'
]

# 产品必填字段
PRODUCT_REQUIRED_FIELDS = [
    'hs_code',
    'product_name',
    'quantity',
    'unit',
    'unit_price'
]

# 数据验证规则
DATA_VALIDATION_RULES = {
    'hs_code': {
        'pattern': HS_CODE_PATTERN,
        'error_message': 'HS 编码格式错误（应为 6-10 位数字）'
    },
    'quantity': {
        'min': 0,
        'error_message': '数量不能为负数'
    },
    'unit_price': {
        'min': 0,
        'error_message': '单价不能为负数'
    },
    'weight': {
        'min': 0,
        'error_message': '重量不能为负数'
    }
}

# 合规风险类型
RISK_TYPES = {
    'IMPORT_LICENSE': {
        'name': '进口许可证',
        'code': 'IMPORT_LICENSE',
        'description': '需要进口许可证的商品',
        'severity': 'HIGH'
    },
    'ANTI_DUMPING': {
        'name': '反倾销税',
        'code': 'ANTI_DUMPING',
        'description': '受反倾销措施影响的商品',
        'severity': 'HIGH'
    },
    'QUOTA_CONTROL': {
        'name': '配额管制',
        'code': 'QUOTA_CONTROL',
        'description': '需要进口配额的商品',
        'severity': 'MEDIUM'
    },
    'QUALITY_CERT': {
        'name': '质量认证',
        'code': 'QUALITY_CERT',
        'description': '需要质量认证的商品',
        'severity': 'MEDIUM'
    },
    'SANITARY_INSPECTION': {
        'name': '检验检疫',
        'code': 'SANITARY_INSPECTION',
        'description': '需要检验检疫的商品',
        'severity': 'MEDIUM'
    },
    'TWO_USE': {
        'name': '两用物项',
        'code': 'TWO_USE',
        'description': '军民两用物项管制',
        'severity': 'HIGH'
    },
    'ORIGIN_RESTRICT': {
        'name': '原产地限制',
        'code': 'ORIGIN_RESTRICT',
        'description': '特定原产地限制商品',
        'severity': 'HIGH'
    }
}

# 风险等级
RISK_LEVELS = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']

# 管制清单：需要进口许可证的 HS 编码前缀
IMPORT_LICENSE_HSCODE_PREFIXES = [
    '0101',  # 活动马
    '0102',  # 活动牛
    '0103',  # 活动猪
    '0104',  # 活动羊
    '0105',  # 活动鸡
    '0106',  # 活动鸭
    '0401',  # 鲜奶
    '0402',  # 浓缩奶
    '1516',  # 动物油
    '1517',  # 加工食用脂
]

# 反倾销税清单：HS 编码 + 原产国
ANTI_DUMPING_LIST = [
    {'hs_code_prefix': '3901', 'origins': ['越南', '泰国'], 'product': '聚乙烯'},
    {'hs_code_prefix': '7207', 'origins': ['韩国', '日本'], 'product': '热轧钢坯'},
    {'hs_code_prefix': '7208', 'origins': ['韩国', '台湾'], 'product': '热轧钢板'},
    {'hs_code_prefix': '7209', 'origins': ['韩国', '日本'], 'product': '热轧薄板'},
    {'hs_code_prefix': '7210', 'origins': ['欧盟', '韩国'], 'product': '镀层钢板'},
    {'hs_code_prefix': '7211', 'origins': ['韩国'], 'product': '涂层钢板'},
    {'hs_code_prefix': '7212', 'origins': ['韩国', '日本'], 'product': '合金钢板'},
    {'hs_code_prefix': '8421', 'origins': ['美国'], 'product': '空气过滤设备'},
    {'hs_code_prefix': '8517', 'origins': ['越南', '马来西亚'], 'product': '通信设备'},
    {'hs_code_prefix': '9405', 'origins': ['印度'], 'product': '灯具'}
]

# 配额管制清单：HS 编码前缀
QUOTA_CONTROL_HSCODE_PREFIXES = [
    '0201',  # 鲜冻牛肉
    '0202',  # 鲜冻羊肉
    '0206',  # 牲口食用杂碎
    '1001',  # 小麦
    '1002',  # 黑麦
    '1003',  # 大麦
    '1005',  # 玉米
    '1006',  # 大米
    '1210',  # 豆类
    '1211',  # 油料种子
    '1212',  # 淀粉
    '1701',  # 甘蔗糖
    '1702',  # 甜菜糖
    '2303',  # 谷物纤维残渣
    '2304',  # 豆油渣
    '2305',  # 花生渣
]

# 质量认证要求清单
QUALITY_CERT_LIST = [
    {'hs_code_prefix': '8415', 'cert': 'CCC', 'product': '空调'},
    {'hs_code_prefix': '8418', 'cert': 'CCC', 'product': '电冰箱'},
    {'hs_code_prefix': '8419', 'cert': 'CCC', 'product': '洗衣机'},
    {'hs_code_prefix': '8511', 'cert': 'CCC', 'product': '点火线圈'},
    {'hs_code_prefix': '8512', 'cert': 'CCC', 'product': '汽车灯具'},
    {'hs_code_prefix': '8513', 'cert': 'CCC', 'product': '手电筒'},
    {'hs_code_prefix': '8514', 'cert': 'CCC', 'product': '微波炉'},
    {'hs_code_prefix': '8516', 'cert': 'CCC', 'product': '电热水器'},
    {'hs_code_prefix': '8519', 'cert': 'CCC', 'product': 'CD 播放机'},
    {'hs_code_prefix': '8521', 'cert': 'CCC', 'product': '录像机'},
]

# 检验检疫清单：HS 编码前缀
SANITARY_INSPECTION_HSCODE_PREFIXES = [
    '0101',  # 活动马
    '0102',  # 活动牛
    '0103',  # 活动猪
    '0104',  # 活动羊
    '0105',  # 活动鸡
    '0106',  # 活动鸭
    '0107',  # 活动火鸡
    '0201',  # 鲜冻牛肉
    '0202',  # 鲜冻羊肉
    '0203',  # 鲜冻猪肉
    '0204',  # 鲜冻绵羊肉
    '0207',  # 鲜冻鸡鸭肉
    '0301',  # 活动鱼苗
    '0302',  # 冷冻鱼
    '0303',  # 鲜冷鱼
    '0304',  # 去骨鱼肉
    '0305',  # 干熏鱼
    '0306',  # 甲壳动物
    '0307',  # 软体动物
    '0701',  # 马铃薯
    '0702',  # 番茄
    '0703',  # 洋葱
    '0704',  # 葱蒜
    '0705',  # 生菜
    '0706',  # 胡萝卜
    '0707',  # 黄瓜
    '0708',  # 豆类蔬菜
    '0709',  # 其他蔬菜
    '0801',  # 香蕉
    '0802',  # 坚果
    '0803',  # 鲜柠檬
    '0804',  # 鲜柑橘
    '0805',  # 鲜葡萄
    '0806',  # 鲜葡萄
    '0807',  # 鲜西瓜
    '0808',  # 鲜苹果
    '0809',  # 鲜甜橙
    '0810',  # 其他水果
]

# 两用物项管制清单
TWO_USE_HSCODE_PREFIXES = [
    '3822',  # 化验室用试剂
    '3823',  # 有机化学产品
    '3824',  # 其他未列名制品
    '8413',  # 泵
    '8414',  # 风机
    '8415',  # 空调器
    '8419',  # 锅炉
    '8421',  # 过滤设备
    '8422',  # 洗瓶机
    '8423',  # 秤
    '8424',  # 喷雾器
    '8425',  # 起重机
    '8426',  # 升降机
    '8427',  # 叉车
    '8428',  # 自动梯
]

# 特定原产地限制清单
ORIGIN_RESTRICTED_COUNTRY = {
    '美国': {
        'hs_code_prefixes': ['8517', '8528', '8471'],
        'reason': '贸易制裁',
        'risk_level': 'HIGH'
    },
    '俄罗斯': {
        'hs_code_prefixes': ['7207', '7208', '7209', '7210'],
        'reason': '进口许可要求',
        'risk_level': 'MEDIUM'
    },
    '伊朗': {
        'hs_code_prefixes': ['2709', '2710', '2711', '2712', '2713'],
        'reason': '能源产品管制',
        'risk_level': 'CRITICAL'
    },
    '朝鲜': {
        'hs_code_prefixes': ['*'],
        'reason': '全面贸易限制',
        'risk_level': 'CRITICAL'
    }
}
