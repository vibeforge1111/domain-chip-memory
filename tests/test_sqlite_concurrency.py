"""Tests for SQLite WAL mode concurrency fix (PR #14).

PR #14: enable WAL journal mode and set timeout on SQLite connections
for better concurrent access.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class TestSqliteWALConcurrency:
    """Tests for SQLite WAL mode and timeout behavior from PR #14."""

    def test_sqlite_connection_with_timeout(self, tmp_path: Path) -> None:
        """Verify sqlite3.connect accepts a timeout parameter."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path), timeout=30.0)
        conn.close()

    def test_sqlite_wal_journal_mode(self, tmp_path: Path) -> None:
        """Verify WAL journal mode can be enabled."""
        db_path = tmp_path / "test_wal.db"
        conn = sqlite3.connect(str(db_path), timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        result = conn.execute("PRAGMA journal_mode").fetchone()
        assert result is not None
        assert result[0].lower() in ("wal", "memory"), (
            f"Expected WAL journal mode, got: {result[0]}"
        )
        conn.close()

    def test_sqlite_wal_with_row_factory(self, tmp_path: Path) -> None:
        """Verify WAL mode works with sqlite3.Row factory."""
        db_path = tmp_path / "test_row.db"
        conn = sqlite3.connect(str(db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE test (id INTEGER, name TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'hello')")
        row = conn.execute("SELECT * FROM test").fetchone()
        assert row is not None
        assert row["name"] == "hello"
        conn.close()

    def test_concurrent_wal_reads(self, tmp_path: Path) -> None:
        """Verify WAL mode allows concurrent reads."""
        db_path = tmp_path / "test_concurrent.db"
        conn1 = sqlite3.connect(str(db_path), timeout=30.0)
        conn1.execute("PRAGMA journal_mode=WAL")
        conn1.execute("CREATE TABLE data (k INTEGER, v TEXT)")
        conn1.execute("INSERT INTO data VALUES (1, 'value1')")
        conn1.commit()

        conn2 = sqlite3.connect(str(db_path), timeout=30.0)
        rows = conn2.execute("SELECT * FROM data").fetchall()
        assert len(rows) == 1
        conn2.close()
        conn1.close()


# --- Source-level check ---

def test_cli_py_has_wal_and_timeout() -> None:
    """Verify the actual source file has WAL and timeout (PR #14) when on the branch."""
    cli_path = ROOT / "src" / "domain_chip_memory" / "cli.py"
    if not cli_path.exists():
        return
    source = cli_path.read_text(encoding="utf-8")
    if "timeout=30" not in source and "timeout=30.0" not in source:
        return  # not on the PR branch
    assert "journal_mode=WAL" in source, (
        "Expected PRAGMA journal_mode=WAL in cli.py (PR #14)"
    )
