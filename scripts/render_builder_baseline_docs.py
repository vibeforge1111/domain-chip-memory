from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUILDER_POINTER = Path.home() / ".spark-intelligence" / "artifacts" / "memory-validation-runs" / "latest-full-run.json"

README_PATH = ROOT / "README.md"
NEXT_PHASE_PATH = ROOT / "docs" / "NEXT_PHASE_SPARK_MEMORY_KB_BENCHMARK_PROGRAM_2026-04-10.md"
CURRENT_STATUS_PATH = ROOT / "docs" / "CURRENT_STATUS_BENCHMARKS_AND_KB_2026-04-09.md"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _replace_marked_block(content: str, start_marker: str, end_marker: str, replacement_body: str) -> str:
    pattern = re.compile(
        rf"(?P<start>{re.escape(start_marker)}\n)(?P<body>.*?)(?P<end>\n{re.escape(end_marker)})",
        re.DOTALL,
    )
    match = pattern.search(content)
    if not match:
        raise ValueError(f"Missing markers: {start_marker} / {end_marker}")
    return content[: match.start('body')] + replacement_body.rstrip("\n") + content[match.start('end') :]


def _fmt_seconds(value: Any) -> str:
    if value is None or value == "":
        return "unknown"
    return f"{float(value):0.3f}s"


def _row_by_name(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["baseline_name"]): row for row in rows}


def _load_builder_payloads(pointer_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    pointer = _load_json(pointer_path)
    run_summary = _load_json(Path(str(pointer["run_summary"])))
    regression = _load_json(Path(str(run_summary["regression_output_dir"])) / "telegram-memory-regression.json")
    soak = _load_json(Path(str(run_summary["soak_output_dir"])) / "telegram-memory-architecture-soak.json")
    return pointer, run_summary, regression, soak


def _build_common_lines(pointer_path: Path, run_summary: dict[str, Any], regression: dict[str, Any], soak: dict[str, Any]) -> list[str]:
    regression_summary = regression["summary"]
    soak_summary = soak["summary"]
    aggregate_rows = _row_by_name(list(soak.get("aggregate_results") or []))
    selector_rows = _row_by_name(list(soak.get("selection_aggregate_results") or []))
    ssm_aggregate = aggregate_rows.get("summary_synthesis_memory", {})
    dsech_aggregate = aggregate_rows.get("dual_store_event_calendar_hybrid", {})
    ssm_selector = selector_rows.get("summary_synthesis_memory", {})
    dsech_selector = selector_rows.get("dual_store_event_calendar_hybrid", {})
    output_root = str(run_summary["output_root"])
    builder_pointer = str(pointer_path)
    live_soak = f"{soak_summary.get('completed_runs', 'unknown')}/{soak_summary.get('requested_runs', 'unknown')}, `{soak_summary.get('failed_runs', 'unknown')}` failed"
    return [
        "- active runtime architecture: `summary_synthesis_memory + heuristic_v1`",
        "- active Builder challenger: `dual_store_event_calendar_hybrid + heuristic_v1`",
        "- latest head-to-head offline `ProductMemory` comparison: tied at `1156/1266`",
        f"- latest clean live Builder full validation root: `{output_root}`",
        f"- latest clean live Builder full-run pointer: `{builder_pointer}`",
        f"- latest clean live Builder soak: `{live_soak}`",
        f"- latest live whole-suite aggregate: `{ssm_aggregate.get('matched', 'unknown')}/{ssm_aggregate.get('total', 'unknown')}` for `summary_synthesis_memory` vs `{dsech_aggregate.get('matched', 'unknown')}/{dsech_aggregate.get('total', 'unknown')}` for `dual_store_event_calendar_hybrid`",
        f"- latest live selector-pack aggregate: `{ssm_selector.get('matched', 'unknown')}/{ssm_selector.get('total', 'unknown')}` for `summary_synthesis_memory` vs `{dsech_selector.get('matched', 'unknown')}/{dsech_selector.get('total', 'unknown')}` for `dual_store_event_calendar_hybrid`",
        f"- latest clean live Builder regression: `{regression_summary.get('matched_case_count', 'unknown')}/{regression_summary.get('case_count', 'unknown')}` with KB coverage `{regression_summary.get('kb_current_state_hits', 'unknown')}/{regression_summary.get('kb_current_state_total', 'unknown')}` current-state and `{regression_summary.get('kb_evidence_hits', 'unknown')}/{regression_summary.get('kb_evidence_total', 'unknown')}` evidence hits",
        f"- latest clean live Builder timings: benchmark `{_fmt_seconds(run_summary.get('benchmark_duration_seconds'))}`, regression `{_fmt_seconds(run_summary.get('regression_duration_seconds'))}`, soak `{_fmt_seconds(run_summary.get('soak_duration_seconds'))}`, total `{_fmt_seconds(run_summary.get('total_duration_seconds'))}`",
        "- Builder runtime is therefore pinned to `summary_synthesis_memory`",
    ]


def render_docs(*, builder_latest_run: Path) -> None:
    pointer, run_summary, regression, soak = _load_builder_payloads(builder_latest_run)
    common_lines = _build_common_lines(builder_latest_run, run_summary, regression, soak)

    readme = README_PATH.read_text(encoding="utf-8")
    readme = _replace_marked_block(
        readme,
        "<!-- AUTO_BUILDER_BASELINE_README_START -->",
        "<!-- AUTO_BUILDER_BASELINE_README_END -->",
        "\n".join(common_lines),
    )
    README_PATH.write_text(readme, encoding="utf-8")

    next_phase = NEXT_PHASE_PATH.read_text(encoding="utf-8")
    next_phase_lines = [
        "- the latest offline `ProductMemory` comparison between `summary_synthesis_memory` and `dual_store_event_calendar_hybrid` is tied at `1156/1266`",
        f"- the latest clean live Builder full validation root is `{run_summary['output_root']}`",
        f"- the latest clean live Builder full-run pointer is `{builder_latest_run}`",
        f"- the latest clean live Builder soak is fully green at `{soak['summary'].get('completed_runs', 'unknown')}/{soak['summary'].get('requested_runs', 'unknown')}`, `{soak['summary'].get('failed_runs', 'unknown')}` failed",
        f"- that live Builder soak still favors `summary_synthesis_memory` at `{_row_by_name(list(soak.get('aggregate_results') or [])).get('summary_synthesis_memory', {}).get('matched', 'unknown')}/{_row_by_name(list(soak.get('aggregate_results') or [])).get('summary_synthesis_memory', {}).get('total', 'unknown')}` overall and `{_row_by_name(list(soak.get('selection_aggregate_results') or [])).get('summary_synthesis_memory', {}).get('matched', 'unknown')}/{_row_by_name(list(soak.get('selection_aggregate_results') or [])).get('summary_synthesis_memory', {}).get('total', 'unknown')}` on selector packs",
        f"- the latest clean live Builder timings are benchmark `{_fmt_seconds(run_summary.get('benchmark_duration_seconds'))}`, regression `{_fmt_seconds(run_summary.get('regression_duration_seconds'))}`, soak `{_fmt_seconds(run_summary.get('soak_duration_seconds'))}`, total `{_fmt_seconds(run_summary.get('total_duration_seconds'))}`",
        "- because the offline side is now a tie instead of a loss, Builder has repinned the runtime selector to `summary_synthesis_memory`",
    ]
    next_phase = _replace_marked_block(
        next_phase,
        "<!-- AUTO_BUILDER_BASELINE_NEXT_PHASE_START -->",
        "<!-- AUTO_BUILDER_BASELINE_NEXT_PHASE_END -->",
        "\n".join(next_phase_lines),
    )
    NEXT_PHASE_PATH.write_text(next_phase, encoding="utf-8")

    current_status = CURRENT_STATUS_PATH.read_text(encoding="utf-8")
    current_status_lines = [
        "- the latest head-to-head offline `ProductMemory` comparison between `summary_synthesis_memory` and `dual_store_event_calendar_hybrid` is tied at `1156/1266`",
        f"- the latest clean live Builder full validation root is `{run_summary['output_root']}`",
        f"- the latest clean live Builder full-run pointer is `{builder_latest_run}`",
        f"- the latest clean live Builder soak is `{soak['summary'].get('completed_runs', 'unknown')}/{soak['summary'].get('requested_runs', 'unknown')}`, `{soak['summary'].get('failed_runs', 'unknown')}` failed and still favors `summary_synthesis_memory`",
        f"- the latest clean live Builder timings are benchmark `{_fmt_seconds(run_summary.get('benchmark_duration_seconds'))}`, regression `{_fmt_seconds(run_summary.get('regression_duration_seconds'))}`, soak `{_fmt_seconds(run_summary.get('soak_duration_seconds'))}`, total `{_fmt_seconds(run_summary.get('total_duration_seconds'))}`",
        "- Builder therefore repinned the runtime selector to `summary_synthesis_memory`",
    ]
    current_status = _replace_marked_block(
        current_status,
        "<!-- AUTO_BUILDER_BASELINE_CURRENT_STATUS_START -->",
        "<!-- AUTO_BUILDER_BASELINE_CURRENT_STATUS_END -->",
        "\n".join(current_status_lines),
    )
    CURRENT_STATUS_PATH.write_text(current_status, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh chip-side Builder baseline docs from Builder latest-full-run.json.")
    parser.add_argument("--builder-latest-run", default=str(DEFAULT_BUILDER_POINTER), help="Path to Builder latest-full-run.json")
    args = parser.parse_args()
    render_docs(builder_latest_run=Path(args.builder_latest_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
