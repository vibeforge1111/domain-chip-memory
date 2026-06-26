"""Regression tests for the builder-state-DB connect timeout.

Resurrects/adjusts domain-chip-memory#38. The two ``sqlite3.connect`` calls
that open the Telegram builder ``state.db`` (in ``_load_supported_builder_rows``
and ``_load_supported_builder_rows_for_humans``, now sharing the
``_connect_state_db`` helper) used the default ``timeout=0``-style behaviour,
so a concurrently write-locked DB raised ``database is locked`` immediately.

These tests assert (1) ``sqlite3.connect`` is called with ``timeout=30.0`` and
(2) the read still succeeds against a briefly write-locked DB rather than
raising, which the original PR's import-only stub test never checked.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

from domain_chip_memory import cli


_BUILDER_EVENTS_SCHEMA = """
CREATE TABLE builder_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    truth_kind TEXT NOT NULL,
    target_surface TEXT NOT NULL,
    component TEXT NOT NULL,
    run_id TEXT,
    parent_event_id TEXT,
    correlation_id TEXT,
    request_id TEXT,
    trace_ref TEXT,
    channel_id TEXT,
    session_id TEXT,
    human_id TEXT,
    agent_id TEXT,
    actor_id TEXT,
    evidence_lane TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    reason_code TEXT,
    provenance_json TEXT,
    facts_json TEXT,
    created_at TEXT NOT NULL
)
"""


def _make_builder_home(tmp_path: Path) -> Path:
    builder_home = tmp_path / "builder-home"
    builder_home.mkdir()
    state_db = builder_home / "state.db"
    connection = sqlite3.connect(state_db)
    try:
        connection.execute(_BUILDER_EVENTS_SCHEMA)
        connection.execute(
            """
            INSERT INTO builder_events (
                event_id, event_type, truth_kind, target_surface, component,
                evidence_lane, severity, status, summary, channel_id,
                session_id, human_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "evt-1",
                "intent_committed",
                "event",
                "telegram",
                "telegram_runtime",
                "runtime",
                "info",
                "committed",
                "Captured inbound Telegram message",
                "telegram",
                "chat-12345",
                "12345",
                "2026-04-09 20:19:27",
            ),
        )
        connection.commit()
    finally:
        connection.close()
    return builder_home


def test_builder_state_db_connect_passes_timeout(tmp_path: Path, monkeypatch):
    builder_home = _make_builder_home(tmp_path)

    seen_timeouts: list[object] = []
    real_connect = sqlite3.connect

    def _spy_connect(database, *args, **kwargs):
        seen_timeouts.append(kwargs.get("timeout"))
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(cli.sqlite3, "connect", _spy_connect)

    payload = cli._normalize_builder_telegram_state_db(str(builder_home), limit=25)

    assert isinstance(payload, dict)
    # Every connect the loader made must carry the 30s lock timeout.
    assert seen_timeouts, "expected the loader to open the state DB at least once"
    assert all(timeout == 30.0 for timeout in seen_timeouts), seen_timeouts


def test_builder_state_db_read_waits_out_a_brief_write_lock(tmp_path: Path):
    builder_home = _make_builder_home(tmp_path)
    state_db = builder_home / "state.db"

    locked = threading.Event()
    released = threading.Event()

    def _hold_write_lock() -> None:
        holder = sqlite3.connect(state_db, timeout=30.0)
        try:
            holder.isolation_level = None
            holder.execute("BEGIN EXCLUSIVE")
            locked.set()
            # Hold the lock briefly; well under the 30s connect timeout so the
            # reader should wait, not raise.
            time.sleep(0.5)
            holder.execute("COMMIT")
        finally:
            holder.close()
            released.set()

    locker = threading.Thread(target=_hold_write_lock)
    locker.start()
    try:
        assert locked.wait(timeout=5.0), "writer never acquired the exclusive lock"
        # With the old default timeout this raised OperationalError immediately;
        # with timeout=30.0 it blocks until the writer commits, then succeeds.
        payload = cli._normalize_builder_telegram_state_db(str(builder_home), limit=25)
        assert isinstance(payload, dict)
        assert released.is_set()
    finally:
        locker.join(timeout=5.0)
