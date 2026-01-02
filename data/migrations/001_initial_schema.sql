-- PSX Stock Analysis Platform - Initial Schema
-- Migration 001: Create core tables

-- Company reference data
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT UNIQUE NOT NULL,
    name TEXT,
    sector TEXT,
    description TEXT,
    ceo TEXT,
    chairperson TEXT,
    company_secretary TEXT,
    auditor TEXT,
    registrar TEXT,
    fiscal_year_end TEXT,
    website TEXT,
    address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_companies_sector ON companies(sector);
CREATE INDEX IF NOT EXISTS idx_companies_symbol ON companies(symbol);

-- Daily market data (append-only)
CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    date DATE NOT NULL,
    price REAL,
    change REAL,
    change_pct REAL,
    open REAL,
    high REAL,
    low REAL,
    volume INTEGER,
    ldcp REAL,
    week_52_high REAL,
    week_52_low REAL,
    pe_ratio REAL,
    ytd_change_pct REAL,
    year_change_pct REAL,
    market_cap REAL,
    shares_outstanding INTEGER,
    free_float_shares INTEGER,
    free_float_pct REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id),
    UNIQUE(company_id, date)
);

CREATE INDEX IF NOT EXISTS idx_quotes_date ON quotes(date);
CREATE INDEX IF NOT EXISTS idx_quotes_company_date ON quotes(company_id, date);

-- Financial statements (quarterly/annual)
CREATE TABLE IF NOT EXISTS financials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    period TEXT NOT NULL,
    period_type TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL,
    raw_value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id),
    UNIQUE(company_id, period, period_type, metric)
);

CREATE INDEX IF NOT EXISTS idx_financials_company ON financials(company_id);
CREATE INDEX IF NOT EXISTS idx_financials_period ON financials(period, period_type);
CREATE INDEX IF NOT EXISTS idx_financials_metric ON financials(metric);

-- Financial ratios
CREATE TABLE IF NOT EXISTS ratios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    period TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL,
    raw_value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id),
    UNIQUE(company_id, period, metric)
);

CREATE INDEX IF NOT EXISTS idx_ratios_company ON ratios(company_id);
CREATE INDEX IF NOT EXISTS idx_ratios_metric ON ratios(metric);

-- Announcements (append-only, deduplicated)
CREATE TABLE IF NOT EXISTS announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    date DATE NOT NULL,
    title TEXT NOT NULL,
    category TEXT,
    url TEXT,
    content_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id),
    UNIQUE(company_id, content_hash)
);

CREATE INDEX IF NOT EXISTS idx_announcements_company ON announcements(company_id);
CREATE INDEX IF NOT EXISTS idx_announcements_date ON announcements(date);
CREATE INDEX IF NOT EXISTS idx_announcements_category ON announcements(category);

-- Financial reports (PDFs)
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    report_type TEXT NOT NULL,
    period TEXT NOT NULL,
    url TEXT NOT NULL,
    local_path TEXT,
    text_path TEXT,
    is_downloaded BOOLEAN DEFAULT FALSE,
    is_parsed BOOLEAN DEFAULT FALSE,
    page_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id),
    UNIQUE(company_id, report_type, period)
);

CREATE INDEX IF NOT EXISTS idx_reports_company ON reports(company_id);
CREATE INDEX IF NOT EXISTS idx_reports_type ON reports(report_type);

-- Dividends/Payouts
CREATE TABLE IF NOT EXISTS dividends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    announcement_date DATE,
    ex_date DATE,
    record_date DATE,
    payment_date DATE,
    dividend_type TEXT,
    amount REAL,
    percentage REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE INDEX IF NOT EXISTS idx_dividends_company ON dividends(company_id);

-- Scrape metadata (audit trail)
CREATE TABLE IF NOT EXISTS scrape_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER,
    symbol TEXT,
    source_url TEXT,
    status TEXT,
    error_message TEXT,
    duration_ms INTEGER,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO schema_version (version) VALUES (1);
