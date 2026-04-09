from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _run_command(args: list[str], *, cwd: Path) -> None:
    subprocess.run(args, check=True, cwd=str(cwd))


def main() -> None:
    script_path = Path(__file__).resolve()
    examples_dir = script_path.parent
    repo_root = script_path.parents[2]

    parser = argparse.ArgumentParser(description="Run the checked-in Spark KB example wrappers and collect one aggregate summary.")
    parser.add_argument(
        "--write-dir",
        default=str(repo_root / "tmp" / "example_smoke_artifacts"),
        help="Directory where wrapper outputs and aggregate summary should be written.",
    )
    args = parser.parse_args()

    write_dir = Path(args.write_dir)
    write_dir.mkdir(parents=True, exist_ok=True)

    spark_kb_write_dir = write_dir / "spark_kb"
    spark_kb_invalid_write_dir = write_dir / "spark_kb_invalid"

    _run_command(
        [
            sys.executable,
            str(examples_dir / "spark_kb" / "run_smoke.py"),
            "--write-dir",
            str(spark_kb_write_dir),
            "--output-dir",
            str(write_dir / "spark_kb_vault"),
        ],
        cwd=repo_root,
    )
    _run_command(
        [
            sys.executable,
            str(examples_dir / "spark_kb_invalid" / "run_validate_failure.py"),
            "--write-dir",
            str(spark_kb_invalid_write_dir),
        ],
        cwd=repo_root,
    )

    spark_kb_summary = json.loads((spark_kb_write_dir / "summary.json").read_text(encoding="utf-8"))
    spark_kb_invalid_summary = json.loads((spark_kb_invalid_write_dir / "summary.json").read_text(encoding="utf-8"))
    aggregate = {
        "write_dir": str(write_dir),
        "runs": {
            "spark_kb": spark_kb_summary,
            "spark_kb_invalid": spark_kb_invalid_summary,
        },
        "all_expected_results_observed": (
            bool(spark_kb_summary.get("validation_valid"))
            and bool(spark_kb_summary.get("health_valid"))
            and not bool(spark_kb_invalid_summary.get("validation_valid"))
            and not bool(spark_kb_invalid_summary.get("snapshot_valid"))
        ),
    }
    (write_dir / "summary.json").write_text(json.dumps(aggregate, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(aggregate, indent=2))


if __name__ == "__main__":
    main()
