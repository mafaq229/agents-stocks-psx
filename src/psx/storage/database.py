"""SQLite database connection and migration management."""

import sqlite3
from pathlib import Path
from typing import Optional
import logging

from psx.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class Database:
    """SQLite database connection manager with migration support."""

    def __init__(self, db_path: str = "data/db/psx.db"):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[sqlite3.Connection] = None

    # running this function like an attribute (hides complexity of connection). self.connection.execute will run connection first then execute.
    # otherwise we do something like this db.get_connection() i.e. not clean for lazy initalization
    @property
    def connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._connection is None:
            # check_same_thread=False: allows connection to be used from multiple threads.
            # By default, SQLite only allows access from the thread that created it.
            # We disable this check because asyncio + Playwright may access from different contexts.
            # Safe here since we're mostly single-threaded and SQLite has internal write locking.
            self._connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
            )
            # lets you access columns by names like dict e.g. row["version"] instead of just row[0].
            self._connection.row_factory = sqlite3.Row
            # Enable foreign keys (disabled by default in sqlite)
            self._connection.execute("PRAGMA foreign_keys = ON")
        return self._connection

    def close(self) -> None:
        """Close database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute SQL statement."""
        try:
            cursor = self.connection.execute(sql, params)
            return cursor
        except sqlite3.Error as e:
            raise DatabaseError(f"SQL execution failed: {e}")

    def executemany(self, sql: str, params_list: list) -> sqlite3.Cursor:
        """Execute SQL statement with multiple parameter sets."""
        try:
            cursor = self.connection.executemany(sql, params_list)
            return cursor
        except sqlite3.Error as e:
            raise DatabaseError(f"SQL executemany failed: {e}")

    def commit(self) -> None:
        """Commit current transaction."""
        self.connection.commit()

    def rollback(self) -> None:
        """Rollback current transaction."""
        self.connection.rollback()

    def get_schema_version(self) -> int:
        """Get current schema version."""
        try:
            cursor = self.connection.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            )
            row = cursor.fetchone()
            return row["version"] if row else 0
        except sqlite3.OperationalError:
            # Table doesn't exist yet
            return 0

    def run_migrations(self, migrations_dir: str = "data/migrations") -> None:
        """
        Run pending database migrations.

        Args:
            migrations_dir: Directory containing SQL migration files
        """
        migrations_path = Path(migrations_dir)
        if not migrations_path.exists():
            logger.warning(f"Migrations directory not found: {migrations_dir}")
            return

        current_version = self.get_schema_version()
        logger.info(f"Current schema version: {current_version}")

        # Find and sort migration files
        migration_files = sorted(migrations_path.glob("*.sql"))

        for migration_file in migration_files:
            # Extract version from filename (e.g., 001_initial_schema.sql -> 1)
            version_str = migration_file.stem.split("_")[0]
            try:
                version = int(version_str)
            except ValueError:
                logger.warning(f"Skipping invalid migration file: {migration_file}")
                continue

            if version <= current_version:
                continue

            logger.info(f"Running migration: {migration_file.name}")

            try:
                sql = migration_file.read_text()
                self.connection.executescript(sql)
                self.commit()
                logger.info(f"Migration {version} completed")
            except sqlite3.Error as e:
                self.rollback()
                raise DatabaseError(f"Migration {version} failed: {e}")

    def init_database(self, migrations_dir: str = "data/migrations") -> None:
        """
        Initialize database with all migrations.

        Args:
            migrations_dir: Directory containing SQL migration files
        """
        logger.info(f"Initializing database at {self.db_path}")
        self.run_migrations(migrations_dir)
        logger.info("Database initialization complete")


# Global database instance (can be overridden)
_db: Optional[Database] = None


def get_database(db_path: str = "data/db/psx.db") -> Database:
    """Get or create global database instance."""
    global _db
    if _db is None:
        _db = Database(db_path)
    return _db


def init_database(db_path: str = "data/db/psx.db", migrations_dir: str = "data/migrations") -> Database:
    """Initialize database with migrations and return instance."""
    db = get_database(db_path)
    db.init_database(migrations_dir)
    return db
