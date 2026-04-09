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
    example_dir = script_path.parent
    repo_root = script_path.parents[3]

    parser = argparse.ArgumentParser(description="Run the checked-in invalid Spark KB example through validator preflight and capture its failure summary.")
    parser.add_argument(
        "--write-dir",
        default=str(repo_root / "tmp" / "spark_kb_invalid_artifacts"),
        help="Directory where validation and summary JSON outputs should be written.",
    )
    args = parser.parse_args()

    write_dir = Path(args.write_dir)
    write_dir.mkdir(parents=True, exist_ok=True)

    validation_output = write_dir / "validation.json"
    summary_output = write_dir / "summary.json"

    _run_command(
        [
            sys.executable,
            "-m",
            "domain_chip_memory.cli",
            "validate-spark-kb-inputs",
            str(example_dir / "snapshot.json"),
            "--repo-source-manifest",
            str(example_dir / "repo-sources.json"),
            "--filed-output-file",
            str(example_dir / "bad-output.json"),
            "--filed-output-manifest",
            str(example_dir / "filed-outputs.json"),
            "--write",
            str(validation_output),
        ],
        cwd=repo_root,
    )

    validation_payload = json.loads(validation_output.read_text(encoding="utf-8"))
    summary = {
        "example_dir": str(example_dir),
        "write_dir": str(write_dir),
        "validation_valid": bool(validation_payload.get("valid")),
        "snapshot_valid": bool(validation_payload.get("snapshot_valid")),
        "missing_repo_source_file_count": len(list(validation_payload.get("missing_repo_source_files") or [])),
        "filed_output_manifest_error_count": len(list(validation_payload.get("filed_output_manifest_errors") or [])),
        "filed_output_file_error_count": len(list(validation_payload.get("filed_output_file_errors") or [])),
        "artifacts": {
            "validation": str(validation_output),
        },
    }
    summary_output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
