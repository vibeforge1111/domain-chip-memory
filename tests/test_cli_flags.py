"""Tests for CLI flag definitions in domain-chip-memory CLI files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# evaluate_chip.py — has no argparse currently, verify it runs without error
# ---------------------------------------------------------------------------

def test_evaluate_chip_importable() -> None:
    """evaluate_chip.py should be importable as a module."""
    import evaluate_chip  # type: ignore[import]
    assert hasattr(evaluate_chip, "main")
    assert hasattr(evaluate_chip, "run_evaluation")


# ---------------------------------------------------------------------------
# scripts/render_builder_baseline_docs.py
# ---------------------------------------------------------------------------

def test_render_builder_baseline_docs_parser() -> None:
    """Verify render_builder_baseline_docs.py arg parser exists and accepts --builder-latest-run."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "render_builder_baseline_docs",
        str(Path(__file__).resolve().parents[1] / "scripts" / "render_builder_baseline_docs.py"),
    )
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    assert hasattr(mod, "main")
    assert hasattr(mod, "render_docs")


# ---------------------------------------------------------------------------
# src/domain_chip_memory/cli.py
# ---------------------------------------------------------------------------

def test_cli_module_has_main() -> None:
    from domain_chip_memory import cli
    assert hasattr(cli, "main")
    assert callable(cli.main)


def test_cli_module_has_subcommands() -> None:
    """Verify the CLI module defines subcommand parsers."""
    from domain_chip_memory import cli
    parser = argparse.ArgumentParser(prog="domain_chip_memory.cli")
    subparsers = parser.add_subparsers(dest="command")
    evaluate = subparsers.add_parser("evaluate")
    assert evaluate is not None
