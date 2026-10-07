# 海关报关智能生成系统

**简体中文** | [English](README.en.md)

基于大语言模型的智能海关报关单生成系统，支持**本地 Ollama** 与**远程 OpenAI 兼容接口**（OpenAI / DeepSeek / Moonshot 等）两种后端，可随时切换。

> 📖 面向 AI 助手与开发者的技术说明见 [AGENT.md](AGENT.md)。

## 功能特性

- 🤖 **AI 智能处理**: 支持本地 Ollama 或远程 API（OpenAI / DeepSeek / Moonshot 等）
- 🔀 **后端可切换**: 通过 `LLM_BACKEND` 环境变量一键切换，默认本地 Ollama
- 📊 **多格式支持**: 支持 CSV、XLSX、XLS 文件输入
- 🔍 **数据验证**: 自动检测数据错误和不一致
- 📝 **报告生成**: 生成专业的报关单、装箱单、发票等文档
- 🔄 **智能纠错**: AI 辅助修正数据问题
- 📈 **数据分析**: 统计分析和数据预览

## 架构总览

![双后端 LLM 架构](docs/architecture-preview.png)

系统把"调用哪个大模型"收敛到单一位置：业务代码只依赖 `AIReasoner`，
由 `get_llm_client()` 工厂根据 `LLM_BACKEND` 决定实例化 `OllamaClient`（本地）
还是 `OpenAICompatibleClient`（远程）。因此在两种模式之间切换时，
`AgentCoordinator` 及其上层调用方无需任何改动。

- **交互式架构图**（可切换主题、缩放、搜索、聚焦、导出）：[docs/llm-backend-architecture.html](docs/llm-backend-architecture.html)
- **架构图源文件**（Archify JSON，可修改后重新生成）：[docs/llm-backend-architecture.json](docs/llm-backend-architecture.json)

```
CLI 入口 → AgentCoordinator → AIReasoner → get_llm_client()
                                              ├─ LLM_BACKEND=ollama → OllamaClient → Ollama 服务 (localhost:11434)
                                              └─ LLM_BACKEND=openai → OpenAICompatibleClient → 远程 API
```

> ℹ️ 架构图由 [Archify](https://github.com/tt-a1i/archify) 生成。修改
> `docs/llm-backend-architecture.json` 后需重新运行 `validate` 与 `deliver`
> 才会更新 HTML（该 HTML 是自包含单文件，可直接用浏览器打开）。

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

通过环境变量配置（也可复制 `.env.example` 为 `.env` 后填写）。

#### 模式一：本地 Ollama（默认）

不设置任何变量即为本地模式，行为与以往完全一致：

```bash
# Ollama 配置
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_MODEL=qwen3.5:27b
export OLLAMA_TIMEOUT=120

# 日志级别
export LOG_LEVEL=DEBUG
```

#### 模式二：远程大模型（OpenAI 兼容接口）

先安装远程调用所需依赖：

```bash
pip install "openai>=1.0.0"
```

再设置以下环境变量：

```bash
export LLM_BACKEND=openai
export OPENAI_API_KEY=sk-xxxxxxxx          # 必填，缺失会启动即报错
export OPENAI_BASE_URL=https://api.openai.com/v1
export OPENAI_MODEL=gpt-4o

python cli.py --input data/sample.csv
```

常用服务商配置：

| 服务商 | `OPENAI_BASE_URL` | `OPENAI_MODEL` 示例 |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Moonshot (Kimi) | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| 本地 vLLM / LM Studio | `http://localhost:8000/v1` | 你的模型名 |

例如使用 DeepSeek：

```bash
export LLM_BACKEND=openai
export OPENAI_API_KEY=sk-你的密钥
export OPENAI_BASE_URL=https://api.deepseek.com/v1
export OPENAI_MODEL=deepseek-chat
```

#### 切回本地模式

```bash
unset LLM_BACKEND                 # 或 export LLM_BACKEND=ollama
```

#### 查看当前生效配置

```bash
python cli.py --print-config      # API Key 会自动脱敏
```

#### 完整配置项

| 变量 | 默认值 | 说明 |
|---|---|---|
| `LLM_BACKEND` | `ollama` | `ollama` 或 `openai` |
| `OLLAMA_HOST` | `http://localhost:11434` | 本地服务地址 |
| `OLLAMA_MODEL` | `qwen3.5:27b` | 本地模型 |
| `OLLAMA_TIMEOUT` | `120` | 本地超时（秒） |
| `OPENAI_API_KEY` | 空 | 远程密钥（`openai` 模式必填） |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | 远程服务地址 |
| `OPENAI_MODEL` | `gpt-4o` | 远程模型 |
| `OPENAI_TIMEOUT` | `120` | 远程超时（秒） |
| `OPENAI_FALLBACK_MODEL` | 空 | 可选降级模型，留空表示不降级 |
| `LLM_MAX_RETRIES` | `3` | 失败重试次数（429/5xx/超时） |
| `LLM_RETRY_BACKOFF` | `1.0` | 重试退避基数（秒） |
| `LOG_LEVEL` | `INFO` | 日志级别 |

#### 重试与错误处理

- 遇到 **429 限流 / 5xx / 超时** 会自动重试，次数由 `LLM_MAX_RETRIES` 控制；
- 遇到 **401 / 403 / 404 / 400** 等错误**不会重试**，立即失败并在日志中给出 HTTP 状态码；
- `LLM_BACKEND=openai` 但缺少 `OPENAI_API_KEY` 时，程序会在**启动阶段**直接报错退出并给出修复提示。

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
│   │   ├── reasoning.py    # AI 推理引擎（别名 Reasoner）
│   │   ├── llm_client.py   # LLM 客户端（Ollama / OpenAI 兼容）
│   │   └── prompts.py      # Prompt 模板
│   ├── template/           # 模板层
│   │   ├── __init__.py
│   │   └── engine.py       # 模板引擎
│   └── utils/              # 工具模块
│       ├── __init__.py
│       ├── config.py       # 配置管理
│       ├── llm_client.py   # LLM 客户端（缓存/降级）
│       ├── llm_errors.py   # LLM 异常定义
│       ├── logger.py       # 日志模块
│       └── constants.py    # 常量定义
├── tests/                  # 测试
│   ├── test_agent.py
│   ├── test_data.py
│   ├── test_llm_client.py       # LLM 客户端单元测试（无需联网）
│   ├── test_llm_integration.py  # LLM 集成测试（需 openai 依赖）
│   └── sample_data.csv
├── docs/                   # 架构图
│   ├── llm-backend-architecture.html      # 交互式架构图（自包含单文件）
│   ├── llm-backend-architecture.json      # Archify 源文件
│   └── architecture-preview.png           # README 中引用的静态预览图
├── cli.py                  # CLI 入口
├── requirements.txt        # 依赖
├── README.md               # 用户文档（简体中文）
├── README.en.md            # 用户文档（English）
├── AGENT.md                # 面向 AI/开发者的技术说明
├── CLAUDE.md               # Claude Code 指引
├── .env.example            # 环境变量示例
├── .gitignore              # Git 忽略规则
├── output/                # 输出目录
├── logs/                  # 日志目录（已 gitignore）
└── templates/             # 模板目录
```

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_agent.py -v

# 仅运行 LLM 相关测试（全 mock，无需联网、无需安装 openai）
pytest tests/test_llm_client.py -v

# LLM 集成测试（需真实 openai SDK；未安装则自动跳过）
pip install "openai>=1.0.0"
pytest tests/test_llm_integration.py -v

# 带覆盖率报告
pytest tests/ --cov=src --cov-report=html
```

> ✅ `pytest tests/ -q` 当前为 **72 passed / 7 skipped / 0 failed**，
> 全套约 1 秒完成。测试使用离线替身，**不依赖本机是否运行 Ollama**。
> （7 项 skipped 为 LLM 集成测试，需 `pip install "openai>=1.0.0"` 后才会执行。）

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
3. 在 `src/agent/prompts.py` 添加对应的 Prompt

### 自定义配置

```python
from src.utils.config import Config

# 设置输出目录
Config.set_output_dir("/path/to/output")

# 设置 Ollama 模型
Config.set_ollama_model("qwen3.5:27b")

# 运行期切换后端（等价于 LLM_BACKEND 环境变量）
Config.set_llm_backend("openai")
Config.set_llm_model("deepseek-chat")

# 打印配置（密钥自动脱敏）
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
