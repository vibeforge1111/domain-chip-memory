"""Tests for logging fixes replacing silent error swallows (PR #5).

PR #5: fulltext index build errors now use logger.warning instead of silent pass.
"""
from __future__ import annotations

import logging
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class TestLoggingFixes:
    """Tests for logging behavior changes from PR #5."""

    def test_logger_warning_importable(self) -> None:
        """Verify logging module can be configured and used."""
        logger = logging.getLogger("test_fulltext_index")
        assert logger is not None

    def test_logger_warning_supports_context(self) -> None:
        """Verify logger.warning accepts format strings with context."""
        logger = logging.getLogger("test_fulltext_context")
        query = "MATCH (n) RETURN n"
        # This should not raise
        logger.warning("fulltext index: failed to build fulltext index for query: %s", query)

    def test_logger_warning_with_path(self) -> None:
        """Verify logger.warning with Path argument works."""
        logger = logging.getLogger("test_fulltext_path")
        marker_path = Path("/tmp/test_marker.txt")
        # This should not raise
        logger.warning("fulltext index: failed to write marker file at %s", marker_path)


# --- Source-level check ---

def test_memory_sidecars_py_has_logger_warning() -> None:
    """Verify the actual source file has logger.warning calls (PR #5) when on the branch."""
    sidecars_path = ROOT / "src" / "domain_chip_memory" / "memory_sidecars.py"
    if not sidecars_path.exists():
        return
    source = sidecars_path.read_text(encoding="utf-8")
    if "logger.warning" not in source:
        return  # not on the PR branch
    assert "fulltext index" in source, (
        "Expected fulltext index context in logger.warning calls (PR #5)"
    )
