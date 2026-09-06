# 海关报关智能生成系统

基于 Ollama + RAG 框架的智能海关报关单生成系统。

## 功能特性

- 🤖 **AI 智能处理**: 使用 Ollama + Qwen 模型进行智能数据分析和验证
- 📊 **多格式支持**: 支持 CSV、XLSX、XLS 文件输入
- 🔍 **数据验证**: 自动检测数据错误和不一致
- 📝 **报告生成**: 生成专业的报关单、装箱单、发票等文档
- 🔄 **智能纠错**: AI 辅助修正数据问题
- 📈 **数据分析**: 统计分析和数据预览

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 确保 Ollama 运行

```bash
# 启动 Ollama 服务
ollama serve

# 拉取模型 (可选，默认为 qwen3.5:27b)
ollama pull qwen3.5:27b
```

### 3. 运行

```bash
# 处理单个文件
python cli.py --input data/sample.csv

# 处理多个文件
python cli.py --input data/file1.csv data/file2.csv

# 自定义输出目录
python cli.py --input data/sample.csv --output my_output/

# 显示详细信息
python cli.py --input data/sample.csv --verbose
```

### 4. 配置

通过环境变量配置：

```bash
# Ollama 配置
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_MODEL=qwen3.5:27b
export OLLAMA_TIMEOUT=120

# 日志级别
export LOG_LEVEL=DEBUG
```

## 数据格式

系统支持两种数据格式：

### 格式 1: 扁平化格式 (一行一产品)

```csv
Exporter,Importer,Invoice No,HS Code,Product Name,Quantity,Unit,Unit Price,Weight,Origin
Test Company,Test Importer,INV-001,85285210,Monitor,100,PCS,100.00,5.0,CN
```

### 格式 2: 键值对格式

```csv
field,value
exporter,Test Company
importer,Test Importer
invoice_number,INV-001
products,"[{'hs_code': '85285210', 'product_name': 'Monitor', 'quantity': 100, 'unit': 'PCS', 'unit_price': 100.00, 'weight': 5.0, 'origin': 'CN'}]"
```

## 目录结构

```
customs_agent/
├── src/                    # 源代码
│   ├── __init__.py
│   ├── data/               # 数据层
│   │   ├── __init__.py
│   │   ├── loader.py       # 数据加载
│   │   ├── validator.py    # 数据验证
│   │   └── models.py       # 数据模型
│   ├── agent/              # Agent 层
│   │   ├── __init__.py
│   │   ├── coordinator.py  # Agent 协调器
│   │   ├── reasoner.py     # AI 推理引擎
│   │   └── prompt.py       # Prompt 模板
│   ├── template/           # 模板层
│   │   ├── __init__.py
│   │   └── engine.py       # 模板引擎
│   └── utils/              # 工具模块
│       ├── __init__.py
│       ├── config.py       # 配置管理
│       ├── logger.py       # 日志模块
│       └── constants.py    # 常量定义
├── tests/                  # 测试
│   ├── test_agent.py
│   ├── test_data.py
│   └── sample_data.csv
├── cli.py                  # CLI 入口
├── requirements.txt        # 依赖
├── README.md              # 文档
├── output/                # 输出目录
├── logs/                  # 日志目录
└── templates/             # 模板目录
```

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_agent.py -v

# 带覆盖率报告
pytest tests/ --cov=src --cov-report=html
```

## 使用示例

### 创建测试数据

```python
# 创建 CSV 文件
import pandas as pd

data = {
    "Exporter": ["Test Company"],
    "Importer": ["Test Importer"],
    "Invoice No": ["INV-001"],
    "HS Code": ["85285210"],
    "Product Name": ["Test Monitor"],
    "Quantity": [100],
    "Unit": ["PCS"],
    "Unit Price": [100.0],
    "Weight": [5.0],
    "Origin": ["CN"]
}

df = pd.DataFrame(data)
df.to_csv("test_data.csv", index=False)
```

### 处理数据

```bash
python cli.py --input test_data.csv
```

### 查看结果

```bash
# 查看输出文件
ls output/

# 查看日志
cat logs/customs_agent.log
```

## 错误处理

系统会自动检测以下错误：

- ❌ 缺失必填字段
- ❌ HS 编码格式错误
- ❌ 数量或价格为负数
- ❌ 单位不一致
- ⚠️ 数据不一致警告

## 扩展

### 添加新模板

1. 在 `templates/` 目录创建新模板
2. 在 `src/template/engine.py` 注册模板
3. 在 `src/agent/reasoner.py` 添加对应的 Prompt

### 自定义配置

```python
from src.utils.config import Config

# 设置输出目录
Config.set_output_dir("/path/to/output")

# 设置 Ollama 模型
Config.set_ollama_model("qwen3.5:27b")

# 打印配置
Config.print_config()
```

## 贡献

1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证

MIT License
