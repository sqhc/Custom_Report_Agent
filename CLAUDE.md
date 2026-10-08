# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> 📖 Full developer/AI-facing documentation is in [AGENT.md](AGENT.md). Read it before
> touching LLM code — it documents the dual-backend architecture and the constraints below.

## Project Overview

海关报关智能生成系统 - An AI-powered customs declaration document generation system that processes CSV data and generates Word/Excel reports using a local Ollama LLM **or any OpenAI-compatible remote API** (OpenAI, DeepSeek, Moonshot, vLLM, ...).

## Architecture

### Core Components

- **cli.py** - CLI entry point with `--input` (CSV file), `--output` (directory), `--config` (optional config file) and `--print-config` arguments
- **src/agent/** - AI orchestration layer:
  - `coordinator.py` - Main workflow orchestrator: load_file → analyze_data → parse_data → validate_data → select_template → generate_report
  - `reasoning.py` - `AIReasoner` (aliased as `Reasoner`); prompt-layer wrapper over a pluggable LLM client. Does **not** import `ollama` directly.
  - `llm_client.py` - `BaseLLMClient` / `OllamaClient` / `OpenAICompatibleClient` + `get_llm_client()` factory, selected by `Config.LLM_BACKEND`
  - `prompts.py` - Prompt templates for AI agents
- **src/utils/llm_client.py** - A **separate** legacy client used by `header_detector.py`, `description_extractor.py` and `agents/core/agent.py`. Adds JSON validation, on-disk cache and model fallback. It also honors `LLM_BACKEND`. Do not merge it with `src/agent/llm_client.py`.
- **src/utils/llm_errors.py** - `LLMConfigError` / `LLMClientError` / `LLMNotInstalledError`. **Must stay dependency-free** (no intra-project imports) to avoid circular imports.
- **src/data/** - Data handling:
  - `loader.py` - CSV/Excel file loading with pandas
  - `models.py` - Data models: `CustomsData`, `Product`
  - `validator.py` - Data validation (HS code format, required fields)
- **src/template/** - Document generation:
  - `engine.py` - `TemplateEngine` for Word (python-docx) and Excel (pandas/openpyxl) generation
- **src/utils/** - Utilities:
  - `config.py` - Configuration management (paths, Ollama **and** OpenAI-compatible settings, `validate_llm()`)
  - `logger.py` - Logging setup
  - `constants.py` - Constants including `CURRENCY_SYMBOLS`
- **agents/** - An unrelated generic agent framework (tool-calling loop). Only `agents/core/agent.py` reuses `src.utils.llm_client`.

### Data Flow

1. CLI receives input file path
2. `DataLoader` loads CSV/Excel into pandas DataFrame
3. `Reasoner` (AI) analyzes data structure and recommends report type
4. `DataParser` extracts and transforms data into `CustomsData` model
5. `DataValidator` validates HS codes, required fields, numeric values
6. `TemplateEngine` generates Word/Excel output

## LLM Backends

Switch with the `LLM_BACKEND` env var — `"ollama"` (default, unchanged legacy behavior) or `"openai"`:

```bash
# Local (default)
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_MODEL=qwen3.5:27b

# Remote (OpenAI-compatible)
export LLM_BACKEND=openai
export OPENAI_API_KEY=sk-xxxxxxxx
export OPENAI_BASE_URL=https://api.deepseek.com/v1
export OPENAI_MODEL=deepseek-chat
```

### Hard constraints

1. **Never `import openai` at module top level.** `src/utils/__init__.py` imports `llm_client`
   at package-import time, so a top-level import would break `import src.utils` for everyone
   without the `openai` package. Import it lazily inside `OpenAICompatibleClient` only.
2. `LLM_BACKEND=ollama` must remain a complete no-op path (full backward compatibility).
3. **Never change `AIReasoner`'s public signatures** — `coordinator.py` and `tests/test_agent.py`
   depend on them. Add aliases instead of renames (`Reasoner = AIReasoner`).
4. Env vars are read at **import time** into `Config` class attributes. Tests must patch
   `Config.X` directly (`os.environ` changes have no effect), then restore and call
   `reset_llm_client()`.
5. Mask secrets in all logs/output via `src.utils.config.mask_secret`.
6. `config/config.yaml` is **not** global config — only `tools/extract_table.py` reads it.

## Development Commands

### Run Test
```bash
python run_test.py                                     # needs tests/sample_data.csv
python3 -m pytest -q                                   # EVERYTHING (77 passed / 7 skipped)
python3 -m pytest tests/ -q                            # tests/ only (72 passed / 7 skipped)
python3 -m pytest tests/test_llm_client.py -v          # LLM unit tests (offline, no openai needed)
python3 -m pytest tests/test_llm_integration.py -v     # real openai SDK; auto-skips if not installed
python3 -m pytest agents/tools/test_tools.py -q        # agents/ framework self-test
```

> ✅ The suite is green (**0 failed**, ~1s). Tests use offline stubs and never require a
> running Ollama. `tests/test_data.py` and `tests/test_agent.py` write only to `tempfile`
> directories — they no longer touch tracked repo files.
>
> ⚠️ `pytest -q` (77) and `pytest tests/ -q` (72) differ because `agents/tools/test_tools.py`
> lives outside `tests/` and is only collected when pytest runs from the repo root.
> Use bare `pytest -q` to judge the full suite.

### Run Production
```bash
python cli.py --input /path/to/data.csv --output /path/to/output
python cli.py --print-config                            # API key is masked
```

### Install Dependencies
```bash
pip install -r requirements.txt
pip install "openai>=1.0.0"    # only needed for LLM_BACKEND=openai
```

### Key Dependencies
- `pandas` - Data loading/manipulation
- `python-docx` - Word document generation
- `openpyxl` - Excel generation
- `ollama` - Local LLM client
- `openai` - Remote OpenAI-compatible client (lazy-loaded)

## Key Patterns

- All components use structured logging via `setup_logger(__name__)`
- `Config` class centralizes paths: `BASE_DIR`, `OUTPUT_DIR`, `LOG_DIR`, `TEMPLATE_DIR`
- Ollama endpoint: `Config.OLLAMA_HOST` (default: `http://localhost:11434`)
- Local model: `Config.OLLAMA_MODEL` (default: `qwen3.5:27b`)
- Remote model: `Config.OPENAI_MODEL` (default: `gpt-4o`)
- Output files named as: `报关单_{exporter_short}_{timestamp}.docx`
- Remote retries: 429/5xx/timeouts retry up to `LLM_MAX_RETRIES`; 401/403/404/400 fail fast with the status code

## Known Issues

- python-docx namespace handling requires full XML namespace URI for `w:ascii` font attribute (use `r'{http://schemas.openxmlformats.org/wordprocessingml/2006/main}ascii'`)
- Ollama timeout: 120s configured in `Config.OLLAMA_TIMEOUT`
- `.llm_cache/` entries key on `model:prompt`, so switching backends reuses cache for identical model names — run `rm -rf .llm_cache/*` after switching
- **Test suite is fully green:** `python3 -m pytest -q` → **77 passed / 7 skipped / 0 failed**
  (~1s; `pytest tests/ -q` alone gives 72/7/0). The 7 skips are LLM integration tests
  (need `pip install "openai>=1.0.0"`). All tests run offline via stubs; none require a live
  Ollama server.
- `agents/` (the generic agent framework) has its own docs: **[agents/AGENT.md](agents/AGENT.md)**.
  Note its `BaseTool.parameters` base default is a broken `dataclasses.field` — every builtin
  tool overrides it, so always declare `parameters` explicitly in new tools.
