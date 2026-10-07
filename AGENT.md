# AGENT.md

面向 AI 编程助手（以及新加入的工程师）的项目说明书。
如需面向最终用户的使用说明，请阅读 [README.md](README.md)。

---

## 1. 项目概览

**海关报关智能生成系统**：读取 CSV/Excel 报关数据，经 AI 分析、解析、校验后，
生成 Word/Excel 报关单据。

技术栈：Python 3.10+ / pandas / python-docx / openpyxl / Ollama 或 OpenAI 兼容 API。

入口：`cli.py`（命令行）、`run_test.py`（端到端冒烟脚本）。

---

## 2. 大模型接入架构（重要）

系统支持**两种可随时切换的 LLM 后端**，通过环境变量 `LLM_BACKEND` 控制：

| `LLM_BACKEND` | 说明 | 依赖 |
|---|---|---|
| `ollama`（默认） | 本地 Ollama 服务 | `ollama` 库 |
| `openai` | 任何兼容 OpenAI 接口的远程服务（OpenAI / DeepSeek / Moonshot / vLLM / One-API…） | `openai>=1.0.0` |

**不设置任何新环境变量时，行为与纯 Ollama 版本完全一致。**

### 2.1 存在两个 LLM 客户端，职责不同

这是本项目最容易混淆的地方，修改前务必分清：

| 模块 | 工厂函数 | 用途 | 特性 |
|---|---|---|---|
| `src/agent/llm_client.py` | `src.agent.llm_client.get_llm_client()` | 面向 `AIReasoner` 的**无状态**单轮/多轮对话 | 抽象基类 + 三实现 + 重试 |
| `src/utils/llm_client.py` | `src.utils.llm_client.get_llm_client()` | 面向 `HeaderDetector`、`description_extractor`、`agents/core/agent.py` | 额外提供 **JSON 校验、磁盘缓存、模型降级** |

两者是**独立命名空间下的独立单例**，不要互相导入，也不要合并（缓存/降级语义不同）。
**两者都遵守 `LLM_BACKEND`**。

### 2.2 `src/agent/llm_client.py` 结构

```
BaseLLMClient (ABC)
├── chat(messages: list, **kwargs) -> str        # 抽象
├── generate(prompt: str, system: str) -> str    # 抽象
├── chat_stream(messages, callback=None) -> str  # 默认退化为非流式
└── is_available() -> bool                       # 非阻塞，不探活

OllamaClient            backend='ollama'   —— 封装 ollama.Client，行为与改造前一致
OpenAICompatibleClient  backend='openai'   —— openai SDK，自管重试
```

**重试策略**（`OpenAICompatibleClient`，由本类自行实现，SDK 内建重试已关闭）：

| 情况 | 行为 |
|---|---|
| 429 / 5xx / 超时 / 连接错误 | 重试至 `LLM_MAX_RETRIES`，指数退避 |
| 400 / 401 / 403 / 404 等其它 4xx | **不重试**，立即抛 `LLMClientError` |
| 重试耗尽 | 抛 `LLMClientError`，含 `status_code` 与 `attempts` |
| 流式请求 | **不重试**（避免已输出内容重复） |

### 2.3 惰性导入约定（关键约束）

`src/utils/__init__.py` 在包导入时即导入 `llm_client`，因此：

> **绝不能在模块顶层 `import openai`。**

`openai` 只允许在 `OpenAICompatibleClient.__init__` 或
`_call_openai_compatible` 内部导入，并捕获 `ImportError` 转为
`LLMNotInstalledError`（含 pip 安装提示）。

已验证：未安装 `openai` 时 `import src.utils` 与 `import src.agent` 均正常工作。

### 2.4 异常层次

定义在 `src/utils/llm_errors.py`（**零依赖模块**，避免循环导入）：

```
LLMConfigError(ValueError)        —— 配置缺失/非法，启动期错误
└── LLMNotInstalledError          —— 缺少 openai 依赖
LLMClientError(RuntimeError)      —— 调用失败；属性 .status_code / .attempts
```

> 该文件不得导入任何项目内其它模块 —— `config.py` 与两个 `llm_client.py` 都依赖它。

---

## 3. 配置

全部通过环境变量（支持 `.env`，由 `python-dotenv` 加载；参考 [.env.example](.env.example)）。

> **环境变量在 Python 进程启动时读取。** 运行期修改需调用
> `Config.set_llm_backend()` / `Config.set_llm_model()`。

### 后端选择

| 变量 | 默认值 | 说明 |
|---|---|---|
| `LLM_BACKEND` | `ollama` | `ollama` 或 `openai`（大小写不敏感） |

### Ollama（本地）

| 变量 | 默认值 |
|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` |
| `OLLAMA_MODEL` | `qwen3.5:27b` |
| `OLLAMA_TIMEOUT` | `120` |

### OpenAI 兼容（远程）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `OPENAI_API_KEY` | 空 | **必填**，缺失则启动即报错 |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | 须以 `http(s)://` 开头 |
| `OPENAI_MODEL` | `gpt-4o` | |
| `OPENAI_TIMEOUT` | `120` | |
| `OPENAI_FALLBACK_MODEL` | 空 | 仅远程模式；留空表示不降级 |

### 通用

| 变量 | 默认值 |
|---|---|
| `LLM_MAX_RETRIES` | `3` |
| `LLM_RETRY_BACKOFF` | `1.0`（秒，指数退避基数） |
| `LOG_LEVEL` | `INFO` |

### 各服务商配置速查

```bash
# OpenAI
LLM_BACKEND=openai
OPENAI_API_KEY=sk-xxxxxxxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o

# DeepSeek
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat

# Moonshot (Kimi)
OPENAI_BASE_URL=https://api.moonshot.cn/v1
OPENAI_MODEL=moonshot-v1-8k

# 本地 vLLM / LM Studio / One-API
OPENAI_API_KEY=not-needed
OPENAI_BASE_URL=http://localhost:8000/v1
OPENAI_MODEL=<你的模型名>
```

---

## 4. 真实目录结构

> ⚠️ [README.md](README.md) 的旧目录树曾把 `reasoning.py` 写成 `reasoner.py`、
> 把 `prompts.py` 写成 `prompt.py`。**以下是权威版本。**

```
custom_agent_project/
├── cli.py                     # CLI 入口（--input/--output/--config/--print-config）
├── run_test.py                # 端到端冒烟脚本（需要 tests/sample_data.csv）
├── AGENT.md / CLAUDE.md / README.md
├── .env.example               # 环境变量示例
├── requirements.txt
├── config/
│   ├── config.yaml            # 仅 tools/extract_table.py 读取，非全局配置！
│   └── currency_mapping.json
├── src/
│   ├── agent/                 # 工作流编排层
│   │   ├── coordinator.py     # AgentCoordinator：load→analyze→parse→validate→select→generate
│   │   ├── reasoning.py       # AIReasoner（别名 Reasoner）—— 提示词封装
│   │   ├── llm_client.py      # ★ BaseLLMClient / OllamaClient / OpenAICompatibleClient
│   │   └── prompts.py         # Prompt 模板
│   ├── data/                  # loader.py / models.py / validator.py / cache.py
│   ├── template/engine.py     # Word/Excel 生成
│   └── utils/
│       ├── config.py          # ★ Config（含 LLM 后端配置与 validate_llm）
│       ├── llm_errors.py      # ★ LLM 异常（零依赖）
│       ├── llm_client.py      # ★ legacy LLMClient（缓存/降级，同样遵守 LLM_BACKEND）
│       ├── header_detector.py / description_extractor.py
│       ├── hs_validator.py / compliance_checker.py / image_ocr.py
│       └── constants.py / logger.py / cli_interface.py ...
├── agents/                    # 另一套「通用 Agent 框架」（与 src/agent 无关！）
│   ├── core/agent.py          #   使用 src.utils.llm_client
│   └── tools/builtin/...      #   bash/file/web/code/memory/search 工具
├── tools/extract_table.py
└── tests/
```

### `src/agent/` 与 `agents/` 的区别

- **`src/agent/`** —— 报关业务的**工作流编排**，由 `cli.py` 驱动。
- **`agents/`** —— 一个**通用 Agent 框架**（工具调用循环、工具注册表），
  与报关流程相互独立；仅 `agents/core/agent.py` 复用了 `src.utils.llm_client`。

修改 LLM 相关内容时，两者可能都需要考虑。

---

## 5. 常见任务的正确做法

### 新增一个使用 LLM 的功能

```python
# 业务编排（无状态对话）—— 优先复用 AIReasoner
from src.agent.reasoning import AIReasoner
reasoner = AIReasoner()          # 自动按 LLM_BACKEND 选后端

# 需要 JSON 校验 / 缓存 / 降级 —— 使用 legacy 客户端
from src.utils.llm_client import get_llm_client
client = get_llm_client()
data = client.call_with_retry(prompt, system=..., require_json=True)

# 需要自定义后端/模型 —— 直接构造客户端
from src.agent.llm_client import get_llm_client as get_agent_client
client = get_agent_client(model="deepseek-chat")
```

### 测试中的正确打桩方式

`Config` 在**导入期**读取环境变量，因此测试里改 `os.environ` **无效**，
必须直接打桩类属性，并在结束后还原：

```python
from src.utils.config import Config

original = Config.LLM_BACKEND
Config.LLM_BACKEND = 'openai'
try:
    ...
finally:
    Config.LLM_BACKEND = original
```

另外务必调用 `reset_llm_client()`（两个模块各有同名函数）清理单例缓存。

---

## 6. 开发命令

```bash
pip install -r requirements.txt

# 全部测试
python3 -m pytest tests/ -q

# 只跑 LLM 相关（无需网络/无需安装 openai）
python3 -m pytest tests/test_llm_client.py -v

# 集成测试（需真实 openai SDK；未安装则自动跳过）
pip install "openai>=1.0.0"
python3 -m pytest tests/test_llm_integration.py -v

# 端到端（需本地 Ollama 与 tests/sample_data.csv）
python3 run_test.py

# 生产运行
python3 cli.py --input data/sample.csv --output my_output/
python3 cli.py --print-config          # 密钥自动脱敏
```

---

## 7. 已知问题

### 7.1 LLM 相关

- **`.llm_cache/` 会跨后端复用问题**：缓存键为 `md5(f"{model}:{prompt}")`，
  不同模型名天然隔离；但**同名模型**在切换后端后仍会命中旧缓存。
  切换后端请清理：`rm -rf .llm_cache/*`。
- **远程模式默认不降级**：`OPENAI_FALLBACK_MODEL` 为空时，重试耗尽即失败。
  Ollama 模式仍保留原有硬编码降级模型 `glm-4.7-flash`（为避免行为漂移）。
- **`is_available()` 不探活**：仅表示"库已安装且客户端已构造"，不代表服务可达。
  这是刻意保持的语义，以免给离线场景引入额外延迟。

### 7.2 既有缺陷（**与 LLM 改造无关，修复前请先确认**）

当前 `pytest tests/ -q` 的基线为 **64 passed / 7 failed**，7 项失败均为改造前既有：

- `tests/test_data.py`（5 项）：`DataValidator` 缺少测试所依赖的 `reset()`
  方法或相关断言不匹配。
- `tests/test_agent.py`（2 项）：`tests/sample_data.csv` 不存在导致加载失败，
  且 `test_process_file` 在 AI 不可用时断言过严。
- `run_test.py` 依赖 `tests/sample_data.csv`，该文件当前**不存在**。

> 判定回归的方法：确认失败集合与上述 7 项**完全一致**，且通过数只增不减。

---

## 8. 修改本项目时的注意事项

1. **保持向后兼容**：`LLM_BACKEND=ollama` 时必须是彻底的 no-op 路径。
2. **不要在模块顶层导入 `openai`**（见 2.3）。
3. **不要在 `src/utils/llm_errors.py` 中导入项目内其它模块**（避免循环导入）。
4. **`AIReasoner` 的对外签名不要变**：`coordinator.py` 与 `tests/test_agent.py` 依赖它。
   需要新名称时请加别名（现有 `Reasoner = AIReasoner`）。
5. **日志与打印中务必脱敏密钥**：复用 `src.utils.config.mask_secret`。
6. 每个模块使用 `setup_logger(__name__)` 获取 logger。
7. `config/config.yaml` **不是**全局配置，仅服务于 `tools/extract_table.py`。
