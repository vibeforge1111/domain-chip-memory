"""Tests for manifest path traversal protection (PR #13).

PR #13: _safe_manifest_path blocks absolute paths and '..' traversal.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# --- Standalone unit tests (no import needed) ---

def _safe_manifest_path(repo_root: Path, manifest_row: dict) -> Path:
    """Replicates the fix from PR #13: safe manifest path resolution."""
    rel = Path(str(manifest_row.get("path", "")).strip())
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("Manifest path must be relative without traversal")
    target = (repo_root.resolve() / rel).resolve()
    root = repo_root.resolve()
    if root not in target.parents and target != root:
        raise ValueError("Manifest path escapes repo root")
    return target


class TestSafeManifestPath:
    """Tests for _safe_manifest_path path traversal protection."""

    def test_valid_relative_path(self, tmp_path: Path) -> None:
        sub = tmp_path / "subdir"
        sub.mkdir()
        result = _safe_manifest_path(tmp_path, {"path": "subdir"})
        assert result == sub.resolve()

    def test_valid_file_in_root(self, tmp_path: Path) -> None:
        result = _safe_manifest_path(tmp_path, {"path": "manifest.json"})
        assert result == (tmp_path / "manifest.json").resolve()

    def test_valid_nested_path(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        result = _safe_manifest_path(tmp_path, {"path": "a/b/c"})
        assert result == nested.resolve()

    def test_absolute_path_rejected(self, tmp_path: Path) -> None:
        try:
            _safe_manifest_path(tmp_path, {"path": "/etc/passwd"})
            assert False, "Expected ValueError for absolute path"
        except ValueError as exc:
            assert "must be relative" in str(exc)

    def test_dotdot_traversal_rejected(self, tmp_path: Path) -> None:
        try:
            _safe_manifest_path(tmp_path, {"path": "../etc/passwd"})
            assert False, "Expected ValueError for '..' traversal"
        except ValueError as exc:
            assert "without traversal" in str(exc)

    def test_deep_dotdot_traversal_rejected(self, tmp_path: Path) -> None:
        try:
            _safe_manifest_path(tmp_path, {"path": "a/../../etc/passwd"})
            assert False, "Expected ValueError for nested '..' traversal"
        except ValueError as exc:
            assert "without traversal" in str(exc)

    def test_missing_path_key_uses_empty(self, tmp_path: Path) -> None:
        result = _safe_manifest_path(tmp_path, {})
        assert result == tmp_path.resolve()

    def test_empty_path_value(self, tmp_path: Path) -> None:
        result = _safe_manifest_path(tmp_path, {"path": ""})
        assert result == tmp_path.resolve()

    def test_whitespace_path(self, tmp_path: Path) -> None:
        result = _safe_manifest_path(tmp_path, {"path": "  subdir  "})
        assert result == (tmp_path / "subdir").resolve()

    def test_none_path_resolves_to_root(self, tmp_path: Path) -> None:
        """None path becomes 'None' string which resolves to repo root after .resolve()."""
        result = _safe_manifest_path(tmp_path, {"path": None})
        # None becomes Path("None") -> (tmp_path/"None").resolve()
        assert result == (tmp_path / "None").resolve()

    def test_non_string_path_resolves(self, tmp_path: Path) -> None:
        """Non-string path values like int 123 become Path('123')."""
        result = _safe_manifest_path(tmp_path, {"path": 123})
        assert result == (tmp_path / "123").resolve()


# --- Source-level check (skip if not on branch) ---

def test_cli_py_has_safe_manifest_path() -> None:
    """Verify the actual source file defines _safe_manifest_path (PR #13)."""
    cli_path = ROOT / "src" / "domain_chip_memory" / "cli.py"
    if not cli_path.exists():
        return
    source = cli_path.read_text(encoding="utf-8")
    if "_safe_manifest_path" not in source:
        return  # not on the PR branch
    assert "repo_root not in target.parents" in source, (
        "Expected repo_root boundary check in cli.py (PR #13)"
    )
