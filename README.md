# Multi-Agent Financial Analysis Framework (PSX)

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
# Analyze a stock (recommended: markdown output)
uv run psx analyze OGDC --output markdown

# Natural language query
uv run psx analyze "Should I buy PPL?" --output markdown

# Quick summary view (default)
uv run psx analyze LSECL

# JSON output for programmatic use
uv run psx analyze LSECL --output json

# Verbose mode (detailed logs saved to logs/)
uv run psx analyze LSECL --output markdown --verbose
```

Reports are automatically saved to `output/` directory.

## Example Output

<details>
<summary><b>CLI Analysis Output</b> (click to expand)</summary>

```
$ uv run psx analyze OGDC --output markdown

================================================================================
                         OGDC INVESTMENT ANALYSIS
================================================================================
Generated: 2025-01-15 14:32:45

FINANCIAL SNAPSHOT
------------------
Current Price:      PKR 142.50
Market Cap:         PKR 385.2B
P/E Ratio:          8.2x (Sector avg: 12.1x)
P/B Ratio:          1.1x
Dividend Yield:     4.8%
52-Week Range:      PKR 98.50 - PKR 168.00

VALUATION ANALYSIS
------------------
| Method          | Fair Value  | Upside   |
|-----------------|-------------|----------|
| P/E Valuation   | PKR 178.00  | +24.9%   |
| Graham Number   | PKR 165.50  | +16.1%   |
| Book Value      | PKR 158.20  | +11.0%   |
| DCF Analysis    | PKR 192.00  | +34.7%   |
|-----------------|-------------|----------|
| Composite       | PKR 173.43  | +21.7%   |

RECOMMENDATION: BUY
Confidence: Medium (0.72)
Health Score: 78/100

KEY STRENGTHS
- Strong dividend yield (4.8%)
- Trading below sector P/E average
- Healthy current ratio (1.85)
- Consistent dividend history

RED FLAGS
- Revenue decline (-8.2% YoY)
- Elevated debt-to-equity (1.4x)
- Declining production volumes

RECENT NEWS & EVENTS
- [2025-01-12] Q2 FY25 earnings beat estimates by 8%
- [2025-01-08] New gas discovery announced in Block 27
- [2025-01-05] Board approves interim dividend of PKR 3.50

================================================================================
Analysis complete. Tokens: 12,847 | Cost: $0.08 | Time: 34.2s
================================================================================
```

</details>

<details>
<summary><b>JSON Output Structure</b> (click to expand)</summary>

```json
{
  "symbol": "OGDC",
  "generated_at": "2025-01-15T14:32:45",
  "financial_snapshot": {
    "current_price": 142.50,
    "market_cap": 385200000000,
    "pe_ratio": 8.2,
    "pb_ratio": 1.1,
    "dividend_yield": 4.8
  },
  "valuations": [
    {"method": "pe", "fair_value": 178.00, "upside_pct": 24.9},
    {"method": "graham", "fair_value": 165.50, "upside_pct": 16.1},
    {"method": "book_value", "fair_value": 158.20, "upside_pct": 11.0},
    {"method": "dcf", "fair_value": 192.00, "upside_pct": 34.7}
  ],
  "composite_fair_value": 173.43,
  "recommendation": "BUY",
  "confidence": 0.72,
  "health_score": 78,
  "strengths": [
    "Strong dividend yield (4.8%)",
    "Trading below sector P/E average"
  ],
  "red_flags": [
    "Revenue decline (-8.2% YoY)",
    "Elevated debt-to-equity (1.4x)"
  ],
  "news_items": [
    {
      "date": "2025-01-12",
      "title": "Q2 FY25 earnings beat estimates by 8%",
      "source": "Business Recorder"
    }
  ],
  "metrics": {
    "tokens_used": 12847,
    "cost_usd": 0.08,
    "latency_seconds": 34.2
  }
}
```

</details>

## How It Works

```
User Query ──> SupervisorAgent ──┬──> DataAgent ────> Scrape PSX website
                                 │                    Fetch from database
                                 │
                                 ├──> ResearchAgent ─> Web search (Tavily)
                                 │                     Parse PDF reports
                                 │
                                 └──> AnalystAgent ──> Calculate valuations
                                                       Generate recommendation
                                                            │
                                                            v
                                                    Final Analysis Report
```

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

## Evaluation

The project includes an evaluation framework to measure component accuracy:

```bash
# Run all evaluations
uv run python -m evaluation.run_evals --all

# Run specific evaluator
uv run python -m evaluation.run_evals --eval data_agent --verbose

# Generate markdown report
uv run python -m evaluation.run_evals --all --markdown
```

### Evaluation Results

| Component | Metric | Target |
|-----------|--------|--------|
| DataAgent | Data completeness | >90% |
| DataAgent | Field extraction accuracy | >95% |
| AnalystAgent | Recommendation validity | 100% |
| AnalystAgent | Valuation calculation | >85% |
| ResearchAgent | News relevance | >80% |
| PDFParser | Section detection | >85% |
| Scraper | Selector success rate | >95% |

*Run `uv run python -m evaluation.run_evals --all` to generate actual results.*

## Documentation

- [Data Layer](docs/DATA_LAYER.md) - Database schema, storage, and data flow
- [Agent Layer](docs/AGENT_LAYER.md) - Multi-agent architecture and workflow

## Development

```bash
# Install dev dependencies
uv sync --group dev

# Run tests
uv run pytest tests/ -v

# Run linter
uv run ruff check src/ tests/

# Run type checker
uv run mypy src/psx
```

## Docker

### Build and Run

```bash
# Build image
docker build -t psx-agents .

# Run analysis
docker run -e OPENAI_API_KEY=$OPENAI_API_KEY psx-agents analyze OGDC

# Run with persistent data
docker run -v $(pwd)/data:/app/data \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  psx-agents analyze OGDC --output markdown
```

### Docker Compose

```bash
# Copy environment template
cp .env.example .env
# Edit .env with your API keys

# Run analysis
docker-compose run psx analyze OGDC

# Scrape company data
docker-compose run psx scrape OGDC ENGRO

# List companies
docker-compose run psx list
```
