# Data Layer Documentation

This document describes the data storage, schema, and data flow for the PSX Stock Analysis Platform.

## Overview

The data layer provides:
- **SQLite database** for structured financial data
- **JSON cache** for quick access to latest scraped data
- **PDF parser tool** for extracting data from financial reports
- **Unified DataStore API** abstracting all storage operations

## Architecture

```
data/
├── db/
│   └── psx.db              # SQLite database
├── cache/
│   ├── {SYMBOL}/
│   │   └── latest.json     # Cached scraped data per company
│   └── pdfs/               # Cached PDF downloads
├── documents/              # Downloaded PDF reports
└── migrations/
    └── 001_initial_schema.sql
```

---

## Data Flow

### High-Level Architecture

```mermaid
flowchart TB
    subgraph External["External Sources"]
        PSX["PSX Website<br/>dps.psx.com.pk"]
        PDF["PDF Reports<br/>financials.psx.com.pk"]
    end

    subgraph Scraper["Scraper Layer"]
        SC["PSXScraper"]
        PP["PDFParser"]
    end

    subgraph Models["Data Models"]
        SD["ScrapedData"]
        PR["ParsedReport"]
    end

    subgraph Storage["Storage Layer"]
        DS["DataStore API"]
        DB[(SQLite DB)]
        JC["JSON Cache"]
        PC["PDF Cache"]
    end

    subgraph CLI["CLI Layer"]
        CMD["psx commands"]
    end

    PSX -->|"playwright"| SC
    PDF -->|"httpx"| PP
    SC --> SD
    PP --> PR
    SD --> DS
    PR --> DS
    DS --> DB
    DS --> JC
    PP --> PC
    CMD --> SC
    CMD --> PP
    CMD --> DS
```

### Scraping Data Flow

```mermaid
sequenceDiagram
    participant CLI as psx scrape
    participant Scraper as PSXScraper
    participant PSX as PSX Website
    participant Store as DataStore
    participant DB as SQLite
    participant Cache as JSON Cache

    CLI->>Scraper: scrape_company(symbol)
    Scraper->>PSX: GET /company/{symbol}
    PSX-->>Scraper: HTML Page

    Note over Scraper: Extract quote data
    Note over Scraper: Extract company info
    Note over Scraper: Extract financials
    Note over Scraper: Extract ratios
    Note over Scraper: Extract announcements
    Note over Scraper: Extract reports

    Scraper-->>CLI: ScrapedData

    CLI->>Store: save_company(data.company)
    Store->>DB: INSERT INTO companies
    DB-->>Store: company_id

    CLI->>Store: save_quote(company_id, quote)
    Store->>DB: INSERT INTO quotes

    CLI->>Store: save_financials(company_id, rows)
    Store->>DB: INSERT INTO financials

    CLI->>Store: save_ratios(company_id, rows)
    Store->>DB: INSERT INTO ratios

    CLI->>Store: save_announcement(company_id, ann)
    Store->>DB: INSERT INTO announcements

    CLI->>Store: save_report(company_id, report)
    Store->>DB: INSERT INTO reports

    CLI->>Store: save_cache(symbol, data)
    Store->>Cache: Write latest.json

    CLI->>Store: log_scrape(symbol, status)
    Store->>DB: INSERT INTO scrape_log
```

### PDF Parsing Data Flow

```mermaid
sequenceDiagram
    participant CLI as psx parse-pdf
    participant Parser as PDFParser
    participant PDFSrc as PDF Source
    participant Cache as PDF Cache

    CLI->>Parser: parse_from_url(url)

    alt Cached
        Parser->>Cache: Check cache
        Cache-->>Parser: PDF bytes
    else Not Cached
        Parser->>PDFSrc: GET PDF
        PDFSrc-->>Parser: PDF bytes
        Parser->>Cache: Save to cache
    end

    Note over Parser: Extract text (pdfplumber)
    Note over Parser: Identify sections
    Note over Parser: Extract line items
    Note over Parser: Build ParsedReport

    Parser-->>CLI: ParsedReport

    alt --text flag
        CLI->>CLI: Output raw text
    else --llm flag
        CLI->>CLI: Output LLM-formatted text
    else default
        CLI->>CLI: Output sections summary
    end
```

### Data Model Mapping

```mermaid
flowchart LR
    subgraph PSX["PSX Website Sections"]
        Q["Quote Panel"]
        P["Profile Tab"]
        E["Equity Stats"]
        F["Financials Tab"]
        R["Ratios Tab"]
        A["Announcements Tab"]
        D["Reports Tab"]
    end

    subgraph Models["Data Models"]
        QD["QuoteData"]
        CD["CompanyData"]
        ED["EquityData"]
        FR["FinancialRow[]"]
        RR["RatioRow[]"]
        AD["AnnouncementData[]"]
        RD["ReportData[]"]
    end

    subgraph Tables["Database Tables"]
        TQ["quotes"]
        TC["companies"]
        TF["financials"]
        TR["ratios"]
        TA["announcements"]
        TP["reports"]
    end

    Q --> QD --> TQ
    P --> CD --> TC
    E --> ED --> TQ
    F --> FR --> TF
    R --> RR --> TR
    A --> AD --> TA
    D --> RD --> TP
```

---

## Database Schema

### Entity Relationship Diagram

```mermaid
erDiagram
    companies ||--o{ quotes : "has"
    companies ||--o{ financials : "has"
    companies ||--o{ ratios : "has"
    companies ||--o{ announcements : "has"
    companies ||--o{ reports : "has"
    companies ||--o{ dividends : "has"
    companies ||--o{ scrape_log : "logs"

    companies {
        int id PK
        text symbol UK
        text name
        text sector
        text description
        text ceo
        text chairperson
        text company_secretary
        text auditor
        text registrar
        text fiscal_year_end
        text website
        text address
        timestamp created_at
        timestamp updated_at
    }

    quotes {
        int id PK
        int company_id FK
        date date
        real price
        real change
        real change_pct
        real open
        real high
        real low
        int volume
        real ldcp
        real week_52_high
        real week_52_low
        real pe_ratio
        real ytd_change_pct
        real year_change_pct
        real market_cap
        int shares_outstanding
        int free_float_shares
        real free_float_pct
        timestamp created_at
    }

    financials {
        int id PK
        int company_id FK
        text period
        text period_type
        text metric
        real value
        text raw_value
        timestamp created_at
    }

    ratios {
        int id PK
        int company_id FK
        text period
        text metric
        real value
        text raw_value
        timestamp created_at
    }

    announcements {
        int id PK
        int company_id FK
        date date
        text title
        text category
        text url
        text content_hash
        timestamp created_at
    }

    reports {
        int id PK
        int company_id FK
        text report_type
        text period
        text url
        text local_path
        text text_path
        bool is_downloaded
        bool is_parsed
        int page_count
        timestamp created_at
    }

    dividends {
        int id PK
        int company_id FK
        date announcement_date
        date ex_date
        date record_date
        date payment_date
        text dividend_type
        real amount
        real percentage
        timestamp created_at
    }

    scrape_log {
        int id PK
        int company_id FK
        text symbol
        text source_url
        text status
        text error_message
        int duration_ms
        timestamp scraped_at
    }

    schema_version {
        int version PK
        timestamp applied_at
    }
```

### Table Descriptions

#### Core Tables

| Table | Purpose | Key Constraints |
|-------|---------|-----------------|
| `companies` | Company master data | `symbol` is unique |
| `quotes` | Daily market prices | Unique on `(company_id, date)` |
| `financials` | Financial statement metrics | Unique on `(company_id, period, period_type, metric)` |
| `ratios` | Financial ratios | Unique on `(company_id, period, metric)` |

#### Document Tables

| Table | Purpose | Key Constraints |
|-------|---------|-----------------|
| `announcements` | Company announcements | Deduplicated by `content_hash` |
| `reports` | PDF report metadata | Unique on `(company_id, report_type, period)` |
| `dividends` | Dividend history | None (allows duplicates) |

#### System Tables

| Table | Purpose |
|-------|---------|
| `scrape_log` | Audit trail for scrape operations |
| `schema_version` | Database migration tracking |

### Indexes

```sql
-- Company lookups
CREATE INDEX idx_companies_symbol ON companies(symbol);
CREATE INDEX idx_companies_sector ON companies(sector);

-- Quote queries
CREATE INDEX idx_quotes_date ON quotes(date);
CREATE INDEX idx_quotes_company_date ON quotes(company_id, date);

-- Financial queries
CREATE INDEX idx_financials_company ON financials(company_id);
CREATE INDEX idx_financials_period ON financials(period, period_type);
CREATE INDEX idx_financials_metric ON financials(metric);

-- Ratio queries
CREATE INDEX idx_ratios_company ON ratios(company_id);
CREATE INDEX idx_ratios_metric ON ratios(metric);

-- Announcement queries
CREATE INDEX idx_announcements_company ON announcements(company_id);
CREATE INDEX idx_announcements_date ON announcements(date);
CREATE INDEX idx_announcements_category ON announcements(category);

-- Report queries
CREATE INDEX idx_reports_company ON reports(company_id);
CREATE INDEX idx_reports_type ON reports(report_type);

-- Dividend queries
CREATE INDEX idx_dividends_company ON dividends(company_id);
```

### Unique Constraints

| Table | Constraint | Purpose |
|-------|------------|---------|
| `companies` | `symbol` | One record per stock symbol |
| `quotes` | `(company_id, date)` | One quote per company per day |
| `financials` | `(company_id, period, period_type, metric)` | One value per metric per period |
| `ratios` | `(company_id, period, metric)` | One ratio value per period |
| `announcements` | `(company_id, content_hash)` | Deduplication |
| `reports` | `(company_id, report_type, period)` | One report per type per period |

---

## Components

### 1. Database (`src/psx/storage/database.py`)

Low-level SQLite connection and migration management.

```python
from psx.storage.database import Database, init_database

# Initialize database with migrations
db = init_database("data/db/psx.db", "data/migrations")

# Execute queries
cursor = db.execute("SELECT * FROM companies WHERE symbol = ?", ("LSECL",))
row = cursor.fetchone()

# Close when done
db.close()
```

**Key Methods:**
- `connection` - Lazy connection property
- `execute(sql, params)` - Execute single query
- `executemany(sql, params_list)` - Batch operations
- `commit()` / `rollback()` - Transaction control
- `get_schema_version()` - Current migration version
- `run_migrations(dir)` - Apply pending migrations

### 2. DataStore (`src/psx/storage/data_store.py`)

Unified API for all data operations. Use this instead of direct database access.

```python
from psx.storage.data_store import DataStore
from psx.core.models import CompanyData, QuoteData

store = DataStore()

# Save company
company = CompanyData(symbol="TEST", name="Test Corp", sector="Tech")
company_id = store.save_company(company)

# Save quote
quote = QuoteData(price=10.50, change=0.25, volume=1000000)
store.save_quote(company_id, quote)

# Get data
company = store.get_company("TEST")
latest_quote = store.get_latest_quote("TEST")
financials = store.get_financials("TEST", period_type="annual")
```

### 3. PDF Parser (`src/psx/tools/pdf_parser.py`)

Agent-callable tool for extracting data from PSX financial report PDFs.

```python
from psx.tools.pdf_parser import PDFParser

parser = PDFParser(cache_dir="data/cache/pdfs")

# Parse from URL
report = await parser.parse_from_url("https://dps.psx.com.pk/download/document/265412.pdf")

# Access parsed data
print(f"Pages: {report.pages}")
print(f"Sections: {list(report.sections.keys())}")
print(f"Text: {report.raw_text[:1000]}")

# Get LLM-formatted text
llm_text = parser.get_text_for_llm(report, max_chars=50000)

# Extract line items
balance_sheet = report.sections.get("balance_sheet")
if balance_sheet:
    items = parser.extract_line_items(balance_sheet.raw_text)
    print(f"Total Assets: {items.get('total_assets')}")
```

**CLI Usage:**
```bash
# Parse and show sections
psx parse-pdf https://dps.psx.com.pk/download/document/265412.pdf

# Get raw text
psx parse-pdf <url> --text --max-chars 5000

# Get LLM-formatted output
psx parse-pdf <url> --llm
```

### 4. Number Parsers (`src/psx/utils/parsers.py`)

Utilities for converting PSX formatted strings to machine-readable values.

```python
from psx.utils.parsers import (
    parse_price,      # "Rs.5.17" -> 5.17
    parse_number,     # "1,873,125.59" -> 1873125.59
    parse_negative,   # "(9,235)" -> -9235.0
    parse_percent,    # "-9.14%" -> -9.14
    parse_date,       # "Nov 10, 2025" -> "2025-11-10"
    parse_volume,     # "18,570,325" -> 18570325
)
```

---

## Data Models

All models are defined in `src/psx/core/models.py` as dataclasses:

```python
@dataclass
class QuoteData:
    price: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[int] = None
    pe_ratio: Optional[float] = None
    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None
    # ... more fields

@dataclass
class CompanyData:
    symbol: str
    name: Optional[str] = None
    sector: Optional[str] = None
    ceo: Optional[str] = None
    auditor: Optional[str] = None
    # ... more fields

@dataclass
class FinancialRow:
    period: str           # "2025", "Q1 2025"
    period_type: str      # "annual", "quarterly"
    metric: str           # "Revenue", "Profit after Tax"
    value: Optional[float] = None
    raw_value: Optional[str] = None

@dataclass
class ScrapedData:
    symbol: str
    scraped_at: str
    quote: Optional[QuoteData] = None
    company: Optional[CompanyData] = None
    financials: Dict[str, List[FinancialRow]] = field(default_factory=dict)
    # ... more fields
```

---

## Common Operations

### Save Scraped Data

```python
from psx.storage.data_store import DataStore
from psx.scraper import PSXScraper

scraper = PSXScraper()
store = DataStore()

# Scrape
data = await scraper.scrape_company("LSECL")

# Save to database
company_id = store.save_company(data.company)
store.save_quote(company_id, data.quote, data.equity)
store.save_financials(company_id, data.financials.get("annual", []))
store.save_ratios(company_id, data.ratios)

# Save to JSON cache
store.save_cache("LSECL", data)
```

### Query Financial Data

```python
# Get all annual financials
annual = store.get_financials("LSECL", period_type="annual")

# Get specific metrics
eps_data = store.get_financials("LSECL", metrics=["EPS", "Profit after Taxation"])

# Get sector averages for comparison
averages = store.get_sector_averages("Technology")
print(f"Sector avg P/E: {averages['avg_pe']}")
```

### Get Announcements with Filters

```python
# Financial results only
results = store.get_announcements("LSECL", category="financial_results")

# Date range
recent = store.get_announcements(
    "LSECL",
    start_date="2025-01-01",
    end_date="2025-12-31",
    limit=50
)
```

---

## Storage Locations

```mermaid
flowchart TB
    subgraph Data["data/"]
        subgraph DB["db/"]
            SQLITE["psx.db"]
        end
        subgraph Cache["cache/"]
            SC["SYMBOL/latest.json"]
            PC["pdfs/*.pdf"]
        end
        subgraph Docs["documents/"]
            DL["Downloaded PDFs"]
        end
        subgraph Mig["migrations/"]
            SQL["*.sql files"]
        end
    end

    SQLITE --- |"Structured data"| Tables
    SC --- |"Quick access"| JSON
    PC --- |"PDF cache"| PDFs

    subgraph Tables["Tables"]
        T1["companies"]
        T2["quotes"]
        T3["financials"]
        T4["ratios"]
        T5["announcements"]
        T6["reports"]
    end

    subgraph JSON["JSON Structure"]
        J1["_meta"]
        J2["quote"]
        J3["company"]
        J4["financials"]
        J5["ratios"]
        J6["announcements"]
    end

    subgraph PDFs["Cached PDFs"]
        P1["265412.pdf"]
        P2["264877.pdf"]
    end
```

---

## Component Dependencies

```mermaid
flowchart BT
    subgraph Core["psx.core"]
        Models["models.py"]
        Exceptions["exceptions.py"]
    end

    subgraph Utils["psx.utils"]
        Parsers["parsers.py"]
    end

    subgraph Storage["psx.storage"]
        Database["database.py"]
        DataStore["data_store.py"]
    end

    subgraph Scraper["psx.scraper"]
        PSXScraper["psx_scraper.py"]
        Selectors["selectors.py"]
    end

    subgraph Tools["psx.tools"]
        PDFParser["pdf_parser.py"]
    end

    subgraph CLI["psx.cli"]
        Main["main.py"]
    end

    Models --> DataStore
    Models --> PSXScraper
    Exceptions --> Database
    Exceptions --> PDFParser
    Parsers --> PSXScraper
    Database --> DataStore
    DataStore --> Main
    PSXScraper --> Main
    PDFParser --> Main
    Selectors --> PSXScraper
```

---

## Migrations

Migrations are SQL files in `data/migrations/` with format `NNN_description.sql`.

To add a new migration:
1. Create `data/migrations/002_add_feature.sql`
2. Include schema changes
3. Update `schema_version` table
4. Run application - migrations apply automatically

Example migration:
```sql
-- Migration 002: Add sentiment table
CREATE TABLE IF NOT EXISTS sentiment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    date DATE NOT NULL,
    score REAL,
    source TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

INSERT OR IGNORE INTO schema_version (version) VALUES (2);
```

---

## Testing

Run data layer tests:

```bash
# All tests
uv run pytest tests/ -v

# Specific test files
uv run pytest tests/test_database.py -v
uv run pytest tests/test_data_store.py -v
uv run pytest tests/test_pdf_parser.py -v
uv run pytest tests/test_parsers.py -v
```

---

## File Locations

| Component | Location |
|-----------|----------|
| Database module | `src/psx/storage/database.py` |
| DataStore API | `src/psx/storage/data_store.py` |
| PDF Parser | `src/psx/tools/pdf_parser.py` |
| Number parsers | `src/psx/utils/parsers.py` |
| Data models | `src/psx/core/models.py` |
| Exceptions | `src/psx/core/exceptions.py` |
| Schema migration | `data/migrations/001_initial_schema.sql` |
| Tests | `tests/test_*.py` |
