from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module(module_name: str, script_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_render_builder_baseline_docs_updates_marked_sections(tmp_path: Path) -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "render_builder_baseline_docs.py"
    module = _load_module("render_builder_baseline_docs_test", script_path)

    readme = tmp_path / "README.md"
    next_phase = tmp_path / "NEXT_PHASE_SPARK_MEMORY_KB_BENCHMARK_PROGRAM_2026-04-10.md"
    current_status = tmp_path / "CURRENT_STATUS_BENCHMARKS_AND_KB_2026-04-09.md"
    pointer = tmp_path / "latest-full-run.json"
    run_summary = tmp_path / "run-summary.json"
    regression_dir = tmp_path / "telegram-memory-regression"
    soak_dir = tmp_path / "telegram-memory-architecture-soak"
    regression_dir.mkdir()
    soak_dir.mkdir()

    readme.write_text(
        "\n".join(
            [
                "prefix",
                "<!-- AUTO_BUILDER_BASELINE_README_START -->",
                "old",
                "<!-- AUTO_BUILDER_BASELINE_README_END -->",
                "suffix",
            ]
        ),
        encoding="utf-8",
    )
    next_phase.write_text(
        "\n".join(
            [
                "prefix",
                "<!-- AUTO_BUILDER_BASELINE_NEXT_PHASE_START -->",
                "old",
                "<!-- AUTO_BUILDER_BASELINE_NEXT_PHASE_END -->",
                "suffix",
            ]
        ),
        encoding="utf-8",
    )
    current_status.write_text(
        "\n".join(
            [
                "prefix",
                "<!-- AUTO_BUILDER_BASELINE_CURRENT_STATUS_START -->",
                "old",
                "<!-- AUTO_BUILDER_BASELINE_CURRENT_STATUS_END -->",
                "suffix",
            ]
        ),
        encoding="utf-8",
    )

    pointer.write_text(
        json.dumps(
            {
                "output_root": str(tmp_path / "20260412-013326"),
                "run_summary": str(run_summary),
                "updated_at": "2026-04-12T01:33:26+04:00",
            }
        ),
        encoding="utf-8",
    )
    run_summary.write_text(
        json.dumps(
            {
                "output_root": str(tmp_path / "20260412-013326"),
                "benchmark_duration_seconds": 12.348,
                "regression_duration_seconds": 23.045,
                "soak_duration_seconds": 348.233,
                "total_duration_seconds": 383.853,
                "domain_chip_repo_commit": "chip-baseline-sha",
                "regression_output_dir": str(regression_dir),
                "soak_output_dir": str(soak_dir),
            }
        ),
        encoding="utf-8",
    )
    (regression_dir / "telegram-memory-regression.json").write_text(
        json.dumps(
            {
                "summary": {
                    "matched_case_count": 34,
                    "case_count": 34,
                    "kb_current_state_hits": 38,
                    "kb_current_state_total": 38,
                    "kb_evidence_hits": 38,
                    "kb_evidence_total": 38,
                }
            }
        ),
        encoding="utf-8",
    )
    (soak_dir / "telegram-memory-architecture-soak.json").write_text(
        json.dumps(
            {
                "summary": {"completed_runs": 14, "requested_runs": 14, "failed_runs": 0},
                "aggregate_results": [
                    {"baseline_name": "summary_synthesis_memory", "matched": 92, "total": 92},
                    {"baseline_name": "dual_store_event_calendar_hybrid", "matched": 89, "total": 92},
                ],
                "selection_aggregate_results": [
                    {"baseline_name": "summary_synthesis_memory", "matched": 64, "total": 64},
                    {"baseline_name": "dual_store_event_calendar_hybrid", "matched": 61, "total": 64},
                ],
            }
        ),
        encoding="utf-8",
    )

    module.README_PATH = readme
    module.NEXT_PHASE_PATH = next_phase
    module.CURRENT_STATUS_PATH = current_status
    module.DEFAULT_BUILDER_POINTER = pointer
    module._git_revision = lambda _repo_root: "chip-current-sha"

    module.render_docs(builder_latest_run=pointer)

    readme_text = readme.read_text(encoding="utf-8")
    assert "20260412-013326" in readme_text
    assert "chip-side baseline freshness: `warning`" in readme_text
    assert "chip-current-sha" in readme_text

    next_phase_text = next_phase.read_text(encoding="utf-8")
    assert str(pointer) in next_phase_text
    assert "1156/1266" in next_phase_text
    assert "348.233s" in next_phase_text

    current_status_text = current_status.read_text(encoding="utf-8")
    assert "warning" in current_status_text
    assert "14/14" in current_status_text


def test_render_builder_baseline_docs_marks_clean_chip_freshness_when_commits_match(tmp_path: Path) -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "render_builder_baseline_docs.py"
    module = _load_module("render_builder_baseline_docs_clean_test", script_path)

    readme = tmp_path / "README.md"
    next_phase = tmp_path / "NEXT_PHASE_SPARK_MEMORY_KB_BENCHMARK_PROGRAM_2026-04-10.md"
    current_status = tmp_path / "CURRENT_STATUS_BENCHMARKS_AND_KB_2026-04-09.md"
    pointer = tmp_path / "latest-full-run.json"
    run_summary = tmp_path / "run-summary.json"
    regression_dir = tmp_path / "telegram-memory-regression"
    soak_dir = tmp_path / "telegram-memory-architecture-soak"
    regression_dir.mkdir()
    soak_dir.mkdir()

    readme.write_text(
        "\n".join(
            [
                "prefix",
                "<!-- AUTO_BUILDER_BASELINE_README_START -->",
                "old",
                "<!-- AUTO_BUILDER_BASELINE_README_END -->",
                "suffix",
            ]
        ),
        encoding="utf-8",
    )
    next_phase.write_text(
        "\n".join(
            [
                "prefix",
                "<!-- AUTO_BUILDER_BASELINE_NEXT_PHASE_START -->",
                "old",
                "<!-- AUTO_BUILDER_BASELINE_NEXT_PHASE_END -->",
                "suffix",
            ]
        ),
        encoding="utf-8",
    )
    current_status.write_text(
        "\n".join(
            [
                "prefix",
                "<!-- AUTO_BUILDER_BASELINE_CURRENT_STATUS_START -->",
                "old",
                "<!-- AUTO_BUILDER_BASELINE_CURRENT_STATUS_END -->",
                "suffix",
            ]
        ),
        encoding="utf-8",
    )

    pointer.write_text(
        json.dumps(
            {
                "output_root": str(tmp_path / "20260412-013326"),
                "run_summary": str(run_summary),
            }
        ),
        encoding="utf-8",
    )
    run_summary.write_text(
        json.dumps(
            {
                "output_root": str(tmp_path / "20260412-013326"),
                "builder_repo_commit": "builder-sha",
                "domain_chip_repo_commit": "chip-current-sha",
                "benchmark_duration_seconds": 12.348,
                "regression_duration_seconds": 23.045,
                "soak_duration_seconds": 348.233,
                "total_duration_seconds": 383.853,
                "offline_runtime_architecture": "summary_synthesis_memory",
                "offline_product_memory_leaders": [
                    "summary_synthesis_memory",
                    "dual_store_event_calendar_hybrid",
                ],
                "live_regression": "34/34",
                "live_soak_completion": "14/14",
                "live_soak_leaders": ["summary_synthesis_memory"],
                "regression_output_dir": str(regression_dir),
                "soak_output_dir": str(soak_dir),
            }
        ),
        encoding="utf-8",
    )
    (regression_dir / "telegram-memory-regression.json").write_text(
        json.dumps(
            {
                "summary": {
                    "matched_case_count": 34,
                    "case_count": 34,
                }
            }
        ),
        encoding="utf-8",
    )
    (soak_dir / "telegram-memory-architecture-soak.json").write_text(
        json.dumps(
            {
                "summary": {
                    "completed_runs": 14,
                    "requested_runs": 14,
                    "failed_runs": 0,
                },
                "aggregate_results": [
                    {"baseline_name": "summary_synthesis_memory", "matched": 92, "total": 92},
                    {"baseline_name": "dual_store_event_calendar_hybrid", "matched": 89, "total": 92},
                ],
            }
        ),
        encoding="utf-8",
    )

    module.README_PATH = readme
    module.NEXT_PHASE_PATH = next_phase
    module.CURRENT_STATUS_PATH = current_status
    module.DEFAULT_BUILDER_POINTER = pointer
    module._git_revision = lambda _repo_root: "chip-current-sha"

    module.render_docs(builder_latest_run=pointer)

    readme_text = readme.read_text(encoding="utf-8")
    assert "chip-side baseline freshness: `clean`" in readme_text
    assert "current chip commit: `chip-current-sha`" in readme_text

    current_status_text = current_status.read_text(encoding="utf-8")
    assert "`14/14`" in current_status_text


def test_render_builder_baseline_docs_marks_unknown_chip_freshness_when_git_revision_is_unavailable(tmp_path: Path) -> None:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "render_builder_baseline_docs.py"
    module = _load_module("render_builder_baseline_docs_unknown_test", script_path)

    readme = tmp_path / "README.md"
    next_phase = tmp_path / "NEXT_PHASE_SPARK_MEMORY_KB_BENCHMARK_PROGRAM_2026-04-10.md"
    current_status = tmp_path / "CURRENT_STATUS_BENCHMARKS_AND_KB_2026-04-09.md"
    pointer = tmp_path / "latest-full-run.json"
    run_summary = tmp_path / "run-summary.json"
    regression_dir = tmp_path / "telegram-memory-regression"
    soak_dir = tmp_path / "telegram-memory-architecture-soak"
    regression_dir.mkdir()
    soak_dir.mkdir()

    readme.write_text(
        "\n".join(
            [
                "prefix",
                "<!-- AUTO_BUILDER_BASELINE_README_START -->",
                "old",
                "<!-- AUTO_BUILDER_BASELINE_README_END -->",
                "suffix",
            ]
        ),
        encoding="utf-8",
    )
    next_phase.write_text(
        "\n".join(
            [
                "prefix",
                "<!-- AUTO_BUILDER_BASELINE_NEXT_PHASE_START -->",
                "old",
                "<!-- AUTO_BUILDER_BASELINE_NEXT_PHASE_END -->",
                "suffix",
            ]
        ),
        encoding="utf-8",
    )
    current_status.write_text(
        "\n".join(
            [
                "prefix",
                "<!-- AUTO_BUILDER_BASELINE_CURRENT_STATUS_START -->",
                "old",
                "<!-- AUTO_BUILDER_BASELINE_CURRENT_STATUS_END -->",
                "suffix",
            ]
        ),
        encoding="utf-8",
    )

    pointer.write_text(
        json.dumps(
            {
                "output_root": str(tmp_path / "20260412-013326"),
                "run_summary": str(run_summary),
            }
        ),
        encoding="utf-8",
    )
    run_summary.write_text(
        json.dumps(
            {
                "output_root": str(tmp_path / "20260412-013326"),
                "builder_repo_commit": "builder-sha",
                "domain_chip_repo_commit": None,
                "benchmark_duration_seconds": None,
                "regression_duration_seconds": "",
                "soak_duration_seconds": None,
                "total_duration_seconds": "",
                "offline_runtime_architecture": "summary_synthesis_memory",
                "offline_product_memory_leaders": [
                    "summary_synthesis_memory",
                    "dual_store_event_calendar_hybrid",
                ],
                "live_regression": "34/34",
                "live_soak_completion": "14/14",
                "live_soak_leaders": ["summary_synthesis_memory"],
                "regression_output_dir": str(regression_dir),
                "soak_output_dir": str(soak_dir),
            }
        ),
        encoding="utf-8",
    )
    (regression_dir / "telegram-memory-regression.json").write_text(
        json.dumps(
            {
                "summary": {
                    "matched_case_count": 34,
                    "case_count": 34,
                    "kb_current_state_hits": 0,
                    "kb_current_state_total": 0,
                    "kb_evidence_hits": 0,
                    "kb_evidence_total": 0,
                }
            }
        ),
        encoding="utf-8",
    )
    (soak_dir / "telegram-memory-architecture-soak.json").write_text(
        json.dumps(
            {
                "summary": {
                    "completed_runs": 14,
                    "requested_runs": 14,
                    "failed_runs": 0,
                },
                "aggregate_results": [
                    {"baseline_name": "summary_synthesis_memory", "matched": 92, "total": 92},
                    {"baseline_name": "dual_store_event_calendar_hybrid", "matched": 89, "total": 92},
                ],
                "selection_aggregate_results": [],
            }
        ),
        encoding="utf-8",
    )

    module.README_PATH = readme
    module.NEXT_PHASE_PATH = next_phase
    module.CURRENT_STATUS_PATH = current_status
    module.DEFAULT_BUILDER_POINTER = pointer
    module._git_revision = lambda _repo_root: None

    module.render_docs(builder_latest_run=pointer)

    readme_text = readme.read_text(encoding="utf-8")
    assert "chip-side baseline freshness: `unknown`" in readme_text
    assert "chip baseline commit from Builder run: `unknown`" in readme_text
    assert "current chip commit: `unknown`" in readme_text
    assert "latest live selector-pack aggregate: `unknown/unknown`" in readme_text
    assert "benchmark `unknown`, regression `unknown`, soak `unknown`, total `unknown`" in readme_text

    next_phase_text = next_phase.read_text(encoding="utf-8")
    assert "chip-side freshness against that Builder baseline is `unknown`" in next_phase_text
    assert "selector packs" in next_phase_text.lower()

    current_status_text = current_status.read_text(encoding="utf-8")
    assert "chip-side freshness against that Builder baseline is `unknown`" in current_status_text
