# PSX Stock Analysis Platform

A **multi-agent AI framework** for fundamental analysis and stock valuation on Pakistan Stock Exchange (PSX). Built with a modular architecture where specialized agents collaborate to deliver comprehensive investment analysis.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     SupervisorAgent                          │
│                    (Orchestrator)                            │
└─────────────────────┬───────────────────────────────────────┘
                      │
      ┌───────────────┼───────────────┐
      ▼               ▼               ▼
┌───────────┐   ┌───────────┐   ┌───────────┐
│ DataAgent │   │ Research  │   │  Analyst  │
│           │   │   Agent   │   │   Agent   │
├───────────┤   ├───────────┤   ├───────────┤
│• Scraper  │   │• PDF Parse│   │• DCF      │
│• Database │   │• News     │   │• Graham   │
│• Peers    │   │• Reports  │   │• P/E      │
└───────────┘   └───────────┘   └───────────┘
```

**Key Design Decisions:**
- **Tool Results Direct Access** - DataAgent extracts data directly from tool results, bypassing LLM output parsing for efficiency
- **Parallel Tool Execution** - ResearchAgent batches PDF and news searches in single LLM turns
- **Context Passing** - Each agent's output becomes context for the next, enabling informed analysis

## Features

- **Multi-Agent Analysis** - Specialized agents (Data, Research, Analyst) coordinated by a Supervisor
- **Web Scraping** - Playwright-based data collection from PSX (quotes, financials, ratios, announcements)
- **PDF Parsing** - LLM-powered extraction from financial reports
- **SQLite Database** - Structured storage with full query support
- **JSON Cache** - Quick access to latest scraped data
- **CLI Interface** - Simple commands for scraping, analysis, and comparison

## Setup

```bash
# Clone the repository
git clone <repo-url>
cd stocks-psx

# Create virtual environment with Python 3.11
uv venv --python 3.11

# Install dependencies
uv sync

# Install Chromium browser for Playwright
uv run playwright install chromium
```

## Usage

### Scrape Company Data

```bash
# Scrape a single company
uv run psx scrape LSECL

# Scrape multiple companies
uv run psx scrape LSECL ENGRO LUCK

# Run browser in visible mode (for debugging)
uv run psx scrape LSECL --no-headless
```

### List Scraped Companies

```bash
uv run psx list
```

### Show Company Data

```bash
uv run psx show LSECL
```

### Parse Financial Report PDFs

```bash
# Parse PDF from URL
uv run psx parse-pdf https://dps.psx.com.pk/download/document/265412.pdf

# Output raw text
uv run psx parse-pdf <url> --text --max-chars 5000

# Output LLM-formatted text (for AI analysis)
uv run psx parse-pdf <url> --llm
```

### Multi-Agent Analysis

Requires `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` environment variable.

```bash
# Analyze a single stock
uv run psx analyze LSECL

# Natural language query
uv run psx analyze "Should I buy OGDC?"

# Output formats
uv run psx analyze LSECL --output json
uv run psx analyze LSECL --output markdown

# Verbose mode (detailed logs saved to logs/)
uv run psx analyze LSECL --verbose
```

### Compare Multiple Stocks

```bash
# Compare 2-5 stocks
uv run psx compare OGDC PPL MARI

# With output format
uv run psx compare LSECL GHNI --output markdown --verbose
```

Reports are automatically saved to `output/` directory.

## Environment Variables

```bash
# LLM API Keys (at least one required for analysis)
export OPENAI_API_KEY=sk-...           # For GPT-4 models
export ANTHROPIC_API_KEY=sk-ant-...    # For Claude models

# Optional
export TAVILY_API_KEY=tvly-...         # For web search in Research Agent
export PSX_LLM_PROVIDER=openai         # Force specific provider
export PSX_LLM_MODEL=gpt-5.1           # Override default model
```

## Project Structure

```
stocks-psx/
├── src/psx/                 # Main package
│   ├── cli/                 # Command-line interface
│   ├── core/                # Models and exceptions
│   ├── scraper/             # Web scraping logic
│   ├── storage/             # Database and data store
│   ├── tools/               # PDF parser, calculator, web search
│   ├── agents/              # Multi-agent system
│   │   ├── supervisor.py    # Orchestrator agent
│   │   ├── data_agent.py    # Data retrieval agent
│   │   ├── analyst_agent.py # Financial analysis agent
│   │   └── research_agent.py # News and PDF research agent
│   └── utils/               # Parsing utilities
├── data/
│   ├── db/                  # SQLite database
│   ├── cache/               # JSON cache per company
│   ├── documents/           # Downloaded PDFs
│   └── migrations/          # Database migrations
├── output/                  # Analysis reports (auto-generated)
├── logs/                    # Verbose logs (auto-generated)
├── tests/                   # Test suite
└── docs/                    # Documentation
```

## Data Storage

- **SQLite Database**: `data/db/psx.db` - Structured financial data
- **JSON Cache**: `data/cache/{SYMBOL}/latest.json` - Quick access to latest scrape
- **PDF Cache**: `data/cache/pdfs/` - Cached PDF downloads
- **Analysis Output**: `output/` - Saved analysis reports (JSON/Markdown)
- **Logs**: `logs/` - Verbose debug logs

## Documentation

- [Data Layer](docs/DATA_LAYER.md) - Database schema, storage, and data flow
- [Agent Layer](docs/AGENT_LAYER.md) - Multi-agent architecture and workflow

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_parsers.py -v
```

## License

MIT
