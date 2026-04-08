from __future__ import annotations

from datetime import datetime, timezone
import re
from pathlib import Path
from typing import Any


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower())
    return normalized.strip("-") or "item"


def _yaml_scalar(value: str) -> str:
    escaped = str(value).replace('"', '\\"')
    return f'"{escaped}"'


def _markdown_frontmatter(
    *,
    title: str,
    page_type: str,
    summary: str,
    generated_at: str,
    tags: list[str],
) -> str:
    tag_text = ", ".join(tags)
    return "\n".join(
        [
            "---",
            f"title: {_yaml_scalar(title)}",
            f"date_created: {generated_at[:10]}",
            f"date_modified: {generated_at[:10]}",
            f"summary: {_yaml_scalar(summary)}",
            f"tags: [{tag_text}]",
            f"type: {page_type}",
            "status: generated",
            "---",
            "",
        ]
    )


def _render_record_details(record: dict[str, Any]) -> str:
    turn_ids = record.get("turn_ids") or []
    metadata = record.get("metadata") or {}
    metadata_lines = [f"- `{key}`: `{value}`" for key, value in sorted(metadata.items())]
    lines = [
        f"- Session: `{record.get('session_id', '')}`",
        f"- Turns: `{', '.join(turn_ids)}`" if turn_ids else "- Turns: `[]`",
        f"- Timestamp: `{record.get('timestamp') or 'unknown'}`",
    ]
    lines.extend(metadata_lines)
    return "\n".join(lines)


def build_spark_kb_contract_summary() -> dict[str, Any]:
    return {
        "layer_name": "SparkKnowledgeBase",
        "positioning": (
            "User-visible knowledge-base layer compiled from governed Spark memory, "
            "not an independent memory store."
        ),
        "source_of_truth": [
            "SparkMemorySDK current-state view",
            "SparkMemorySDK structured evidence log",
            "SparkMemorySDK event calendar",
        ],
        "required_exports": [
            "current_state",
            "observations",
            "events",
            "sessions",
            "trace",
        ],
        "vault_layout": {
            "root_files": [
                "CLAUDE.md",
                "raw/memory-snapshots/latest.json",
            ],
            "wiki_files": [
                "wiki/index.md",
                "wiki/log.md",
                "wiki/current-state/_index.md",
                "wiki/evidence/_index.md",
                "wiki/events/_index.md",
                "wiki/outputs/_index.md",
            ],
        },
        "compile_rules": [
            "KB pages must preserve provenance, timestamps, session IDs, and turn IDs.",
            "Current-state pages are derived from the SDK current-state view, not ad hoc synthesis.",
            "Evidence and event pages remain inspectable so users can audit why a KB page exists.",
            "The KB compiler may add links and summaries but must not invent unsupported memory facts.",
        ],
        "llm_workflow": {
            "ingest": "raw memory snapshot JSON is written first",
            "compile": "wiki pages are generated from the snapshot into markdown",
            "query": "future query outputs are saved under wiki/outputs/",
            "lint": "future health checks verify links, stale pages, and provenance gaps",
        },
    }


def build_spark_kb_claude_schema(*, generated_at: str) -> str:
    return "\n".join(
        [
            "# Spark Memory Knowledge Base Schema",
            "",
            "## Overview",
            "This vault is the user-visible knowledge-base layer for Spark memory.",
            "Raw memory snapshots live in raw/memory-snapshots/.",
            "Compiled markdown pages live in wiki/.",
            "The wiki is downstream of governed Spark memory; do not invent unsupported facts.",
            "",
            "## Directories",
            "- raw/memory-snapshots/ contains append-only snapshot exports from SparkMemorySDK",
            "- wiki/current-state/ contains one page per durable current-state fact",
            "- wiki/evidence/ contains inspectable evidence pages with provenance",
            "- wiki/events/ contains inspectable event pages with provenance",
            "- wiki/outputs/ contains filed answers and future syntheses",
            "- wiki/index.md and wiki/log.md are AI-maintained navigation surfaces",
            "",
            "## Rules",
            "- Preserve session_id, turn_ids, timestamp, memory_role, and trace metadata",
            "- Link current-state pages back to supporting evidence pages",
            "- Never replace governed runtime memory; this is a visible compiled layer",
            f"- Initial scaffold generated at {generated_at}",
        ]
    ) + "\n"


def scaffold_spark_knowledge_base(
    output_dir: str | Path,
    snapshot: dict[str, Any],
    *,
    vault_title: str = "Spark Memory Knowledge Base",
) -> dict[str, Any]:
    output_path = Path(output_dir)
    generated_at = str(snapshot.get("generated_at") or _utc_timestamp())
    raw_snapshot_dir = output_path / "raw" / "memory-snapshots"
    wiki_dir = output_path / "wiki"
    current_state_dir = wiki_dir / "current-state"
    evidence_dir = wiki_dir / "evidence"
    events_dir = wiki_dir / "events"
    outputs_dir = wiki_dir / "outputs"
    for directory in (
        raw_snapshot_dir,
        current_state_dir,
        evidence_dir,
        events_dir,
        outputs_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    snapshot_path = raw_snapshot_dir / "latest.json"
    snapshot_path.write_text(json_dumps(snapshot), encoding="utf-8")
    (output_path / "CLAUDE.md").write_text(
        build_spark_kb_claude_schema(generated_at=generated_at),
        encoding="utf-8",
    )

    current_state_entries = list(snapshot.get("current_state") or [])
    observation_entries = list(snapshot.get("observations") or [])
    event_entries = list(snapshot.get("events") or [])

    evidence_links_by_turn: dict[tuple[str, str], list[str]] = {}
    evidence_pages: list[dict[str, str]] = []
    for record in observation_entries:
        page_slug = _slugify(record.get("metadata", {}).get("observation_id") or record.get("text") or "evidence")
        file_name = f"{page_slug}.md"
        page_path = evidence_dir / file_name
        title = f"Evidence {record.get('metadata', {}).get('observation_id') or page_slug}"
        summary = f"Structured evidence for {record.get('subject', 'unknown')} {record.get('predicate', 'memory')}."
        content = [
            _markdown_frontmatter(
                title=title,
                page_type="evidence",
                summary=summary,
                generated_at=generated_at,
                tags=["spark-kb", "evidence"],
            ),
            f"# {title}",
            "",
            f"## Text",
            str(record.get("text") or ""),
            "",
            "## Provenance",
            _render_record_details(record),
            "",
        ]
        page_path.write_text("\n".join(content), encoding="utf-8")
        link_label = f"[[evidence/{page_path.stem}]]"
        evidence_pages.append({"title": title, "link": link_label, "path": str(page_path)})
        for turn_id in record.get("turn_ids") or []:
            key = (str(record.get("session_id") or ""), str(turn_id))
            evidence_links_by_turn.setdefault(key, []).append(link_label)

    event_pages: list[dict[str, str]] = []
    for record in event_entries:
        page_slug = _slugify(record.get("metadata", {}).get("event_id") or record.get("text") or "event")
        page_path = events_dir / f"{page_slug}.md"
        title = f"Event {record.get('metadata', {}).get('event_id') or page_slug}"
        summary = f"Event memory for {record.get('subject', 'unknown')} {record.get('predicate', 'event')}."
        content = [
            _markdown_frontmatter(
                title=title,
                page_type="event",
                summary=summary,
                generated_at=generated_at,
                tags=["spark-kb", "event"],
            ),
            f"# {title}",
            "",
            "## Text",
            str(record.get("text") or ""),
            "",
            "## Provenance",
            _render_record_details(record),
            "",
        ]
        page_path.write_text("\n".join(content), encoding="utf-8")
        event_pages.append({"title": title, "link": f"[[events/{page_path.stem}]]", "path": str(page_path)})

    current_state_pages: list[dict[str, str]] = []
    for record in current_state_entries:
        subject = str(record.get("subject") or "unknown")
        predicate = str(record.get("predicate") or "unknown")
        value = str(record.get("metadata", {}).get("value") or record.get("text") or "").strip()
        page_path = current_state_dir / f"{_slugify(subject)}-{_slugify(predicate)}.md"
        title = f"{subject} {predicate}".replace("_", " ").title()
        summary = f"Current-state memory for {subject} {predicate}."
        provenance_links: list[str] = []
        for turn_id in record.get("turn_ids") or []:
            provenance_links.extend(evidence_links_by_turn.get((str(record.get("session_id") or ""), str(turn_id)), []))
        provenance_links = sorted(set(provenance_links))
        content = [
            _markdown_frontmatter(
                title=title,
                page_type="current_state",
                summary=summary,
                generated_at=generated_at,
                tags=["spark-kb", "current-state"],
            ),
            f"# {title}",
            "",
            "## Value",
            value or "Unknown",
            "",
            "## Provenance",
            _render_record_details(record),
            "",
            "## Supporting Evidence",
        ]
        if provenance_links:
            content.extend(f"- {link}" for link in provenance_links)
        else:
            content.append("- No linked evidence pages were found in this snapshot.")
        content.append("")
        page_path.write_text("\n".join(content), encoding="utf-8")
        current_state_pages.append({"title": title, "link": f"[[current-state/{page_path.stem}]]", "path": str(page_path)})

    (current_state_dir / "_index.md").write_text(
        _render_index_page(
            title="Current State Index",
            generated_at=generated_at,
            summary="Visible current-state facts exported from SparkMemorySDK.",
            section_title="Current-State Pages",
            items=current_state_pages,
            tag="current-state",
        ),
        encoding="utf-8",
    )
    (evidence_dir / "_index.md").write_text(
        _render_index_page(
            title="Evidence Index",
            generated_at=generated_at,
            summary="Inspectable evidence pages exported from SparkMemorySDK.",
            section_title="Evidence Pages",
            items=evidence_pages,
            tag="evidence",
        ),
        encoding="utf-8",
    )
    (events_dir / "_index.md").write_text(
        _render_index_page(
            title="Events Index",
            generated_at=generated_at,
            summary="Inspectable event pages exported from SparkMemorySDK.",
            section_title="Event Pages",
            items=event_pages,
            tag="events",
        ),
        encoding="utf-8",
    )
    (outputs_dir / "_index.md").write_text(
        _render_index_page(
            title="Outputs Index",
            generated_at=generated_at,
            summary="Reserved for future Spark KB answers and syntheses.",
            section_title="Output Pages",
            items=[],
            tag="outputs",
        ),
        encoding="utf-8",
    )

    index_content = [
        _markdown_frontmatter(
            title=vault_title,
            page_type="index",
            summary="Top-level navigation for the Spark memory knowledge base.",
            generated_at=generated_at,
            tags=["spark-kb", "index"],
        ),
        f"# {vault_title}",
        "",
        "## Overview",
        f"- Generated at `{generated_at}`",
        f"- Current-state pages: `{len(current_state_pages)}`",
        f"- Evidence pages: `{len(evidence_pages)}`",
        f"- Event pages: `{len(event_pages)}`",
        "",
        "## Navigation",
        "- [[current-state/_index]]",
        "- [[evidence/_index]]",
        "- [[events/_index]]",
        "- [[outputs/_index]]",
        "",
    ]
    (wiki_dir / "index.md").write_text("\n".join(index_content), encoding="utf-8")
    (wiki_dir / "log.md").write_text(
        "\n".join(
            [
                "# Spark KB Log",
                "",
                f"- [{generated_at}] scaffolded visible Spark KB from governed memory snapshot",
                f"- current-state pages: {len(current_state_pages)}",
                f"- evidence pages: {len(evidence_pages)}",
                f"- event pages: {len(event_pages)}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    return {
        "output_dir": str(output_path),
        "snapshot_file": str(snapshot_path),
        "generated_at": generated_at,
        "current_state_page_count": len(current_state_pages),
        "evidence_page_count": len(evidence_pages),
        "event_page_count": len(event_pages),
        "files_written": sorted(
            str(path.relative_to(output_path))
            for path in output_path.rglob("*")
            if path.is_file()
        ),
    }


def _render_index_page(
    *,
    title: str,
    generated_at: str,
    summary: str,
    section_title: str,
    items: list[dict[str, str]],
    tag: str,
) -> str:
    lines = [
        _markdown_frontmatter(
            title=title,
            page_type="index",
            summary=summary,
            generated_at=generated_at,
            tags=["spark-kb", tag],
        ),
        f"# {title}",
        "",
        f"## {section_title}",
    ]
    if items:
        lines.extend(f"- {item['link']} - {item['title']}" for item in items)
    else:
        lines.append("- No pages generated yet.")
    lines.append("")
    return "\n".join(lines)


def json_dumps(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, indent=2) + "\n"
