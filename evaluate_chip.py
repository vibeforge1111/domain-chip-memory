"""Local evaluator for the domain-chip-memory scaffold.

Scores repo readiness across manifest, evidence, evaluation, memory, integration,
and documentation dimensions. This is a local guardrail, not a benchmark score.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load_json(rel_path: str) -> dict | list | None:
    path = ROOT / rel_path
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _chip() -> dict:
    return _load_json("spark-chip.json") or {}


def _project() -> dict:
    return _load_json("spark-researcher.project.json") or {}


def check_schema_version() -> bool:
    return _chip().get("schema_version") == "spark-chip.v1"


def check_io_protocol() -> bool:
    io = _chip().get("io_protocol", {})
    return bool(io.get("input") and io.get("output") and io.get("schemas_dir"))


def check_all_four_hooks() -> bool:
    hooks = _chip().get("hooks", {})
    return all(name in hooks for name in ("evaluate", "watchtower", "packets", "suggest"))


def check_frontier_enabled() -> bool:
    return _chip().get("frontier", {}).get("enabled") is True


def check_project_json_valid() -> bool:
    project = _project()
    return bool(
        project.get("candidate_trials")
        and project.get("eval_metric")
        and project.get("chip", {}).get("manifest")
    )


def check_has_research_grounded() -> bool:
    return (ROOT / "research" / "research_grounded").is_dir()


def check_has_benchmark_grounded() -> bool:
    return (ROOT / "research" / "benchmark_grounded").is_dir()


def check_has_exploratory_frontier() -> bool:
    return (ROOT / "research" / "exploratory_frontier").is_dir()


def check_has_realworld_validated() -> bool:
    return (ROOT / "research" / "realworld_validated").is_dir()


def check_primary_metric() -> bool:
    return bool(_project().get("eval_metric"))


def check_scoring_logic() -> bool:
    project = _project()
    return bool(project.get("eval_metric") and project.get("multiple_metrics"))


def check_baseline_trial() -> bool:
    trials = _project().get("candidate_trials", [])
    return any(trial.get("name") == "baseline" for trial in trials)


def check_required_fields_set() -> bool:
    fields = _project().get("required_fields_set", [])
    return isinstance(fields, list) and len(fields) >= 3


def check_field_patterns_set() -> bool:
    patterns = _project().get("field_patterns_set")
    return isinstance(patterns, dict) and len(patterns) >= 3


def check_multiple_metrics() -> bool:
    metrics = _project().get("multiple_metrics", [])
    return isinstance(metrics, list) and len(metrics) >= 2


def check_candidate_trials() -> bool:
    trials = _project().get("candidate_trials", [])
    return isinstance(trials, list) and len(trials) >= 2


def check_source_registry() -> bool:
    return (ROOT / "schemas").is_dir() and any((ROOT / "schemas").glob("*.json"))


def check_packet_schema() -> bool:
    return any((ROOT / "schemas").glob("*packet*.json")) if (ROOT / "schemas").is_dir() else False


def check_memory_backend() -> bool:
    return bool(_project().get("memory", {}).get("backend"))


def check_obsidian_vault() -> bool:
    vault = _project().get("obsidian_vault", "")
    return bool(vault) and (ROOT / vault).is_dir()


def check_chip_path_set() -> bool:
    return bool(_project().get("chip", {}).get("path"))


def check_commands_defined() -> bool:
    return bool(_project().get("commands"))


def check_guardrails_set() -> bool:
    return bool(_project().get("guardrails"))


def check_watchtower_pages() -> bool:
    pages = _project().get("watchtower_pages", [])
    return isinstance(pages, list) and len(pages) >= 1


def check_self_edit_config() -> bool:
    config = _project().get("self_edit_config", {})
    return bool(config.get("allowed_targets"))


def check_readme_exists() -> bool:
    return (ROOT / "README.md").exists()


def check_architecture_docs() -> bool:
    return (ROOT / "docs").is_dir() and any((ROOT / "docs").glob("*.md"))


def check_docs_directory() -> bool:
    return (ROOT / "docs").is_dir()


def check_pyproject_valid() -> bool:
    return (ROOT / "pyproject.toml").exists()


def check_mission_docs() -> bool:
    mission_docs = _project().get("mission_docs", "")
    return bool(mission_docs) and (ROOT / mission_docs).exists()


CHECKS: list[tuple[str, str, int, callable]] = [
    ("schema_version", "manifest_validity", 3, check_schema_version),
    ("io_protocol", "manifest_validity", 3, check_io_protocol),
    ("all_four_hooks", "manifest_validity", 4, check_all_four_hooks),
    ("frontier_enabled", "manifest_validity", 3, check_frontier_enabled),
    ("project_json_valid", "manifest_validity", 2, check_project_json_valid),
    ("has_research_grounded", "evidence_separation", 5, check_has_research_grounded),
    ("has_benchmark_grounded", "evidence_separation", 5, check_has_benchmark_grounded),
    ("has_exploratory_frontier", "evidence_separation", 5, check_has_exploratory_frontier),
    ("has_realworld_validated", "evidence_separation", 5, check_has_realworld_validated),
    ("primary_metric", "evaluation_depth", 4, check_primary_metric),
    ("scoring_logic", "evaluation_depth", 4, check_scoring_logic),
    ("baseline_trial", "evaluation_depth", 4, check_baseline_trial),
    ("required_fields_set", "evaluation_depth", 2, check_required_fields_set),
    ("field_patterns_set", "evaluation_depth", 2, check_field_patterns_set),
    ("multiple_metrics", "evaluation_depth", 2, check_multiple_metrics),
    ("candidate_trials", "evaluation_depth", 2, check_candidate_trials),
    ("source_registry", "memory_knowledge", 3, check_source_registry),
    ("packet_schema", "memory_knowledge", 3, check_packet_schema),
    ("memory_backend", "memory_knowledge", 3, check_memory_backend),
    ("obsidian_vault", "memory_knowledge", 6, check_obsidian_vault),
    ("chip_path_set", "integration_health", 3, check_chip_path_set),
    ("commands_defined", "integration_health", 3, check_commands_defined),
    ("guardrails_set", "integration_health", 3, check_guardrails_set),
    ("watchtower_pages", "integration_health", 3, check_watchtower_pages),
    ("self_edit_config", "integration_health", 3, check_self_edit_config),
    ("readme_exists", "documentation", 4, check_readme_exists),
    ("architecture_docs", "documentation", 4, check_architecture_docs),
    ("docs_directory", "documentation", 2, check_docs_directory),
    ("pyproject_valid", "documentation", 2, check_pyproject_valid),
    ("mission_docs", "documentation", 3, check_mission_docs),
]

DIMENSION_MAX = {
    "manifest_validity": 15,
    "evidence_separation": 20,
    "evaluation_depth": 20,
    "memory_knowledge": 15,
    "integration_health": 15,
    "documentation": 15,
}


def run_evaluation() -> dict:
    passed: list[str] = []
    failed: list[str] = []
    dimension_scores = {name: 0 for name in DIMENSION_MAX}

    print("=" * 60)
    print("  domain-chip-memory - Chip Evaluation")
    print("=" * 60)

    for name, dimension, points, fn in CHECKS:
        try:
            ok = fn()
        except Exception:
            ok = False
        marker = "+" if ok else " "
        print(f"  [{marker}] {name:<30s}  {dimension:<22s}  {'+' + str(points) if ok else '  '}")
        if ok:
            passed.append(name)
            dimension_scores[dimension] += points
        else:
            failed.append(name)

    total = sum(dimension_scores.values())
    verdict = "alpha" if total < 60 else "beta" if total < 80 else "production"

    print()
    print("-" * 60)
    print("  Dimensions:")
    for dimension, max_points in DIMENSION_MAX.items():
        score = dimension_scores[dimension]
        bar_len = int(20 * score / max_points)
        bar = "#" * bar_len + "." * (20 - bar_len)
        print(f"    {dimension:<22s}  [{bar}]  {score}/{max_points}")
    print("-" * 60)
    print(f"  TOTAL SCORE:  {total}/100   ({verdict})")
    print(f"  Passed: {len(passed)}/30   Failed: {len(failed)}/30")
    print("=" * 60)

    return {
        "timestamp": time.time(),
        "total_score": total,
        "verdict": verdict,
        "passed_count": len(passed),
        "failed_count": len(failed),
        "passed_checks": passed,
        "failed_checks": failed,
        "dimensions": [
            {"name": dimension, "score": dimension_scores[dimension], "max_points": max_points}
            for dimension, max_points in DIMENSION_MAX.items()
        ],
    }


def main() -> None:
    entry = run_evaluation()
    history_path = ROOT / "score_history.jsonl"
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
    print(f"\n  Score entry appended to {history_path.name}\n")


if __name__ == "__main__":
    main()

