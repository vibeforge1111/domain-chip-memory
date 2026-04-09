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

    parser = argparse.ArgumentParser(description="Run the checked-in Spark KB example through validate, build, and health-check CLI steps.")
    parser.add_argument(
        "--output-dir",
        default=str(repo_root / "tmp" / "spark_kb_example"),
        help="Directory where the example vault should be built.",
    )
    parser.add_argument(
        "--write-dir",
        default=str(repo_root / "tmp" / "spark_kb_example_artifacts"),
        help="Directory where validation/build/health JSON outputs should be written.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    write_dir = Path(args.write_dir)
    write_dir.mkdir(parents=True, exist_ok=True)

    validation_output = write_dir / "validation.json"
    build_output = write_dir / "build.json"
    health_output = write_dir / "health.json"
    summary_output = write_dir / "summary.json"

    common_inputs = [
        str(example_dir / "snapshot.json"),
        "--repo-source-manifest",
        str(example_dir / "manifests" / "repo_sources.json"),
        "--filed-output-manifest",
        str(example_dir / "manifests" / "filed_outputs.json"),
    ]

    _run_command(
        [
            sys.executable,
            "-m",
            "domain_chip_memory.cli",
            "validate-spark-kb-inputs",
            *common_inputs,
            "--write",
            str(validation_output),
        ],
        cwd=repo_root,
    )
    _run_command(
        [
            sys.executable,
            "-m",
            "domain_chip_memory.cli",
            "build-spark-kb",
            str(example_dir / "snapshot.json"),
            str(output_dir),
            "--repo-source-manifest",
            str(example_dir / "manifests" / "repo_sources.json"),
            "--filed-output-manifest",
            str(example_dir / "manifests" / "filed_outputs.json"),
            "--write",
            str(build_output),
        ],
        cwd=repo_root,
    )
    _run_command(
        [
            sys.executable,
            "-m",
            "domain_chip_memory.cli",
            "spark-kb-health-check",
            str(output_dir),
            "--write",
            str(health_output),
        ],
        cwd=repo_root,
    )

    validation_payload = json.loads(validation_output.read_text(encoding="utf-8"))
    build_payload = json.loads(build_output.read_text(encoding="utf-8"))
    health_payload = json.loads(health_output.read_text(encoding="utf-8"))
    summary = {
        "example_dir": str(example_dir),
        "output_dir": str(output_dir),
        "write_dir": str(write_dir),
        "validation_valid": bool(validation_payload.get("valid")),
        "build_repo_source_count": int(build_payload.get("compile_result", {}).get("repo_source_count", 0)),
        "build_filed_output_count": int(build_payload.get("compile_result", {}).get("filed_output_count", 0)),
        "health_valid": bool(health_payload.get("valid")),
        "artifacts": {
            "validation": str(validation_output),
            "build": str(build_output),
            "health": str(health_output),
        },
    }
    summary_output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
