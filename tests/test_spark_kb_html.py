import json
import sys
from pathlib import Path

from domain_chip_memory import cli
from domain_chip_memory.spark_kb import scaffold_spark_knowledge_base
from domain_chip_memory.spark_kb_html import render_spark_kb_html_artifact


def _snapshot() -> dict:
    return {
        "runtime_class": "SparkMemorySDK",
        "generated_at": "2026-05-09T07:00:00+00:00",
        "counts": {
            "session_count": 1,
            "current_state_count": 1,
            "observation_count": 1,
            "event_count": 1,
        },
        "sessions": [
            {
                "session_id": "builder-session-1",
                "timestamp": "2026-05-09T06:45:00+00:00",
                "turns": [
                    {
                        "turn_id": "builder-session-1:t1",
                        "speaker": "user",
                        "text": "Turn the LLM wiki into a visual dashboard.",
                        "timestamp": "2026-05-09T06:45:00+00:00",
                    }
                ],
            }
        ],
        "current_state": [
            {
                "memory_role": "current_state",
                "subject": "project",
                "predicate": "next_interface",
                "text": "timeline visual dashboard",
                "session_id": "builder-session-1",
                "turn_ids": ["builder-session-1:t1"],
                "timestamp": "2026-05-09T06:50:00+00:00",
                "metadata": {"value": "timeline visual dashboard"},
            }
        ],
        "observations": [
            {
                "memory_role": "structured_evidence",
                "subject": "project",
                "predicate": "next_interface",
                "text": "The wiki should become a timeline dashboard over Spark memory.",
                "session_id": "builder-session-1",
                "turn_ids": ["builder-session-1:t1"],
                "timestamp": "2026-05-09T06:46:00+00:00",
                "metadata": {"observation_id": "obs-dashboard-1"},
            }
        ],
        "events": [
            {
                "memory_role": "event",
                "subject": "project",
                "predicate": "artifact_design_requested",
                "text": "Visual dashboard layer requested for LLM wiki packets.",
                "session_id": "builder-session-1",
                "turn_ids": ["builder-session-1:t1"],
                "timestamp": "2026-05-09T06:47:00+00:00",
                "metadata": {"event_id": "event-dashboard-1"},
            }
        ],
        "trace": {"operation": "export_knowledge_base_snapshot"},
    }


def test_render_spark_kb_html_artifact_builds_timeline_dashboard(tmp_path: Path):
    vault_dir = tmp_path / "spark_kb_vault"
    scaffold_spark_knowledge_base(vault_dir, _snapshot())

    payload = render_spark_kb_html_artifact(vault_dir)

    html_file = Path(payload["artifact_file"])
    trace_file = Path(payload["trace_file"])
    canvas_board_file = Path(payload["visionboard_board_file"])
    html = html_file.read_text(encoding="utf-8")
    trace = json.loads(trace_file.read_text(encoding="utf-8"))
    canvas_board = json.loads(canvas_board_file.read_text(encoding="utf-8"))

    assert payload["contract_name"] == "SparkKbHtmlArtifact"
    assert html_file.exists()
    assert trace_file.exists()
    assert canvas_board_file.exists()
    assert "Memory Movement Timeline" in html
    assert "Spark LLM Wiki" in html
    assert "Spark Agent Brain" in html
    assert "LLM Wiki" in html
    assert "spark-mark" in html
    assert "spark-wordmark" in html
    assert "<span>/</span>wiki" in html
    assert "hero-lockup" in html
    assert "theme-toggle" in html
    assert "data-theme=\"light\"" in html
    assert "Telegram prompts" in html
    assert "Source-aware search" in html
    assert "data-search-mode=\"current\"" in html
    assert "data-search-mode=\"evidence\"" in html
    assert "data-search-scope=\"supporting current\"" in html
    assert "Comments & Annotations" in html
    assert "sparkKbAnnotations" in html
    assert "copy-annotation-packet" in html
    assert "spark-kb-annotation.v1" in html
    assert "timeline-shell" in html
    assert "timeline-spine" in html
    assert "Spark Memory Flow" in html
    assert "Visionboard JSON" in html
    assert "spark-kb-visionboard-board.json" in html
    assert "Artifact Manifest" in html
    assert "Spark Visionboard" in html
    assert "Create Visionboard" in html
    assert "Spark Visionboard projection" in html
    assert ".main { order: 1; }" in html
    assert "spark-visionboard-board.v1" in html
    assert "data-canvas-object-id" in html
    assert "http://localhost:3000/api/visionboard" in html
    assert "builder-bridge-input" in html
    assert "selected-inspector" in html
    assert "sparkVisionboardApiBaseUrl" in html
    assert "source_links" in html
    assert "data-action=\"generate_diagram\"" in html
    assert "--spark-accent" in html
    assert "#2FCA94" in html
    assert "/wiki" in html
    assert "Instrument Serif" not in html
    assert "heat 5/5" not in html
    assert payload["timeline_item_count"] == 4
    assert payload["kind_counts"]["current_state"] == 1
    assert payload["family_counts"]["memory_kb_current_state"] == 1
    assert payload["visionboard_board"]["schema"] == "spark-visionboard-board.v1"
    assert payload["visionboard_board"]["object_type_counts"]["connector"] >= 1
    assert canvas_board["schema"] == "spark-visionboard-board.v1"
    assert canvas_board["board"]["objects"]["kb-vault"]["type"] == "shape"
    assert trace["operation"] == "render_spark_kb_html_artifact"
    assert trace["artifact_outputs"]["visionboard_board_href"] == "spark-kb-visionboard-board.json"
    assert trace["timeline_item_count"] == 4
    assert trace["source_snapshot_file"].endswith("raw\\memory-snapshots\\latest.json") or trace["source_snapshot_file"].endswith(
        "raw/memory-snapshots/latest.json"
    )
    assert "Current-state APIs outrank wiki summaries for mutable user facts." in trace["non_override_rules"]


def test_render_spark_kb_html_artifact_builds_recursive_learning_journal(tmp_path: Path, monkeypatch):
    vault_dir = tmp_path / "spark_kb_vault"
    wiki_root = tmp_path / "llm_wiki"
    scaffold_spark_knowledge_base(vault_dir, _snapshot())
    _write_recursive_record(
        wiki_root,
        latest_lesson=(
            "Use sscli_v1.secretpayload and access_token=abc123456789secret from "
            "C:\\Users\\USER\\Desktop\\private\\trace.json after Command failed: python -m unsafe"
        ),
    )
    monkeypatch.setenv("SPARK_RECURSIVE_WIKI_ROOT", str(wiki_root))
    monkeypatch.setenv("SPARK_LLM_WIKI_ROOT", str(wiki_root))

    payload = render_spark_kb_html_artifact(vault_dir)

    html_file = Path(payload["artifact_file"])
    html = html_file.read_text(encoding="utf-8")
    journal_index = html_file.parent / "recursive-learning" / "index.html"
    path_page = html_file.parent / "recursive-learning" / "spark-qa-operator" / "index.html"
    run_page = html_file.parent / "recursive-learning" / "spark-qa-operator" / "2026-05-13" / "s1.html"
    run_html = run_page.read_text(encoding="utf-8")

    assert payload["recursive_record_count"] >= 1
    assert payload["recursive_journal"]["record_count"] >= 1
    assert journal_index.exists()
    assert path_page.exists()
    assert run_page.exists()
    assert "What Spark Learned Recently" in html
    assert "Spark QA Operator updated the learning journal." in html
    assert "Recursive Learning Journal" in html
    assert "recursive-learning/index.html" in html
    assert "Comments & Annotations" in html
    assert "Promote to lesson" in html
    assert "Ready for review" in html
    assert "annotation_queue_count" in html
    assert payload["trace"]["annotation_queue_count"] >= 1
    assert "data-search-scope=\"recursive historical evidence private supporting\"" in html
    assert "What Spark learned" in run_html
    assert "[redacted workspace token]" in html
    assert "[redacted]" in html
    assert "[local path]" in html
    assert "sscli_v1.secretpayload" not in html
    assert "abc123456789secret" not in html
    assert "python -m unsafe" not in html
    assert "C:\\Users\\USER\\Desktop\\private" not in html
    assert "sscli_v1.secretpayload" not in run_html


def test_render_spark_kb_html_artifact_command_writes_summary(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}
    vault_dir = tmp_path / "spark_kb_vault"
    html_file = tmp_path / "artifact" / "dashboard.html"
    trace_file = tmp_path / "artifact" / "dashboard.trace.json"
    canvas_board_file = tmp_path / "artifact" / "dashboard.visionboard.json"
    summary_file = tmp_path / "artifact" / "summary.json"
    scaffold_spark_knowledge_base(vault_dir, _snapshot())

    monkeypatch.setattr(cli, "_print", lambda payload: captured.setdefault("payload", payload))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "render-spark-kb-html-artifact",
            str(vault_dir),
            "--output",
            str(html_file),
            "--trace",
            str(trace_file),
            "--visionboard-board",
            str(canvas_board_file),
            "--write",
            str(summary_file),
        ],
    )

    cli.main()

    payload = captured["payload"]
    written = json.loads(summary_file.read_text(encoding="utf-8"))
    assert payload == written
    assert html_file.exists()
    assert trace_file.exists()
    assert canvas_board_file.exists()
    assert payload["artifact_file"] == str(html_file)
    assert payload["recursive_journal"]["record_count"] >= 0
    assert payload["visionboard_board_file"] == str(canvas_board_file)
    assert payload["trace"]["operation"] == "render_spark_kb_html_artifact"


def test_build_spark_kb_command_can_render_html_artifact(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}
    snapshot_file = tmp_path / "snapshot.json"
    vault_dir = tmp_path / "spark_kb_vault"
    html_file = tmp_path / "artifact" / "dashboard.html"
    trace_file = tmp_path / "artifact" / "dashboard.trace.json"
    canvas_board_file = tmp_path / "artifact" / "dashboard.visionboard.json"
    snapshot_file.write_text(json.dumps(_snapshot()), encoding="utf-8")

    monkeypatch.setattr(cli, "_print", lambda payload: captured.setdefault("payload", payload))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "build-spark-kb",
            str(snapshot_file),
            str(vault_dir),
            "--html-artifact",
            "--html-output",
            str(html_file),
            "--html-trace",
            str(trace_file),
            "--visionboard-board",
            str(canvas_board_file),
        ],
    )

    cli.main()

    payload = captured["payload"]
    assert payload["compile_result"]["output_dir"] == str(vault_dir)
    assert payload["html_artifact_result"]["artifact_file"] == str(html_file)
    assert payload["html_artifact_result"]["visionboard_board"]["schema"] == "spark-visionboard-board.v1"
    assert html_file.exists()
    assert trace_file.exists()
    assert canvas_board_file.exists()
    assert (html_file.parent / "recursive-learning" / "index.html").exists()


def _write_recursive_record(root: Path, *, latest_lesson: str) -> Path:
    run_dir = root / "recursive-runs" / "spark-qa-operator" / "2026-05-13"
    run_dir.mkdir(parents=True, exist_ok=True)
    source_html = run_dir / "s1-source.html"
    source_html.write_text("<html><body>source capsule</body></html>", encoding="utf-8")
    metadata = {
        "schemaVersion": "spark-recursive-wiki-pairing.v1",
        "authority": "supporting_not_authoritative",
        "category": "recursive_self_improvement_loop",
        "pathKey": "spark-qa-operator",
        "pathLabel": "Spark QA Operator",
        "day": "2026-05-13",
        "sessionId": "s1",
        "generatedAt": "2026-05-13T10:00:00+00:00",
        "htmlPath": str(source_html),
        "result": {
            "stopReason": "completed_requested_rounds",
            "completedRounds": 2,
            "requestedRounds": 2,
            "keptRounds": 1,
            "revertedRounds": 1,
            "currentScore": 0.91,
            "bestScore": 0.94,
            "latestMutationIntentSummary": latest_lesson,
        },
        "userFacingSummary": "Spark QA Operator kept a source-backed candidate.",
        "boundaries": [
            "Wiki capsules are historical learning notes, not live runtime truth.",
            "Promotion still requires benchmark evidence, held-out/trap checks, privacy review, and human/system review gates.",
        ],
    }
    metadata_path = run_dir / "s1.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (root / "recursive-runs" / "index.html").write_text("<html><body>recursive index</body></html>", encoding="utf-8")
    return metadata_path


def test_build_spark_wiki_dashboard_command_compiles_and_renders_snapshot(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}
    snapshot_file = tmp_path / "snapshot.json"
    vault_dir = tmp_path / "spark_kb_vault"
    html_file = tmp_path / "artifact" / "dashboard.html"
    trace_file = tmp_path / "artifact" / "dashboard.trace.json"
    canvas_board_file = tmp_path / "artifact" / "dashboard.visionboard.json"
    snapshot_file.write_text(json.dumps(_snapshot()), encoding="utf-8")

    monkeypatch.setattr(cli, "_print", lambda payload: captured.setdefault("payload", payload))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "domain_chip_memory.cli",
            "build-spark-wiki-dashboard",
            str(snapshot_file),
            str(vault_dir),
            "--source",
            "snapshot",
            "--html-output",
            str(html_file),
            "--html-trace",
            str(trace_file),
            "--visionboard-board",
            str(canvas_board_file),
        ],
    )

    cli.main()

    payload = captured["payload"]
    assert payload["dashboard_command"]["source_mode"] == "snapshot"
    assert payload["html_artifact_result"]["artifact_file"] == str(html_file)
    assert payload["html_artifact_result"]["visionboard_board"]["schema"] == "spark-visionboard-board.v1"
    assert html_file.exists()
    assert trace_file.exists()
    assert canvas_board_file.exists()
