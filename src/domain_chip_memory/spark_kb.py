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
                "raw/articles/",
                "raw/papers/",
                "raw/repos/",
                "raw/datasets/",
                "raw/assets/",
            ],
            "wiki_files": [
                "wiki/index.md",
                "wiki/log.md",
                "wiki/current-state/_index.md",
                "wiki/evidence/_index.md",
                "wiki/events/_index.md",
                "wiki/sources/_index.md",
                "wiki/syntheses/_index.md",
                "wiki/outputs/_index.md",
            ],
        },
        "compile_rules": [
            "KB pages must preserve provenance, timestamps, session IDs, and turn IDs.",
            "Current-state pages are derived from the SDK current-state view, not ad hoc synthesis.",
            "Evidence and event pages remain inspectable so users can audit why a KB page exists.",
            "The raw/ layer is the intake shelf for governed memory snapshots first, with room for future articles, papers, repos, and datasets.",
            "The wiki/ layer is the compiled markdown surface that should feel Obsidian-friendly and LLM-maintained.",
            "The KB compiler may add links and summaries but must not invent unsupported memory facts.",
        ],
        "llm_workflow": {
            "ingest": "raw memory snapshot JSON is written first, alongside Karpathy-style raw source shelves for future clips and artifacts",
            "compile": "wiki pages are generated from the snapshot into markdown indexes, source pages, and syntheses",
            "query": "future query outputs are saved under wiki/outputs/ and filed back into the visible vault",
            "lint": "future health checks verify links, stale pages, missing indexes, and provenance gaps",
        },
        "health_checks": [
            "required_file_presence",
            "markdown_frontmatter_presence",
            "broken_wikilink_detection",
            "orphan_page_detection",
            "karpathy_layout_presence",
        ],
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
            "- raw/articles/, raw/papers/, raw/repos/, raw/datasets/, and raw/assets/ are reserved for future Karpathy-style source ingest",
            "- wiki/current-state/ contains one page per durable current-state fact",
            "- wiki/evidence/ contains inspectable evidence pages with provenance",
            "- wiki/events/ contains inspectable event pages with provenance",
            "- wiki/sources/ contains source-style pages describing governed snapshot inputs",
            "- wiki/syntheses/ contains compiled overviews and future cross-source syntheses",
            "- wiki/outputs/ contains filed answers and future syntheses",
            "- wiki/index.md and wiki/log.md are AI-maintained navigation surfaces",
            "",
            "## Rules",
            "- Preserve session_id, turn_ids, timestamp, memory_role, and trace metadata",
            "- Link current-state pages back to supporting evidence pages",
            "- Treat raw/ as the intake shelf and wiki/ as the compiled knowledge surface",
            "- Future Obsidian clips and repo artifacts should enter raw/ before being compiled into wiki/",
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
    raw_articles_dir = output_path / "raw" / "articles"
    raw_papers_dir = output_path / "raw" / "papers"
    raw_repos_dir = output_path / "raw" / "repos"
    raw_datasets_dir = output_path / "raw" / "datasets"
    raw_assets_dir = output_path / "raw" / "assets"
    wiki_dir = output_path / "wiki"
    current_state_dir = wiki_dir / "current-state"
    evidence_dir = wiki_dir / "evidence"
    events_dir = wiki_dir / "events"
    sources_dir = wiki_dir / "sources"
    syntheses_dir = wiki_dir / "syntheses"
    outputs_dir = wiki_dir / "outputs"
    attachments_images_dir = wiki_dir / "attachments" / "images"
    for directory in (
        raw_snapshot_dir,
        raw_articles_dir,
        raw_papers_dir,
        raw_repos_dir,
        raw_datasets_dir,
        raw_assets_dir,
        current_state_dir,
        evidence_dir,
        events_dir,
        sources_dir,
        syntheses_dir,
        outputs_dir,
        attachments_images_dir,
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
    snapshot_counts = dict(snapshot.get("counts") or {})

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

    source_pages: list[dict[str, str]] = []
    source_page_path = sources_dir / "spark-memory-snapshot-latest.md"
    source_page_title = "Spark Memory Snapshot Latest"
    source_page_content = [
        _markdown_frontmatter(
            title=source_page_title,
            page_type="source",
            summary="Source page describing the latest governed Spark memory snapshot that compiled this vault.",
            generated_at=generated_at,
            tags=["spark-kb", "source"],
        ),
        f"# {source_page_title}",
        "",
        "## Snapshot File",
        "- `raw/memory-snapshots/latest.json`",
        "",
        "## Snapshot Counts",
        f"- Sessions: `{snapshot_counts.get('session_count', 0)}`",
        f"- Current-state records: `{snapshot_counts.get('current_state_count', 0)}`",
        f"- Observation records: `{snapshot_counts.get('observation_count', 0)}`",
        f"- Event records: `{snapshot_counts.get('event_count', 0)}`",
        "",
        "## Compiler Notes",
        "- This source page is the bridge between governed Spark runtime memory and the visible wiki layer.",
        "- Future Karpathy-style raw sources should enter `raw/` before being compiled into `wiki/`.",
        "",
    ]
    source_page_path.write_text("\n".join(source_page_content), encoding="utf-8")
    source_pages.append(
        {
            "title": source_page_title,
            "link": f"[[sources/{source_page_path.stem}]]",
            "path": str(source_page_path),
        }
    )

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

    synthesis_pages: list[dict[str, str]] = []
    synthesis_page_path = syntheses_dir / "runtime-memory-overview.md"
    synthesis_page_title = "Runtime Memory Overview"
    synthesis_page_content = [
        _markdown_frontmatter(
            title=synthesis_page_title,
            page_type="synthesis",
            summary="Compiled overview that explains how governed Spark memory is surfaced into the visible knowledge base.",
            generated_at=generated_at,
            tags=["spark-kb", "synthesis"],
        ),
        f"# {synthesis_page_title}",
        "",
        "## Overview",
        "- This page is the first compiled synthesis over the current governed Spark memory snapshot.",
        "- It is intentionally downstream of runtime memory, not a second truth store.",
        f"- Source snapshot: [[sources/{source_page_path.stem}]]",
        "",
        "## Current Snapshot Shape",
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
        "## Current-State Highlights",
    ]
    if current_state_pages:
        synthesis_page_content.extend(f"- {item['link']} - {item['title']}" for item in current_state_pages[:10])
    else:
        synthesis_page_content.append("- No current-state pages generated yet.")
    synthesis_page_content.append("")
    synthesis_page_path.write_text("\n".join(synthesis_page_content), encoding="utf-8")
    synthesis_pages.append(
        {
            "title": synthesis_page_title,
            "link": f"[[syntheses/{synthesis_page_path.stem}]]",
            "path": str(synthesis_page_path),
        }
    )

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
    (sources_dir / "_index.md").write_text(
        _render_index_page(
            title="Sources Index",
            generated_at=generated_at,
            summary="Source pages that describe the governed inputs used to compile this vault.",
            section_title="Source Pages",
            items=source_pages,
            tag="sources",
        ),
        encoding="utf-8",
    )
    (syntheses_dir / "_index.md").write_text(
        _render_index_page(
            title="Syntheses Index",
            generated_at=generated_at,
            summary="Compiled overview pages and future cross-source syntheses.",
            section_title="Synthesis Pages",
            items=synthesis_pages,
            tag="syntheses",
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
        f"- Source pages: `{len(source_pages)}`",
        f"- Synthesis pages: `{len(synthesis_pages)}`",
        f"- Current-state pages: `{len(current_state_pages)}`",
        f"- Evidence pages: `{len(evidence_pages)}`",
        f"- Event pages: `{len(event_pages)}`",
        "",
        "## Navigation",
        "- [[sources/_index]]",
        "- [[syntheses/_index]]",
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
                f"- source pages: {len(source_pages)}",
                f"- synthesis pages: {len(synthesis_pages)}",
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
        "source_page_count": len(source_pages),
        "synthesis_page_count": len(synthesis_pages),
        "files_written": sorted(
            str(path.relative_to(output_path))
            for path in output_path.rglob("*")
            if path.is_file()
        ),
    }


def build_spark_kb_health_report(output_dir: str | Path) -> dict[str, Any]:
    output_path = Path(output_dir)
    wiki_dir = output_path / "wiki"
    required_files = [
        output_path / "CLAUDE.md",
        output_path / "raw" / "memory-snapshots" / "latest.json",
        wiki_dir / "index.md",
        wiki_dir / "log.md",
        wiki_dir / "current-state" / "_index.md",
        wiki_dir / "evidence" / "_index.md",
        wiki_dir / "events" / "_index.md",
        wiki_dir / "sources" / "_index.md",
        wiki_dir / "syntheses" / "_index.md",
        wiki_dir / "outputs" / "_index.md",
    ]
    missing_required_files = [
        str(path.relative_to(output_path))
        for path in required_files
        if not path.exists()
    ]

    markdown_files = sorted(path for path in wiki_dir.rglob("*.md") if path.is_file())
    pages_missing_frontmatter: list[str] = []
    inbound_link_counts: dict[str, int] = {}
    broken_wikilinks: list[dict[str, str]] = []

    for path in markdown_files:
        relative_path = str(path.relative_to(output_path)).replace("\\", "/")
        inbound_link_counts.setdefault(relative_path, 0)
        content = path.read_text(encoding="utf-8")
        if relative_path != "wiki/log.md" and not content.startswith("---\n"):
            pages_missing_frontmatter.append(relative_path)
        for link in _extract_wikilinks(content):
            target_relative = _resolve_wikilink_path(output_path, link)
            if target_relative is None:
                broken_wikilinks.append({"source": relative_path, "target": link})
                continue
            inbound_link_counts[target_relative] = inbound_link_counts.get(target_relative, 0) + 1

    orphan_pages = [
        path
        for path, count in sorted(inbound_link_counts.items())
        if count == 0 and not path.endswith("wiki/index.md")
    ]
    return {
        "output_dir": str(output_path),
        "valid": not missing_required_files and not pages_missing_frontmatter and not broken_wikilinks,
        "required_file_count": len(required_files),
        "missing_required_files": missing_required_files,
        "markdown_page_count": len(markdown_files),
        "pages_missing_frontmatter": pages_missing_frontmatter,
        "broken_wikilinks": broken_wikilinks,
        "orphan_pages": orphan_pages,
        "trace": {
            "operation": "spark_kb_health_check",
            "checked_at": _utc_timestamp(),
        },
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


def _extract_wikilinks(text: str) -> list[str]:
    return [match.group(1).split("|", 1)[0].strip() for match in re.finditer(r"\[\[([^\]]+)\]\]", text)]


def _resolve_wikilink_path(output_path: Path, link: str) -> str | None:
    normalized = link.strip().replace("\\", "/").strip("/")
    if not normalized:
        return None
    target_path = output_path / "wiki" / f"{normalized}.md"
    if target_path.exists():
        return str(target_path.relative_to(output_path)).replace("\\", "/")
    return None


def json_dumps(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, indent=2) + "\n"
