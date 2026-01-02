"""Custom exceptions for PSX Stock Analysis Platform."""


class PSXError(Exception):
    """Base exception for all PSX errors."""

    pass


class ScraperError(PSXError):
    """Error during web scraping."""

    def __init__(self, message: str, symbol: str = None, url: str = None):
        self.symbol = symbol
        self.url = url
        super().__init__(message)


class DatabaseError(PSXError):
    """Error during database operations."""

    pass


class ValidationError(PSXError):
    """Error during data validation."""

    def __init__(self, message: str, field: str = None, value=None):
        self.field = field
        self.value = value
        super().__init__(message)


class PDFParseError(PSXError):
    """Error during PDF parsing."""

    def __init__(self, message: str, url: str = None):
        self.url = url
        super().__init__(message)
