# AGENT.md — `agents/` 多智能体协作框架

本文件介绍 **`agents/` 包**（约 4,600 行、18 个 Python 文件）。
项目总体说明请见仓库根目录的 [../AGENT.md](../AGENT.md)；用户文档见 [../README.md](../README.md)。

---

## 1. 这是什么（以及它不是什么）

> ⚠️ **最容易搞混的一点**：`agents/` 与 `src/agent/` 是两个**互不相关**的体系。

| | `src/agent/` | `agents/`（本目录） |
|---|---|---|
| 定位 | 海关报关业务的**工作流编排** | 通用的**多智能体协作框架** |
| 入口 | `cli.py` → `AgentCoordinator` | `tools/extract_table.py`（仅用到 `table_extractor`） |
| 核心 | 六步固定流程（load→analyze→parse→validate→select→generate） | 思考-行动-观察循环、工具调用、多 Agent 协作 |
| 与报关业务 | 强耦合 | **无关**，是通用能力 |
| 在测试中 | 被 `tests/test_agent.py` 覆盖 | 被 `agents/tools/test_tools.py` 覆盖 |

两者唯一的交集：`agents/core/agent.py` 复用了 `src.utils.llm_client.LLMClient`
（即那个带缓存/JSON 校验/降级的 legacy 客户端），因此**它同样遵守 `LLM_BACKEND`**，
详见 [../AGENT.md 第 2 节](../AGENT.md)。

**当前实际使用情况**：本包绝大部分能力目前**未被 `cli.py` 或报关主流程调用**，
属于独立可用的框架代码。唯二的外部引用是：

- `tools/extract_table.py` → `agents.table_extractor`（可用）
- `agents/tools/test_tools.py` → 自测内置工具（pytest 会收集）

---

## 2. 目录结构

```
agents/
├── __init__.py              # 导出 Agent / AgentRunner / AgentManager / ToolRegistry / BaseTool
├── table_extractor.py       # ★ 表格提取 + HTML 对比视图（被 tools/extract_table.py 使用）
├── report_history.py        # 报关记录持久化(SQLite) + 统计 + 图表
├── core/
│   ├── agent.py             # Agent：思考-行动-观察循环，调用 LLM + 工具
│   ├── agent_runner.py      # AgentRunner（执行生命周期）+ BatchRunner（批量）
│   └── agent_manager.py     # AgentManager：多 Agent 协作（顺序/并行/主从/投票）
└── tools/
    ├── base_tool.py         # BaseTool / ToolParameter / ToolResult / @tool 装饰器
    ├── tool_registry.py     # ToolRegistry：全局单例注册表
    ├── test_tools.py        # 内置工具的自测（pytest 会收集，见 §6）
    └── builtin/
        ├── bash_tool.py     # BashTool
        ├── code_tool.py     # CodeExecutionTool / CodeAnalysisTool
        ├── file_tool.py     # FileReadTool / FileWriteTool / FileListTool
        ├── memory_tool.py   # MemoryReadTool / MemoryWriteTool
        ├── search_tool.py   # SearchTool / SearchSuggestionsTool
        └── web_tool.py      # WebFetchTool / WebSearchTool
```

---

## 3. 核心概念

### 3.1 `Agent`（`agents/core/agent.py`）

封装 LLM，按 **思考 → 行动 → 观察** 循环完成结构化任务。

```python
from agents import Agent
from src.utils.llm_client import get_llm_client

agent = Agent(
    name="分析助手",
    description="分析报表",
    tools=[],                       # BaseTool 实例或类
    llm_client=get_llm_client(),    # 可注入；默认走 get_llm_client()
    max_iterations=10,
    verbose=False,
)
response = agent.run("把这份报表分类")   # -> AgentResponse
```

关键类型：

- `AgentState`：`IDLE / RUNNING / PAUSED / COMPLETED / FAILED / THINKING / ACTING`
- `AgentResponse`：`thought` / `action` / `action_input` / `answer` / `success` / `error`
- `AgentMessage`：消息记录（含 `tool_call_id`、`tool_name`、`tool_output`）

**协议约定**：`Agent` 要求 LLM 返回固定 JSON（`thought` / `action` / `action_input` / `answer`），
由 `_build_system_prompt()` 自动注入该格式说明与工具清单。
因此**换成本地小模型时最容易出问题的点就是它不按 JSON 返回**——
legacy 客户端的 `call_with_retry(..., require_json=True)` 正是为此提供了 JSON 校验与重试。

**`context` 必须是可 JSON 序列化**：`agent.run(task, context)` 会把上下文
`json.dumps` 进消息，传入不可序列化对象（如 `MagicMock`）会抛
`Object type ... is not JSON serializable`。测试时请用真实的假对象而非 `MagicMock`。

### 3.2 `AgentRunner`（`agents/core/agent_runner.py`）

管理执行生命周期。

```python
from agents import AgentRunner
runner = AgentRunner(agent, timeout=60, enable_progress=False)
runner.run_sync("任务")                  # -> ExecutionResult
runner.run_async("任务", callback=cb)     # 后台线程执行
runner.wait(timeout=30)                  # 等待异步执行结束
runner.run_with_timeout("任务", timeout=15)
runner.stop(); runner.is_running(); runner.get_result()
```

- `ExecutionState`：`PENDING / RUNNING / PAUSED / COMPLETED / FAILED / CANCELLED`
- `ExecutionResult`：`state` / `output` / `error` / `execution_time` / `iterations` / `metadata`
- **测试时建议 `enable_progress=False`**，否则 rich 会向 stdout 输出大量面板

> 批量执行在**单独的 `BatchRunner` 类**中（同文件，未从 `agents/__init__.py` 导出）：
> ```python
> from agents.core.agent_runner import BatchRunner
> BatchRunner(agent, max_concurrent=4).run_batch([{"task": "...", "context": {...}}])
> ```
> 另提供 `get_summary()` / `export_results(filepath)`。

### 3.3 `AgentManager`（`agents/core/agent_manager.py`）

多 Agent 协作：`register_agent()` 注册，`CollaborationMode` 提供
`SEQUENTIAL / PARALLEL / MASTER_WORKER / VOTING` 四种模式。

---

## 4. 工具系统

### 4.1 编写一个工具

```python
from agents.tools.base_tool import BaseTool, ToolParameter

class MyTool(BaseTool):
    name = "my_tool"                    # 省略则按类名去掉 "Tool" 自动生成
    description = "做什么用的（会进 prompt）"
    parameters = [                      # ← 必须显式定义，见 4.2
        ToolParameter("x", "参数说明", "string", required=True),
    ]

    def execute(self, x: str) -> str:
        return f"结果: {x}"
```

`execute()` 返回裸值；基类会在 `run()` 中包装为 `ToolResult(success, output, error, metadata)`。

### 4.2 ⚠️ `parameters` 必须显式定义（基类默认值有缺陷）

`BaseTool.parameters` 使用了 `dataclasses.field(default_factory=list)`，但
`BaseTool` **不是 dataclass**，因此该默认值是一个 `Field` 对象而非列表：

```python
>>> from agents.tools.base_tool import BaseTool
>>> type(BaseTool.parameters)
<class 'dataclasses.Field'>
>>> # 若子类未覆盖 parameters，则：
>>> tool.validate_params(x=1)      # TypeError: 'Field' object is not iterable
```

**现状**：`builtin/` 下所有工具都显式定义了 `parameters`，因此该缺陷目前**潜伏未触发**。
**约定**：新工具务必自行声明 `parameters = [...]`，不要依赖基类默认值。
（这是一个可修的既有缺陷，但不在本次文档工作范围内。）

### 4.3 `ToolRegistry`（全局单例）

```python
from agents import ToolRegistry
ToolRegistry.register(MyTool(), "my_tool")   # 注册实例
ToolRegistry.register_class(MyTool)          # 注册类
ToolRegistry.get("my_tool")
ToolRegistry.list_tools(); ToolRegistry.get_all()
ToolRegistry.get_tool_schemas()              # 供 LLM function-calling 使用的 schema
ToolRegistry.remove("my_tool"); ToolRegistry.clear()
ToolRegistry.auto_discover("agents.tools.builtin")
```

注意 `ToolRegistry()` 是**单例**（`__new__` 实现），跨实例共享状态；
测试中请用 `clear()` 清理，避免相互污染。

### 4.4 内置工具与"孤儿"工具

`agents/tools/builtin/__init__.py` 实际导出的只有 7 个：

`BashTool`、`FileReadTool`、`FileWriteTool`、`MemoryReadTool`、`MemoryWriteTool`、
`WebFetchTool`、`WebSearchTool`

以下 5 个类**已实现但未在包的 `__init__` 中导出**，需按模块路径直接导入：

| 类 | 模块 |
|---|---|
| `CodeExecutionTool`、`CodeAnalysisTool` | `agents.tools.builtin.code_tool` |
| `SearchTool`、`SearchSuggestionsTool` | `agents.tools.builtin.search_tool` |
| `FileListTool` | `agents.tools.builtin.file_tool` |

它们的功能是完整的，只是没进命名空间——使用前请直接从模块导入，
或考虑补进 `__init__.py`。

### 4.5 存储位置（注意工作目录）

以下工具/模块使用**相对路径**，会写入当前工作目录，请留意：

| 组件 | 路径 |
|---|---|
| `MemoryReadTool` / `MemoryWriteTool` | `MEMORY.md` |
| `ReportHistory`（默认） | `report_history.db`（SQLite） |

`Config.TEMPLATE_DIR` 等目录在导入时自动创建；但上述两个文件不会，
也不在当前 `.gitignore` 覆盖范围内。新增运行时请勿提交到仓库。

---

## 5. 两个独立模块

### 5.1 `table_extractor.py`（当前唯一被外部使用的能力）

```python
from agents.table_extractor import TableExtractor, create_extraction_workflow

ext = TableExtractor()
result = ext.extract_from_pdf("报表.pdf", {"商品名称": "品名", ...})
ext.extract_from_excel("报表.xlsx", mapping, sheet_name=None)
ext.extract_from_word("报表.docx", mapping)
ext.extract_from_web("https://...", mapping, css_selector="table")
ext.generate_comparison_html(result, "out.html", max_rows=100)
```

- 支持 **PDF / Excel / Word / 网页**
- `ExtractionResult` 内含原文与提取值的**逐字段对比**（`_compare_values`）
- CLI 入口：`python tools/extract_table.py --input <文件|URL> [--mapping '{...}']`
  （可调参数见 `config/config.yaml`）

### 5.2 `report_history.py`

报关记录的 SQLite 持久化 + 统计 + 图表（`ReportHistory` / `ReportChartGenerator`）。

- `save_record()` / `save_multiple_records()` / `get_all_records()`
- `get_records_by_date_range()` / `export_to_csv()` / `get_statistics()`
- 统计：`get_trade_partners_stats(top_n)`、`get_product_category_stats(top_n)`、`get_trade_volume_trend(group_by)`
- 图表：`REPORT_CHART_GENERATOR` 生成趋势/伙伴/品类图（含 SVG 与 base64 输出）

---

## 6. 测试

```bash
# 本包自测（5 项）
python3 -m pytest agents/tools/test_tools.py -q

# 从仓库根跑全套：会一并收集本包的 test_tools.py
python3 -m pytest -q            # 77 passed / 7 skipped

# 只跑 tests/ 目录（不含本包）
python3 -m pytest tests/ -q     # 72 passed / 7 skipped
```

> ⚠️ 两个数字不同是正常的：`agents/tools/test_tools.py` 位于 `tests/` 之外，
> 因此 `pytest tests/` **不会**执行它。判断"全套是否通过"请从仓库根运行 `pytest`。

**已修复的两个既有缺陷**（如需追溯）：

1. ~~硬编码绝对路径~~：原第 4 行为
   `sys.path.insert(0, '/Users/shenqing/Desktop/custom_agent_project')`，
   在他人机器或 CI 上无效。已改为基于 `__file__` 计算：
   `PROJECT_ROOT = Path(__file__).resolve().parents[2]`。

2. ~~向仓库根写入副作用文件~~：`MemoryWriteTool` 使用相对路径，
   测试原先直接在仓库根创建 `MEMORY.md` 与 `memory/`，每跑一次测试就污染工作区。
   现已在临时目录中执行（`_temp_cwd()` 上下文管理器），并顺带修正了
   原先写入 `/tmp/test_file.txt`、读取 `/etc/hosts` 的不可移植写法。

此外，该文件原先的 5 个 "test" 函数**没有任何断言**（只要不抛异常就通过），
现已补充真实断言（记忆文件是否真的创建、注册表数量、移除后是否消失等），
并对断网环境保持宽容（网络工具在离线时仍应返回结果而非让测试失败）。

---

## 7. 修改本包时的注意事项

1. **别把 `agents/` 和 `src/agent/` 混为一谈**（见 §1）。改动前先确认目标属于哪一套。
2. **不要改动 `src.utils.llm_client` 的既有约定**：本包依赖其
   `call_with_retry(prompt, system, require_json)` 行为与返回值。详见 [../AGENT.md](../AGENT.md)。
3. **新工具必须显式声明 `parameters`**（见 §4.2）。
4. **注意相对路径副作用**：`MEMORY.md` 与 `report_history.db` 会落在 cwd。
5. **测试请用真实假对象而非 `MagicMock`**：`Agent.run(context=...)` 会做 JSON 序列化。
6. **`ToolRegistry` 是单例**：测试间需 `clear()` 以免污染。
7. 所有模块统一用 `setup_logger(__name__)`，与主项目一致。
8. 本包大量使用 `rich` 输出；非交互场景（CI、测试）请关闭 `verbose` / `enable_progress`。
