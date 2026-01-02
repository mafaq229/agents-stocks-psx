"""CSS selectors for PSX website scraping.

Centralized selector definitions for maintainability.
"""

# Quote section
QUOTE_PRICE = ".quote__close"
QUOTE_CHANGE = ".quote__change"
STATS_ITEM = ".stats_item"
STATS_VALUE = ".stats_value"

# Company profile
PROFILE_DESCRIPTION = "#profile p"
PROFILE_SECTOR = "#profile .company_sector, .company-sector"
SECTOR_STAT = ".stats_item:has(.stats_label:text-matches('sector', 'i')) .stats_value"
SECTOR_LABEL = ".stats_item:has-text('Sector') .stats_value"
SECTOR_BREADCRUMB = ".breadcrumb a:last-child"
COMPANY_HEADER = ".company__header a"

# Equity section
EQUITY_STATS = "#equity .stats_value"

# Financials
FINANCIALS_SECTION = "#financials"
FINANCIALS_TABLE = "#financials table"
ANNUAL_PANEL = "div.tabs__panel[data-name='Annual'] table"
QUARTERLY_PANEL = "div.tabs__panel[data-name='Quarterly'] table"
QUARTERLY_TOGGLE = "div.tabs__list__item[data-name='Quarterly']"

# Ratios
RATIOS_TAB = "a[href='#ratios'], a[data-link='#ratios']"
RATIOS_TABLE = "#ratios table"

# Announcements
ANNOUNCEMENTS_TAB = "a[href='#announcements'], a[data-link='#announcements']"
ANNOUNCEMENT_SUB_TAB = "div.tabs__list__item[data-name='{tab}']"
ANNOUNCEMENT_PANEL = "div.tabs__panel[data-name='{tab}'] table"
COMPANY_ANNOUNCEMENTS_TABLE = ".company_announcements table"

# Reports
REPORTS_TAB = "a[href='#reports'], a[data-link='#reports']"
REPORTS_TABLE = "#reports table"

# Chart
CHART_DIV = "#companyDailyChart"
