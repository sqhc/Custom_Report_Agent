# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

海关报关智能生成系统 - An AI-powered customs declaration document generation system that processes CSV data and generates Word/Excel reports using Ollama (local LLM).

## Architecture

### Core Components

- **cli.py** - CLI entry point with `--input` (CSV file), `--output` (directory), and `--config` (optional config file) arguments
- **src/agent/** - AI orchestration layer:
  - `coordinator.py` - Main workflow orchestrator: load_file → analyze_data → parse_data → validate_data → select_template → generate_report
  - `reasoning.py` - Ollama client for LLM interactions (model configurable via `Config.OLLAMA_MODEL`)
  - `prompts.py` - Prompt templates for AI agents
- **src/data/** - Data handling:
  - `loader.py` - CSV/Excel file loading with pandas
  - `models.py` - Data models: `CustomsData`, `Product`
  - `validator.py` - Data validation (HS code format, required fields)
- **src/template/** - Document generation:
  - `engine.py` - `TemplateEngine` for Word (python-docx) and Excel (pandas/openpyxl) generation
- **src/utils/** - Utilities:
  - `config.py` - Configuration management (paths, Ollama settings)
  - `logger.py` - Logging setup
  - `constants.py` - Constants including `CURRENCY_SYMBOLS`

### Data Flow

1. CLI receives input file path
2. `DataLoader` loads CSV/Excel into pandas DataFrame
3. `Reasoner` (AI) analyzes data structure and recommends report type
4. `DataParser` extracts and transforms data into `CustomsData` model
5. `DataValidator` validates HS codes, required fields, numeric values
6. `TemplateEngine` generates Word/Excel output

## Development Commands

### Run Test
```bash
python run_test.py
```
Uses test data in `tests/sample_data.csv`, outputs to `output/` directory.

### Run Production
```bash
python cli.py --input /path/to/data.csv --output /path/to/output
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Key Dependencies
- `pandas` - Data loading/manipulation
- `python-docx` - Word document generation
- `openpyxl` - Excel generation
- `ollama` - Local LLM client

## Key Patterns

- All components use structured logging via `setup_logger(__name__)`
- `Config` class centralizes paths: `BASE_DIR`, `OUTPUT_DIR`, `LOG_DIR`, `TEMPLATE_DIR`
- Ollama endpoint: `Config.OLLAMA_HOST` (default: `http://localhost:11434`)
- AI model: `Config.OLLAMA_MODEL` (default: `qwen3.5:27b`)
- Output files named as: `报关单_{exporter_short}_{timestamp}.docx`

## Known Issues

- python-docx namespace handling requires full XML namespace URI for `w:ascii` font attribute (use `r'{http://schemas.openxmlformats.org/wordprocessingml/2006/main}ascii'`)
- Ollama timeout: 120s configured in `Config.OLLAMA_TIMEOUT`
