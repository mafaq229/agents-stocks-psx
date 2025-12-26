# PSX Stock Scraper

A web scraper for Pakistan Stock Exchange (PSX) company data.

## Setup

```bash
# Initialize and create virtual environment
uv init --python 3.11
uv venv --python 3.11

# Install dependencies
uv add playwright

# Install Chromium browser for Playwright
uv run playwright install chromium
```

## Usage

```bash
uv run python main.py <SYMBOL>
```

Example:
```bash
uv run python main.py LSECL
```
