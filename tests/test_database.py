"""Tests for Database class."""

import pytest
import tempfile
import os
from pathlib import Path

from psx.storage.database import Database, get_database, init_database
from psx.core.exceptions import DatabaseError


class TestDatabase:
    """Test Database class functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = Database(db_path)
            yield db
            db.close()

    @pytest.fixture
    def temp_db_with_migrations(self, temp_db):
        """Create a temporary database with migrations applied."""
        # Get the project root migrations directory
        migrations_dir = Path(__file__).parent.parent / "data" / "migrations"
        if migrations_dir.exists():
            temp_db.run_migrations(str(migrations_dir))
        return temp_db

    def test_init_creates_directory(self):
        """Test that database initialization creates parent directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "subdir", "test.db")
            db = Database(db_path)
            assert Path(db_path).parent.exists()
            db.close()

    def test_connection_property(self, temp_db):
        """Test lazy connection creation."""
        assert temp_db._connection is None
        conn = temp_db.connection
        assert conn is not None
        assert temp_db._connection is conn

    def test_connection_reuse(self, temp_db):
        """Test connection is reused on subsequent calls."""
        conn1 = temp_db.connection
        conn2 = temp_db.connection
        assert conn1 is conn2

    def test_close(self, temp_db):
        """Test closing database connection."""
        _ = temp_db.connection  # Force connection creation
        temp_db.close()
        assert temp_db._connection is None

    def test_execute_simple_query(self, temp_db):
        """Test executing a simple query."""
        temp_db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        temp_db.execute("INSERT INTO test (name) VALUES (?)", ("test_name",))
        temp_db.commit()

        cursor = temp_db.execute("SELECT * FROM test")
        rows = cursor.fetchall()
        assert len(rows) == 1
        assert rows[0]["name"] == "test_name"

    def test_execute_with_params(self, temp_db):
        """Test executing query with parameters."""
        temp_db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value REAL)")
        temp_db.execute("INSERT INTO test (value) VALUES (?)", (3.14,))
        temp_db.commit()

        cursor = temp_db.execute("SELECT value FROM test WHERE id = ?", (1,))
        row = cursor.fetchone()
        assert row["value"] == pytest.approx(3.14)

    def test_execute_invalid_sql_raises(self, temp_db):
        """Test that invalid SQL raises DatabaseError."""
        with pytest.raises(DatabaseError):
            temp_db.execute("INVALID SQL SYNTAX")

    def test_executemany(self, temp_db):
        """Test executemany for batch inserts."""
        temp_db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        data = [("name1",), ("name2",), ("name3",)]
        temp_db.executemany("INSERT INTO test (name) VALUES (?)", data)
        temp_db.commit()

        cursor = temp_db.execute("SELECT COUNT(*) as cnt FROM test")
        assert cursor.fetchone()["cnt"] == 3

    def test_rollback(self, temp_db):
        """Test rollback functionality."""
        temp_db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        temp_db.commit()

        temp_db.execute("INSERT INTO test (name) VALUES (?)", ("test",))
        temp_db.rollback()

        cursor = temp_db.execute("SELECT COUNT(*) as cnt FROM test")
        assert cursor.fetchone()["cnt"] == 0

    def test_get_schema_version_no_table(self, temp_db):
        """Test getting schema version when table doesn't exist."""
        version = temp_db.get_schema_version()
        assert version == 0

    def test_get_schema_version_with_table(self, temp_db):
        """Test getting schema version when table exists."""
        temp_db.execute(
            "CREATE TABLE schema_version (version INTEGER PRIMARY KEY)"
        )
        temp_db.execute("INSERT INTO schema_version (version) VALUES (5)")
        temp_db.commit()

        version = temp_db.get_schema_version()
        assert version == 5

    def test_run_migrations_no_dir(self, temp_db, tmp_path):
        """Test run_migrations with non-existent directory."""
        nonexistent = str(tmp_path / "nonexistent")
        # Should not raise, just log warning
        temp_db.run_migrations(nonexistent)

    def test_run_migrations_creates_tables(self, temp_db_with_migrations):
        """Test that migrations create expected tables."""
        db = temp_db_with_migrations
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row["name"] for row in cursor.fetchall()}

        expected_tables = {
            "companies",
            "quotes",
            "financials",
            "ratios",
            "announcements",
            "reports",
            "dividends",
            "scrape_log",
            "schema_version",
        }
        assert expected_tables.issubset(tables)

    def test_row_factory(self, temp_db):
        """Test that row factory returns dict-like objects."""
        temp_db.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        temp_db.execute("INSERT INTO test VALUES (1, 'test')")
        temp_db.commit()

        cursor = temp_db.execute("SELECT * FROM test")
        row = cursor.fetchone()

        # Should be able to access by key
        assert row["id"] == 1
        assert row["name"] == "test"

    def test_foreign_keys_enabled(self, temp_db):
        """Test that foreign keys are enabled."""
        cursor = temp_db.execute("PRAGMA foreign_keys")
        result = cursor.fetchone()
        assert result[0] == 1


class TestGlobalDatabase:
    """Test global database functions."""

    def test_get_database_creates_instance(self):
        """Test get_database creates a database instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            # Reset global state
            import psx.storage.database as db_module
            db_module._db = None

            db = get_database(db_path)
            assert db is not None
            assert isinstance(db, Database)

            # Cleanup
            db.close()
            db_module._db = None

    def test_init_database(self):
        """Test init_database runs migrations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            migrations_dir = Path(__file__).parent.parent / "data" / "migrations"

            # Reset global state
            import psx.storage.database as db_module
            db_module._db = None

            if migrations_dir.exists():
                db = init_database(db_path, str(migrations_dir))
                assert db.get_schema_version() >= 1
                db.close()

            db_module._db = None
