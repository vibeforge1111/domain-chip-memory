from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_timestamp(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).isoformat()
    except ValueError:
        return text


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _html_rel(path: Path, html_file: Path) -> str:
    return Path(os.path.relpath(path.resolve(), html_file.parent.resolve())).as_posix()


def _safe_html_rel(path: Path, html_file: Path) -> str:
    try:
        return _html_rel(path, html_file)
    except ValueError:
        try:
            return Path(path).resolve().as_uri()
        except ValueError:
            return path.as_posix()


def _strip_quotes(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        return cleaned[1:-1].replace('\\"', '"')
    return cleaned


def _parse_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    if not raw.startswith("---\n"):
        return {}, raw
    lines = raw.splitlines()
    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
    if end_index is None:
        return {}, raw
    frontmatter: dict[str, str] = {}
    for line in lines[1:end_index]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = _strip_quotes(value.strip())
    body = "\n".join(lines[end_index + 1 :])
    return frontmatter, body


def _title_from_body(body: str, fallback: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _plain_excerpt(body: str, max_chars: int = 220) -> str:
    cleaned_lines: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        stripped = re.sub(r"`([^`]+)`", r"\1", stripped)
        stripped = re.sub(r"\[\[([^|\]]+)\|?([^\]]*)\]\]", lambda m: m.group(2) or m.group(1), stripped)
        stripped = re.sub(r"[*_>#-]+", "", stripped).strip()
        if stripped:
            cleaned_lines.append(stripped)
    excerpt = " ".join(cleaned_lines)
    if len(excerpt) > max_chars:
        return excerpt[: max_chars - 1].rstrip() + "..."
    return excerpt


def _load_snapshot(kb_dir: Path) -> tuple[dict[str, Any], Path | None]:
    snapshot_file = kb_dir / "raw" / "memory-snapshots" / "latest.json"
    if not snapshot_file.exists():
        return {}, None
    return json.loads(snapshot_file.read_text(encoding="utf-8")), snapshot_file


def _read_pages(kb_dir: Path, html_file: Path) -> list[dict[str, Any]]:
    wiki_dir = kb_dir / "wiki"
    pages: list[dict[str, Any]] = []
    if not wiki_dir.exists():
        return pages
    for page_path in sorted(wiki_dir.rglob("*.md")):
        raw = page_path.read_text(encoding="utf-8")
        frontmatter, body = _parse_frontmatter(raw)
        fallback_title = page_path.stem.replace("-", " ").replace("_", " ").title()
        page_type = frontmatter.get("type") or page_path.parent.name.rstrip("s") or "wiki"
        pages.append(
            {
                "title": frontmatter.get("title") or _title_from_body(body, fallback_title),
                "summary": frontmatter.get("summary") or _plain_excerpt(body, 180),
                "excerpt": _plain_excerpt(body),
                "type": page_type,
                "status": frontmatter.get("status", "unknown"),
                "authority": frontmatter.get("authority", "supporting_not_authoritative"),
                "owner_system": frontmatter.get("owner_system", "domain-chip-memory"),
                "wiki_family": frontmatter.get("wiki_family", f"memory_kb_{page_type}"),
                "source_of_truth": frontmatter.get("source_of_truth", "SparkMemorySDK"),
                "freshness": frontmatter.get("freshness", "snapshot_generated"),
                "relative_path": _rel(page_path, kb_dir),
                "href": _safe_html_rel(page_path, html_file),
            }
        )
    return pages


def _record_value(record: dict[str, Any]) -> str:
    metadata = record.get("metadata") or {}
    value = str(metadata.get("value") or "").strip()
    if value:
        return value
    return str(record.get("text") or "").strip()


def _timeline_item(
    *,
    item_id: str,
    timestamp: object,
    kind: str,
    family: str,
    title: str,
    detail: str,
    authority: str,
    source_paths: list[str],
    session_id: str = "",
    turn_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "timestamp": _parse_timestamp(timestamp),
        "kind": kind,
        "family": family,
        "title": title,
        "detail": detail,
        "authority": authority,
        "session_id": session_id,
        "turn_ids": turn_ids or [],
        "source_paths": source_paths,
    }


def _snapshot_timeline(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for session in snapshot.get("sessions") or []:
        session_id = str(session.get("session_id") or "unknown-session")
        source_path = f"wiki/sources/session-{_slug(session_id)}.md"
        for index, turn in enumerate(session.get("turns") or [], start=1):
            speaker = str(turn.get("speaker") or "unknown")
            turn_id = str(turn.get("turn_id") or f"{session_id}:turn:{index}")
            items.append(
                _timeline_item(
                    item_id=f"turn-{len(items) + 1}",
                    timestamp=turn.get("timestamp") or session.get("timestamp") or snapshot.get("generated_at"),
                    kind="source_turn",
                    family="memory_kb_source",
                    title=f"{speaker.title()} turn",
                    detail=str(turn.get("text") or "").strip(),
                    authority="source_record",
                    source_paths=[source_path],
                    session_id=session_id,
                    turn_ids=[turn_id],
                )
            )
    for record in snapshot.get("observations") or []:
        observation_id = str((record.get("metadata") or {}).get("observation_id") or record.get("text") or "evidence")
        items.append(
            _timeline_item(
                item_id=f"evidence-{len(items) + 1}",
                timestamp=record.get("timestamp") or snapshot.get("generated_at"),
                kind="evidence",
                family="memory_kb_evidence",
                title=f"Evidence: {record.get('subject', 'unknown')}.{record.get('predicate', 'memory')}",
                detail=_record_value(record),
                authority="supporting_not_authoritative",
                source_paths=[f"wiki/evidence/{_slug(observation_id)}.md"],
                session_id=str(record.get("session_id") or ""),
                turn_ids=[str(turn_id) for turn_id in record.get("turn_ids") or []],
            )
        )
    for record in snapshot.get("current_state") or []:
        subject = str(record.get("subject") or "unknown")
        predicate = str(record.get("predicate") or "unknown")
        items.append(
            _timeline_item(
                item_id=f"state-{len(items) + 1}",
                timestamp=record.get("timestamp") or snapshot.get("generated_at"),
                kind="current_state",
                family="memory_kb_current_state",
                title=f"Current state: {subject}.{predicate}",
                detail=_record_value(record),
                authority="governed_runtime_memory",
                source_paths=[f"wiki/current-state/{_slug(subject)}-{_slug(predicate)}.md"],
                session_id=str(record.get("session_id") or ""),
                turn_ids=[str(turn_id) for turn_id in record.get("turn_ids") or []],
            )
        )
    for record in snapshot.get("events") or []:
        event_id = str((record.get("metadata") or {}).get("event_id") or record.get("text") or "event")
        items.append(
            _timeline_item(
                item_id=f"event-{len(items) + 1}",
                timestamp=record.get("timestamp") or snapshot.get("generated_at"),
                kind="event",
                family="memory_kb_event",
                title=f"Event: {record.get('subject', 'unknown')}.{record.get('predicate', 'event')}",
                detail=_record_value(record),
                authority="supporting_not_authoritative",
                source_paths=[f"wiki/events/{_slug(event_id)}.md"],
                session_id=str(record.get("session_id") or ""),
                turn_ids=[str(turn_id) for turn_id in record.get("turn_ids") or []],
            )
        )
    return sorted(items, key=lambda item: (item["timestamp"] or "", item["kind"], item["id"]))


def _page_timeline_fallback(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for page in pages:
        if page["type"] in {"index", "source"}:
            continue
        items.append(
            _timeline_item(
                item_id=f"page-{len(items) + 1}",
                timestamp="",
                kind=page["type"],
                family=page["wiki_family"],
                title=page["title"],
                detail=page["summary"] or page["excerpt"],
                authority=page["authority"],
                source_paths=[page["relative_path"]],
            )
        )
    return items


def _slug(value: object) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "item"


def _counter(values: list[str]) -> dict[str, int]:
    return dict(sorted(Counter(value or "unknown" for value in values).items()))


def _canvas_base(
    object_id: str,
    object_type: str,
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    z_index: int,
) -> dict[str, Any]:
    now = 0
    return {
        "id": object_id,
        "type": object_type,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "rotation": 0,
        "layerId": "layer-main",
        "locked": True,
        "visible": True,
        "opacity": 1,
        "zIndex": z_index,
        "createdAt": now,
        "updatedAt": now,
        "createdBy": "domain-chip-memory",
    }


def _canvas_shape(
    object_id: str,
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    label: str,
    stroke: str = "#2FCA94",
    fill: str = "#141820",
    shape_type: str = "rect",
    z_index: int = 10,
) -> dict[str, Any]:
    return {
        **_canvas_base(object_id, "shape", x=x, y=y, width=width, height=height, z_index=z_index),
        "shapeType": shape_type,
        "fill": fill,
        "stroke": stroke,
        "strokeWidth": 2,
        "content": label,
        "contentColor": "#F0F0F4",
    }


def _canvas_sticky(
    object_id: str,
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    content: str,
    color: str,
    z_index: int,
) -> dict[str, Any]:
    return {
        **_canvas_base(object_id, "sticky", x=x, y=y, width=width, height=height, z_index=z_index),
        "content": content,
        "color": color,
        "fontSize": 13,
    }


def _canvas_connector(
    object_id: str,
    points: list[dict[str, int]],
    *,
    label: str = "",
    stroke: str = "#2FCA94",
    dashed: bool = False,
    z_index: int = 5,
) -> dict[str, Any]:
    return {
        **_canvas_base(object_id, "connector", x=0, y=0, width=1, height=1, z_index=z_index),
        "points": points,
        "stroke": stroke,
        "strokeWidth": 2,
        "startArrow": False,
        "endArrow": True,
        "label": label,
        "lineStyle": "elbow",
        "dashed": dashed,
    }


def _assign_canvas_object_ids(timeline: list[dict[str, Any]]) -> None:
    for item in timeline:
        item["canvas_object_id"] = f"kb-timeline-{_slug(item.get('id'))}"


def _assign_source_links(timeline: list[dict[str, Any]], pages: list[dict[str, Any]]) -> None:
    pages_by_path = {str(page.get("relative_path") or ""): page for page in pages}
    for item in timeline:
        source_links = []
        for source_path in item.get("source_paths") or []:
            page = pages_by_path.get(str(source_path))
            source_links.append(
                {
                    "path": str(source_path),
                    "href": str((page or {}).get("href") or ""),
                    "title": str((page or {}).get("title") or source_path),
                }
            )
        item["source_links"] = source_links


def _build_spark_visionboard_board(model_seed: dict[str, Any]) -> dict[str, Any]:
    timeline = list(model_seed.get("timeline") or [])
    generated_at = model_seed.get("generated_at") or _utc_timestamp()
    objects: dict[str, dict[str, Any]] = {}

    def add(obj: dict[str, Any]) -> None:
        objects[str(obj["id"])] = obj

    add(
        {
            **_canvas_base("kb-frame-main", "frame", x=20, y=20, width=980, height=580, z_index=1),
            "label": "Spark Memory Wiki / Visionboard Projection",
            "backgroundColor": "rgba(24,28,38,0.72)",
        }
    )
    add(_canvas_shape("kb-builder", x=70, y=90, width=170, height=82, label="Builder\nbridge calls", stroke="#2FCA94", z_index=10))
    add(_canvas_shape("kb-memory", x=70, y=360, width=170, height=82, label="Domain Chip\nmemory lanes", stroke="#6E5CA0", z_index=10))
    add(_canvas_shape("kb-vault", x=370, y=210, width=210, height=128, label="Compiled LLM\nWiki Vault\nraw + markdown", stroke="#2FCA94", fill="#0E1018", z_index=12))
    add(_canvas_shape("kb-artifact", x=760, y=135, width=160, height=86, label="HTML Artifact\noperator view", stroke="#D8C868", z_index=10))
    add(_canvas_shape("kb-trace", x=760, y=315, width=160, height=86, label="Trace Payloads\nBuilder ready", stroke="#B8A8DC", z_index=10))
    add(_canvas_connector("kb-edge-builder-vault", [{"x": 240, "y": 130}, {"x": 370, "y": 260}], label="export", z_index=4))
    add(_canvas_connector("kb-edge-memory-vault", [{"x": 240, "y": 400}, {"x": 370, "y": 292}], label="compile", stroke="#B8A8DC", z_index=4))
    add(_canvas_connector("kb-edge-vault-artifact", [{"x": 580, "y": 245}, {"x": 760, "y": 178}], label="render", stroke="#D8C868", z_index=4))
    add(_canvas_connector("kb-edge-vault-trace", [{"x": 580, "y": 300}, {"x": 760, "y": 358}], label="actions", stroke="#B8A8DC", z_index=4))

    colors = {
        "current_state": "green",
        "evidence": "blue",
        "event": "purple",
        "source_turn": "yellow",
    }
    for index, item in enumerate(timeline[:8]):
        object_id = str(item.get("canvas_object_id") or f"kb-timeline-{index + 1}")
        x = 90 + (index % 4) * 220
        y = 660 + (index // 4) * 125
        content = f"{item.get('kind', 'item')}\n{item.get('title', 'Untitled')}"
        add(
            _canvas_sticky(
                object_id,
                x=x,
                y=y,
                width=180,
                height=86,
                content=content,
                color=colors.get(str(item.get("kind")), "orange"),
                z_index=30 + index,
            )
        )
        add(
            _canvas_connector(
                f"kb-edge-vault-{object_id}",
                [{"x": 475, "y": 338}, {"x": x + 90, "y": y}],
                label=str(item.get("kind") or ""),
                stroke="#506070",
                dashed=True,
                z_index=3,
            )
        )

    return {
        "schema": "spark-visionboard-board.v1",
        "source": "domain-chip-memory.spark_kb_html",
        "generated_at": generated_at,
        "board": {
            "id": f"spark-memory-wiki-{_slug(generated_at)[:24]}",
            "name": "Spark Memory Wiki Visionboard Projection",
            "objects": objects,
            "layers": [{"id": "layer-main", "name": "Memory Wiki", "visible": True, "locked": False, "order": 0}],
            "viewport": {"x": 40, "y": 40, "zoom": 0.75},
            "selectedIds": [],
            "activeLayerId": "layer-main",
            "createdAt": 0,
            "updatedAt": 0,
        },
        "diagram_packets": [
            {
                "id": "wiki-memory-flow",
                "type": "spark_visionboard_projection",
                "title": "Spark Memory Wiki Flow",
                "object_ids": ["kb-builder", "kb-memory", "kb-vault", "kb-artifact", "kb-trace"],
            },
            {
                "id": "wiki-timeline-items",
                "type": "spark_visionboard_timeline_projection",
                "title": "Timeline Items",
                "object_ids": [str(item.get("canvas_object_id")) for item in timeline[:8]],
            },
        ],
        "visionboard_api": {
            "default_base_url": "http://localhost:3000/api/visionboard",
            "create_board": "POST /boards",
            "add_objects": "POST /boards/{board_id}/objects",
            "generate": "POST /generate",
        },
    }


def _canvas_board_summary(canvas_board: dict[str, Any]) -> dict[str, Any]:
    board = canvas_board.get("board") or {}
    objects = board.get("objects") or {}
    return {
        "schema": canvas_board.get("schema"),
        "board_name": board.get("name"),
        "object_count": len(objects),
        "object_type_counts": _counter([str((obj or {}).get("type") or "unknown") for obj in objects.values()]),
        "diagram_packet_count": len(canvas_board.get("diagram_packets") or []),
    }


def _build_model(kb_dir: Path, html_file: Path) -> dict[str, Any]:
    snapshot, snapshot_file = _load_snapshot(kb_dir)
    pages = _read_pages(kb_dir, html_file)
    timeline = _snapshot_timeline(snapshot) if snapshot else _page_timeline_fallback(pages)
    _assign_canvas_object_ids(timeline)
    _assign_source_links(timeline, pages)
    generated_at = _utc_timestamp()
    family_counts = _counter([page["wiki_family"] for page in pages])
    kind_counts = _counter([item["kind"] for item in timeline])
    page_type_counts = _counter([page["type"] for page in pages])
    authority_counts = _counter([page["authority"] for page in pages])
    owner_system_counts = _counter([page["owner_system"] for page in pages])
    model_seed = {
        "generated_at": generated_at,
        "timeline": timeline,
    }
    canvas_board = _build_spark_visionboard_board(model_seed)
    canvas_summary = _canvas_board_summary(canvas_board)
    recursive_runs = _discover_recursive_run_links(html_file)
    trace = {
        "operation": "render_spark_kb_html_artifact",
        "generated_at": generated_at,
        "input_dir": str(kb_dir),
        "source_snapshot_file": str(snapshot_file) if snapshot_file else None,
        "markdown_page_count": len(pages),
        "timeline_item_count": len(timeline),
        "family_counts": family_counts,
        "authority_counts": authority_counts,
        "owner_system_counts": owner_system_counts,
        "visionboard_board": canvas_summary,
        "recursive_run_links": recursive_runs,
        "non_override_rules": [
            "HTML artifacts visualize and route context; they do not become runtime truth.",
            "Current-state APIs outrank wiki summaries for mutable user facts.",
            "Every action payload must preserve source_paths, authority, owner_system, and wiki_family.",
            "Generated diagrams are interpretations unless backed by source paths in the trace.",
        ],
    }
    return {
        "title": "Spark LLM Wiki",
        "subtitle": "Source-backed memory, agent knowledge, and recursive learning history.",
        "generated_at": generated_at,
        "snapshot_counts": snapshot.get("counts") or {},
        "family_counts": family_counts,
        "kind_counts": kind_counts,
        "page_type_counts": page_type_counts,
        "authority_counts": authority_counts,
        "owner_system_counts": owner_system_counts,
        "pages": pages,
        "timeline": timeline,
        "recursive_runs": recursive_runs,
        "canvas_board": canvas_board,
        "canvas_board_summary": canvas_summary,
        "trace": trace,
    }


def _discover_recursive_run_links(html_file: Path) -> list[dict[str, str]]:
    candidates: list[Path] = []
    for env_name in ("SPARK_RECURSIVE_WIKI_ROOT", "SPARK_LLM_WIKI_ROOT"):
        raw = os.environ.get(env_name)
        if raw:
            candidates.append(Path(raw))
    candidates.extend(
        [
            Path.home() / ".spark-intelligence" / "wiki",
            Path.home() / ".spark" / "state" / "spark-intelligence" / "wiki",
        ]
    )
    links: list[dict[str, str]] = []
    seen: set[Path] = set()
    for root in candidates:
        recursive_root = root / "recursive-runs"
        index_file = recursive_root / "index.html"
        if not index_file.exists() or index_file in seen:
            continue
        seen.add(index_file)
        links.append(
            {
                "label": "Recursive Runs",
                "href": _safe_html_rel(index_file, html_file),
            }
        )
    return links


def build_spark_kb_html_artifact_contract_summary() -> dict[str, Any]:
    return {
        "contract_name": "SparkKbHtmlArtifact",
        "input": "Compiled Spark KB vault with raw/memory-snapshots/latest.json and wiki/**/*.md.",
        "outputs": [
            "artifacts/spark-kb-dashboard.html",
            "artifacts/spark-kb-dashboard.trace.json",
            "artifacts/spark-kb-visionboard-board.json",
        ],
        "runtime_role": "human-readable visual dashboard over LLM wiki packets",
        "authority": "visualization_only",
        "owner_system": "domain-chip-memory",
        "builder_bridge": {
            "action_payloads": [
                "ask_agent",
                "find_support",
                "generate_diagram",
            ],
            "required_fields": [
                "source_paths",
                "authority",
                "owner_system",
                "wiki_family",
                "timeline_item_id",
                "canvas_object_id",
            ],
        },
        "cli": {
            "render_existing_vault": "domain-chip-memory render-spark-kb-html-artifact <kb_dir>",
            "compile_any_supported_input_and_render": "domain-chip-memory build-spark-wiki-dashboard <input.json> <kb_dir> --source builder-export",
            "compile_snapshot_and_render": "domain-chip-memory build-spark-kb <snapshot.json> <kb_dir> --html-artifact",
            "compile_builder_export_and_render": "domain-chip-memory build-spark-kb-from-builder-export <export.json> <kb_dir> --html-artifact",
        },
        "spark_visionboard": {
            "display_name": "Spark Visionboard",
            "schema": "spark-visionboard-board.v1",
            "default_api_base_url": "http://localhost:3000/api/visionboard",
            "diagram_source": "Spark Visionboard board objects, frames, stickies, and connectors.",
        },
        "non_override_rules": [
            "The artifact can prepare actions but must not mutate memory directly.",
            "Source-aware current-state and evidence retrieval remain authoritative.",
            "Wiki packets are supporting context unless promoted through governed memory lanes.",
        ],
    }


def render_spark_kb_html_artifact(
    kb_dir: str | Path,
    *,
    output_file: str | Path | None = None,
    trace_file: str | Path | None = None,
    canvas_board_file: str | Path | None = None,
) -> dict[str, Any]:
    kb_path = Path(kb_dir)
    artifact_file = Path(output_file) if output_file else kb_path / "artifacts" / "spark-kb-dashboard.html"
    artifact_trace_file = Path(trace_file) if trace_file else artifact_file.with_suffix(".trace.json")
    artifact_canvas_file = Path(canvas_board_file) if canvas_board_file else artifact_file.parent / "spark-kb-visionboard-board.json"
    model = _build_model(kb_path, artifact_file)
    model["artifact_outputs"] = {
        "html_href": _safe_html_rel(artifact_file, artifact_file),
        "trace_href": _safe_html_rel(artifact_trace_file, artifact_file),
        "visionboard_board_href": _safe_html_rel(artifact_canvas_file, artifact_file),
    }
    model["trace"]["artifact_outputs"] = model["artifact_outputs"]
    artifact_file.parent.mkdir(parents=True, exist_ok=True)
    artifact_trace_file.parent.mkdir(parents=True, exist_ok=True)
    artifact_canvas_file.parent.mkdir(parents=True, exist_ok=True)
    artifact_file.write_text(_render_html(model), encoding="utf-8")
    artifact_trace_file.write_text(json.dumps(model["trace"], indent=2) + "\n", encoding="utf-8")
    artifact_canvas_file.write_text(json.dumps(model["canvas_board"], indent=2) + "\n", encoding="utf-8")
    return {
        "contract_name": "SparkKbHtmlArtifact",
        "artifact_file": str(artifact_file),
        "trace_file": str(artifact_trace_file),
        "visionboard_board_file": str(artifact_canvas_file),
        "input_dir": str(kb_path),
        "source_snapshot_file": model["trace"]["source_snapshot_file"],
        "markdown_page_count": model["trace"]["markdown_page_count"],
        "timeline_item_count": model["trace"]["timeline_item_count"],
        "family_counts": model["family_counts"],
        "kind_counts": model["kind_counts"],
        "authority_counts": model["authority_counts"],
        "owner_system_counts": model["owner_system_counts"],
        "visionboard_board": model["canvas_board_summary"],
        "trace": model["trace"],
    }


def _render_html(model: dict[str, Any]) -> str:
    data_json = json.dumps(model, ensure_ascii=False).replace("</", "<\\/")
    timeline_markup = "\n".join(_render_timeline_item(item) for item in model["timeline"])
    page_rows = "\n".join(_render_page_row(page) for page in model["pages"])
    spark_logo = _spark_logo_markup()
    family_chips = "\n".join(
        f'<button class="filter-chip" data-family="{escape(family)}"><span class="filter-label">{escape(_family_label(family))}</span><span class="filter-count">{count}</span></button>'
        for family, count in model["family_counts"].items()
    )
    recursive_links = "\n".join(
        f'<a class="connection-card" href="{escape(link["href"])}"><span>{escape(link["label"])}</span><strong>Open</strong></a>'
        for link in model.get("recursive_runs", [])
    )
    recursive_links = recursive_links or '<div class="connection-card is-muted"><span>Recursive Runs</span><strong>Not linked yet</strong></div>'
    stat_cards = "\n".join(
        [
            _render_stat("Timeline", str(len(model["timeline"])), "events, state movement, source turns"),
            _render_stat("Wiki Packets", str(len(model["pages"])), "markdown pages compiled into the artifact"),
            _render_stat("Families", str(len(model["family_counts"])), "typed memory/wiki lanes"),
            _render_stat("Owners", str(len(model["owner_system_counts"])), "source systems preserved in trace"),
        ]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(model["title"])}</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap');
    :root {{
      --spark-bg: #0E1018;
      --spark-bg-subtle: #141820;
      --spark-surface: #181C26;
      --spark-raised: #1E2230;
      --spark-line: #222430;
      --spark-line-strong: #2A2E40;
      --spark-accent: #2FCA94;
      --spark-accent-hover: #22B884;
      --spark-accent-subtle: rgba(47, 202, 148, 0.10);
      --spark-accent-mid: rgba(47, 202, 148, 0.15);
      --spark-iris: #B8A8DC;
      --spark-iris-dim: #6E5CA0;
      --spark-gold: #D8C868;
      --spark-logo: #1DDFA2;
      --spark-text: #F0F0F4;
      --spark-bright: #E0E2EC;
      --spark-muted: #8890B0;
      --spark-tertiary: #6A7080;
      --spark-ghost: #506070;
      color-scheme: dark;
    }}
    [data-theme="light"] {{
      --spark-bg: #F5F5F3;
      --spark-bg-subtle: #EDEDEB;
      --spark-surface: #FFFFFF;
      --spark-raised: #FFFFFF;
      --spark-line: #E2E2E0;
      --spark-line-strong: #D0D0CE;
      --spark-accent: #0A6F4E;
      --spark-accent-hover: #075B41;
      --spark-accent-subtle: rgba(47, 202, 148, 0.10);
      --spark-accent-mid: rgba(47, 202, 148, 0.16);
      --spark-iris: #6E5CA0;
      --spark-iris-dim: #6E5CA0;
      --spark-gold: #8A7330;
      --spark-logo: #0A6F4E;
      --spark-text: #1A1A18;
      --spark-bright: #1A1A18;
      --spark-muted: #4A4A47;
      --spark-tertiary: #6E6E69;
      --spark-ghost: #A0A09C;
      color-scheme: light;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle 1px, rgba(47, 202, 148, 0.035) 1px, transparent 1px),
        var(--spark-bg);
      background-size: 24px 24px, 100% 100%;
      background-attachment: fixed;
      color: var(--spark-text);
      font-family: "DM Sans", Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 14px;
      line-height: 1.55;
      letter-spacing: 0.01em;
    }}
    [data-theme="light"] body {{ background: var(--spark-bg); }}
    a {{ color: inherit; }}
    button, input {{ font: inherit; }}
    .artifact-shell {{
      display: grid;
      grid-template-columns: 244px 1fr;
      min-height: 100vh;
      gap: 0;
    }}
    .side-nav {{
      position: sticky;
      top: 0;
      height: 100vh;
      padding: 0.75rem;
      border-right: 1px solid var(--spark-line);
      background: var(--spark-bg);
      backdrop-filter: blur(16px);
      overflow: auto;
    }}
    .nav-inner {{
      min-height: calc(100vh - 1.5rem);
      border: 1px solid var(--spark-line-strong);
      border-radius: 8px;
      background: var(--spark-surface);
      padding: 0.75rem;
    }}
    .brand-kicker, .mono-label, .metric-label, .timeline-kind, .filter-chip, .nav-link, .action-button, .theme-toggle {{
      font-family: "DM Mono", "SFMono-Regular", Consolas, monospace;
      text-transform: uppercase;
      letter-spacing: 0.14em;
    }}
    .brand-lockup {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
      min-width: 0;
      padding: 0.45rem 0.35rem 0.65rem;
    }}
    .spark-mark {{ width: 32px; height: auto; color: var(--spark-logo); flex: 0 0 auto; }}
    .spark-wordmark {{ width: 78px; height: auto; color: var(--spark-text); flex: 0 0 auto; }}
    .spark-divider {{ width: 1px; height: 20px; background: var(--spark-line-strong); flex: 0 0 auto; }}
    .spark-product {{
      color: var(--spark-muted);
      font-family: "DM Sans", Inter, ui-sans-serif, system-ui, sans-serif;
      font-size: 0.8rem;
      font-weight: 600;
      letter-spacing: 0.02em;
      text-transform: none;
      white-space: nowrap;
    }}
    .spark-product span {{ color: var(--spark-logo); }}
    .hero-lockup {{ display: none; margin-bottom: 1.2rem; }}
    .hero-lockup .brand-lockup {{ padding: 0; }}
    .brand-kicker {{ color: var(--spark-accent); font-size: 0.68rem; margin-top: 0.5rem; }}
    .brand-title {{
      margin: 0.35rem 0 0.35rem;
      font-size: 1.35rem;
      line-height: 1.05;
      font-weight: 650;
    }}
    .brand-copy {{ margin: 0; color: var(--spark-muted); line-height: 1.5; }}
    .theme-toggle {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      width: 100%;
      border: 1px solid var(--spark-line);
      border-radius: 6px;
      background: var(--spark-bg-subtle);
      color: var(--spark-muted);
      padding: 0.68rem 0.75rem;
      cursor: pointer;
      font-size: 0.72rem;
    }}
    .theme-toggle:hover {{ border-color: var(--spark-accent); background: var(--spark-accent-subtle); color: var(--spark-text); }}
    .nav-group {{ margin-top: 1.5rem; display: grid; gap: 0.5rem; }}
    .nav-link, .filter-chip {{
      width: 100%;
      border: 1px solid var(--spark-line);
      background: var(--spark-bg-subtle);
      color: var(--spark-text);
      border-radius: 6px;
      padding: 0.68rem 0.75rem;
      text-align: left;
      cursor: pointer;
      text-decoration: none;
      transition: border-color 200ms ease, background 200ms ease, color 200ms ease;
    }}
    .nav-link:hover, .filter-chip:hover, .action-button:hover {{
      border-color: var(--spark-accent);
      background: var(--spark-accent-subtle);
    }}
    .filter-chip {{
      display: flex;
      justify-content: space-between;
      gap: 0.75rem;
      font-size: 0.76rem;
      min-width: 0;
    }}
    .filter-label {{ min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .filter-count {{ flex: 0 0 auto; color: inherit; }}
    .filter-chip.is-active {{
      border-color: var(--spark-accent);
      color: var(--spark-accent);
      background: var(--spark-accent-subtle);
    }}
    [data-theme="light"] .side-nav {{ background: var(--spark-bg); }}
    [data-theme="light"] .nav-inner,
    [data-theme="light"] .nav-link,
    [data-theme="light"] .filter-chip,
    [data-theme="light"] .theme-toggle {{
      background: var(--spark-surface);
      color: var(--spark-text);
    }}
    [data-theme="light"] .theme-toggle {{ color: var(--spark-muted); }}
    [data-theme="light"] .filter-chip.is-active {{
      color: var(--spark-accent);
      background: var(--spark-accent-subtle);
    }}
    .connection-grid {{
      display: grid;
      gap: 0.5rem;
      padding: 1rem;
    }}
    .connection-card {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      border: 1px solid var(--spark-line);
      border-radius: 6px;
      background: var(--spark-bg-subtle);
      color: var(--spark-text);
      padding: 0.75rem 0.85rem;
      text-decoration: none;
    }}
    .connection-card strong {{
      color: var(--spark-accent);
      font-family: "DM Mono", "SFMono-Regular", Consolas, monospace;
      font-size: 0.72rem;
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      white-space: nowrap;
    }}
    .connection-card.is-muted strong {{ color: var(--spark-muted); }}
    .prompt-list {{
      display: grid;
      gap: 0.5rem;
      padding: 0 1rem 1rem;
    }}
    .prompt-chip {{
      border: 1px solid var(--spark-line);
      border-radius: 5px;
      background: var(--spark-bg-subtle);
      color: var(--spark-muted);
      padding: 0.55rem 0.65rem;
      font-family: "DM Mono", "SFMono-Regular", Consolas, monospace;
      font-size: 0.72rem;
      overflow-wrap: anywhere;
    }}
    .main {{
      padding: clamp(1rem, 3vw, 2.5rem);
      overflow: hidden;
    }}
    .topbar {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(14rem, 22rem);
      gap: 1rem;
      align-items: start;
      margin-bottom: 1rem;
    }}
    .hero {{
      border-bottom: 1px solid var(--spark-line);
      padding: 1rem 0 1.35rem;
      background: transparent;
    }}
    .hero h1 {{
      margin: 0;
      max-width: 34rem;
      font-size: clamp(1.75rem, 4vw, 2.45rem);
      line-height: 1.08;
      font-weight: 650;
      letter-spacing: -0.02em;
    }}
    .hero p {{ max-width: 42rem; color: var(--spark-muted); line-height: 1.7; }}
    .search-panel {{
      border: 1px solid var(--spark-line);
      border-radius: 6px;
      padding: 1rem;
      background: var(--spark-surface);
    }}
    .search-input {{
      width: 100%;
      border: 1px solid var(--spark-line);
      border-radius: 5px;
      background: var(--spark-bg-subtle);
      color: var(--spark-text);
      padding: 0.75rem 0.85rem;
      outline: none;
    }}
    .search-input:focus {{ border-color: var(--spark-accent); box-shadow: 0 0 0 3px var(--spark-accent-subtle); }}
    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      border: 1px solid var(--spark-line);
      border-radius: 6px;
      background: var(--spark-surface);
      margin: 1rem 0;
      overflow: hidden;
    }}
    .stat-card {{
      min-height: 6rem;
      border-right: 1px solid var(--spark-line);
      background: transparent;
      padding: 0.9rem;
    }}
    .stat-card:last-child {{ border-right: 0; }}
    .metric-label {{ color: var(--spark-muted); font-size: 0.72rem; }}
    .metric-value {{ margin-top: 0.45rem; font-size: 1.72rem; color: var(--spark-bright); font-weight: 650; font-variant-numeric: tabular-nums; }}
    .metric-help {{ margin-top: 0.25rem; color: var(--spark-muted); font-size: 0.88rem; line-height: 1.35; }}
    .workspace {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(18rem, 24rem);
      gap: 1rem;
      align-items: start;
    }}
    .section-band {{
      border: 1px solid var(--spark-line);
      border-radius: 6px;
      background: var(--spark-surface);
      overflow: hidden;
    }}
    .section-header {{
      display: flex;
      justify-content: space-between;
      gap: 1rem;
      align-items: center;
      padding: 1rem 1rem 0.75rem;
      border-bottom: 1px solid var(--spark-line);
    }}
    .section-header h2 {{ margin: 0; font-size: 1rem; }}
    .timeline-shell {{ position: relative; padding: 1rem; }}
    .timeline-spine {{
      position: absolute;
      left: 1.48rem;
      top: 1rem;
      bottom: 1rem;
      width: 1px;
      background: linear-gradient(var(--spark-accent), var(--spark-iris));
      opacity: 0.65;
    }}
    .timeline-item {{
      position: relative;
      margin-left: 2rem;
      padding: 1rem 1rem 1rem 1.15rem;
      border-bottom: 1px solid var(--spark-line);
      border-radius: 6px;
      cursor: pointer;
      transition: background 180ms ease, border-color 180ms ease;
    }}
    .timeline-item:focus-visible {{ outline: 2px solid var(--spark-accent); outline-offset: 3px; }}
    .timeline-item.is-selected {{ background: var(--spark-accent-subtle); }}
    .timeline-item:last-child {{ border-bottom: 0; }}
    .timeline-item::before {{
      content: "";
      position: absolute;
      left: -1rem;
      top: 1.3rem;
      width: 0.62rem;
      height: 0.62rem;
      border-radius: 999px;
      background: var(--spark-accent);
      box-shadow: 0 0 0 5px rgba(56, 242, 194, 0.1);
    }}
    .timeline-kind {{
      display: inline-flex;
      gap: 0.4rem;
      align-items: center;
      color: var(--spark-accent);
      font-size: 0.72rem;
    }}
    .timeline-title {{ margin: 0.35rem 0; font-size: 1.2rem; }}
    .timeline-detail {{ color: var(--spark-muted); line-height: 1.5; margin: 0; }}
    .timeline-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.45rem;
      margin-top: 0.8rem;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      max-width: 100%;
      border: 1px solid var(--spark-line);
      border-radius: 999px;
      color: var(--spark-muted);
      padding: 0.3rem 0.5rem;
      font-size: 0.72rem;
      overflow-wrap: normal;
    }}
    .timeline-meta .pill {{ overflow-wrap: anywhere; }}
    .action-row {{ display: flex; flex-wrap: wrap; gap: 0.45rem; margin-top: 0.9rem; }}
    .action-button {{
      border: 1px solid var(--spark-line);
      border-radius: 5px;
      background: var(--spark-bg-subtle);
      color: var(--spark-text);
      padding: 0.48rem 0.62rem;
      cursor: pointer;
      font-size: 0.72rem;
    }}
    .inspector {{
      display: grid;
      gap: 1rem;
      position: sticky;
      top: 1rem;
    }}
    .diagram svg {{ width: 100%; height: auto; display: block; }}
    .canvas-preview-wrap {{ overflow: hidden; background: var(--spark-bg-subtle); }}
    .canvas-object {{ transition: opacity 180ms ease, stroke 180ms ease, filter 180ms ease; }}
    .canvas-object.is-selected {{ filter: drop-shadow(0 0 8px rgba(47, 202, 148, 0.55)); }}
    .canvas-object.is-dimmed {{ opacity: 0.34; }}
    .bridge-status {{
      border-bottom: 1px solid var(--spark-line);
      padding: 0.7rem 1rem;
      color: var(--spark-muted);
      font-size: 0.78rem;
      line-height: 1.45;
    }}
    .bridge-status code {{
      color: var(--spark-bright);
      font-family: "DM Mono", "SFMono-Regular", Consolas, monospace;
      font-size: 0.75rem;
    }}
    .bridge-status.is-live {{ color: var(--spark-accent); }}
    .bridge-status.is-error {{ color: var(--spark-gold); }}
    .bridge-controls {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 0.55rem;
      padding: 0.75rem 1rem;
      border-bottom: 1px solid var(--spark-line);
      background: rgba(14, 16, 24, 0.42);
    }}
    .bridge-field {{
      display: grid;
      gap: 0.35rem;
    }}
    .bridge-field label {{
      color: var(--spark-muted);
      font-family: "DM Mono", "SFMono-Regular", Consolas, monospace;
      font-size: 0.68rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}
    .bridge-input {{
      width: 100%;
      min-width: 0;
      border: 1px solid var(--spark-line);
      border-radius: 5px;
      background: var(--spark-bg-subtle);
      color: var(--spark-text);
      padding: 0.55rem 0.65rem;
      font-family: "DM Mono", "SFMono-Regular", Consolas, monospace;
      font-size: 0.72rem;
      outline: none;
    }}
    .bridge-input:focus {{ border-color: var(--spark-accent); box-shadow: 0 0 0 3px var(--spark-accent-subtle); }}
    .bridge-save {{
      justify-self: start;
      border: 1px solid var(--spark-line);
      border-radius: 5px;
      background: var(--spark-bg-subtle);
      color: var(--spark-text);
      padding: 0.48rem 0.62rem;
      cursor: pointer;
      font-family: "DM Mono", "SFMono-Regular", Consolas, monospace;
      font-size: 0.72rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}
    .bridge-save:hover {{ border-color: var(--spark-accent); background: var(--spark-accent-subtle); }}
    .bridge-save.is-wide {{ justify-self: stretch; }}
    .selected-inspector {{
      display: grid;
      gap: 0.75rem;
      padding: 1rem;
    }}
    .selected-title {{
      margin: 0;
      color: var(--spark-bright);
      font-size: 1rem;
      line-height: 1.25;
    }}
    .selected-detail {{
      margin: 0;
      color: var(--spark-muted);
      line-height: 1.5;
    }}
    .selected-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 0.5rem;
    }}
    .selected-cell {{
      min-width: 0;
      border: 1px solid var(--spark-line);
      border-radius: 5px;
      padding: 0.55rem;
      background: var(--spark-bg-subtle);
    }}
    .selected-cell .metric-label {{ font-size: 0.64rem; }}
    .selected-cell div:last-child {{
      margin-top: 0.25rem;
      overflow-wrap: anywhere;
      color: var(--spark-text);
      font-family: "DM Mono", "SFMono-Regular", Consolas, monospace;
      font-size: 0.72rem;
    }}
    .manifest-list {{
      display: grid;
      gap: 0.5rem;
      padding: 1rem;
    }}
    .manifest-link {{
      display: flex;
      justify-content: space-between;
      gap: 0.75rem;
      border: 1px solid var(--spark-line);
      border-radius: 5px;
      padding: 0.6rem;
      background: var(--spark-bg-subtle);
      color: var(--spark-text);
      text-decoration: none;
      font-family: "DM Mono", "SFMono-Regular", Consolas, monospace;
      font-size: 0.72rem;
    }}
    .manifest-link:hover {{ border-color: var(--spark-accent); background: var(--spark-accent-subtle); }}
    .manifest-link span:last-child {{ color: var(--spark-muted); }}
    .trace-pre {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      color: var(--spark-muted);
      margin: 0;
      font-size: 0.78rem;
      line-height: 1.45;
      font-family: "DM Mono", "SFMono-Regular", Consolas, monospace;
    }}
    .pages-table {{ width: 100%; border-collapse: collapse; }}
    .pages-table th, .pages-table td {{
      padding: 0.85rem 1rem;
      border-bottom: 1px solid var(--spark-line);
      text-align: left;
      vertical-align: top;
    }}
    .pages-table th {{ color: var(--spark-muted); font-size: 0.74rem; }}
    .pages-table td {{ color: var(--spark-text); }}
    .page-summary {{ color: var(--spark-muted); margin-top: 0.25rem; line-height: 1.4; }}
    .empty-state {{ padding: 2rem; color: var(--spark-muted); }}
    .is-hidden {{ display: none; }}
    @media (max-width: 1100px) {{
      .artifact-shell, .topbar, .workspace {{ grid-template-columns: 1fr; }}
      .artifact-shell {{ display: flex; flex-direction: column; }}
      .main {{ order: 1; }}
      .side-nav {{ order: 2; }}
      .side-nav {{ position: relative; height: auto; }}
      .nav-inner {{ min-height: 0; }}
      .hero-lockup {{ display: flex; }}
      .stats-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .stat-card:nth-child(2) {{ border-right: 0; }}
      .inspector {{ position: relative; top: 0; }}
    }}
    @media (max-width: 640px) {{
      .main {{ padding: 0.75rem; }}
      .hero h1 {{ font-size: 1.75rem; }}
      .stats-grid {{ grid-template-columns: 1fr; }}
      .stat-card {{ border-right: 0; border-bottom: 1px solid var(--spark-line); }}
      .stat-card:last-child {{ border-bottom: 0; }}
      .pages-table, .pages-table tbody, .pages-table tr, .pages-table td {{ display: block; width: 100%; }}
      .pages-table thead {{ display: none; }}
      .pages-table td {{ padding: 0.75rem; }}
    }}
  </style>
</head>
<body>
  <script id="spark-kb-data" type="application/json">{data_json}</script>
  <div class="artifact-shell">
    <aside class="side-nav" aria-label="Spark LLM wiki navigation">
      <div class="nav-inner">
        {spark_logo}
        <div class="brand-kicker">Spark Artifact</div>
        <div class="brand-title">LLM Wiki</div>
        <p class="brand-copy">Governed memory, agent brain context, recursive learning notes, and Builder-ready trace payloads.</p>
        <div class="nav-group" aria-label="Sections">
          <a class="nav-link" href="#overview">Overview</a>
          <a class="nav-link" href="#timeline">Timeline</a>
          <a class="nav-link" href="#flow">Spark Flow</a>
          <a class="nav-link" href="#connections">Agent Brain</a>
          <a class="nav-link" href="#packets">Wiki Packets</a>
          <a class="nav-link" href="#trace">Trace</a>
        </div>
        <div class="nav-group" aria-label="Theme">
          <button class="theme-toggle" id="theme-toggle" type="button"><span>Theme</span><strong id="theme-label">Dark</strong></button>
        </div>
        <div class="nav-group" aria-label="Family filters">
          <div class="mono-label">Filter By Family</div>
          <button class="filter-chip is-active" data-family="all"><span class="filter-label">All</span><span class="filter-count">{len(model["pages"])}</span></button>
          {family_chips}
        </div>
      </div>
    </aside>
    <main class="main">
      <section class="topbar" id="overview">
        <div class="hero">
          <div class="hero-lockup">{spark_logo}</div>
          <div class="brand-kicker">// Compiled From Spark KB</div>
          <h1>{escape(model["title"])}</h1>
          <p>{escape(model["subtitle"])}</p>
        </div>
        <div class="search-panel">
          <label class="mono-label" for="search">Search timeline and packets</label>
          <input class="search-input" id="search" type="search" placeholder="Try current_state, evidence, Builder, session...">
        </div>
      </section>
      <section class="stats-grid" aria-label="Artifact metrics">{stat_cards}</section>
      <section class="section-band" id="connections" style="margin-bottom: 1rem;">
        <div class="section-header">
          <h2>Spark Agent Brain</h2>
          <span class="pill">local/private</span>
        </div>
        <div class="connection-grid">
          <a class="connection-card" href="#packets"><span>LLM Wiki packets</span><strong>{len(model["pages"])} pages</strong></a>
          <a class="connection-card" href="#trace"><span>Builder action payloads</span><strong>Ready</strong></a>
          {recursive_links}
        </div>
        <div class="prompt-list" aria-label="Telegram natural-language prompts">
          <div class="mono-label">Telegram prompts</div>
          <div class="prompt-chip">/wiki</div>
          <div class="prompt-chip">answer from your LLM wiki how should recursive loops work?</div>
          <div class="prompt-chip">search your wiki for Spark QA Operator lessons</div>
        </div>
      </section>
      <section class="workspace">
        <div class="section-band" id="timeline">
          <div class="section-header">
            <h2>Memory Movement Timeline</h2>
            <span class="pill" id="result-count">{len(model["timeline"])} visible</span>
          </div>
          <div class="timeline-shell">
            <div class="timeline-spine" aria-hidden="true"></div>
            <div id="timeline-list">{timeline_markup or '<div class="empty-state">No timeline items found.</div>'}</div>
          </div>
        </div>
        <aside class="inspector">
          <div class="section-band diagram" id="flow">
            <div class="section-header">
              <h2>Spark Memory Flow</h2>
              <a class="pill" href="{escape(model["artifact_outputs"]["visionboard_board_href"])}">Visionboard JSON</a>
            </div>
            {_render_canvas_board(model["canvas_board"])}
          </div>
          <div class="section-band" id="selected">
            <div class="section-header"><h2>Selected Memory</h2><span class="pill">provenance</span></div>
            <div class="selected-inspector" id="selected-inspector">
              <p class="selected-detail">Select a timeline item to inspect its source paths, authority lane, and Visionboard object.</p>
            </div>
          </div>
          <div class="section-band" id="manifest">
            <div class="section-header"><h2>Artifact Manifest</h2><span class="pill">outputs</span></div>
            <div class="manifest-list">
              <a class="manifest-link" href="{escape(model["artifact_outputs"]["html_href"])}"><span>Dashboard</span><span>html</span></a>
              <a class="manifest-link" href="{escape(model["artifact_outputs"]["trace_href"])}"><span>Trace</span><span>json</span></a>
              <a class="manifest-link" href="{escape(model["artifact_outputs"]["visionboard_board_href"])}"><span>Spark Visionboard</span><span>json</span></a>
              <button class="bridge-save is-wide" id="create-visionboard-board" type="button">Create Visionboard</button>
            </div>
          </div>
          <div class="section-band" id="trace">
            <div class="section-header"><h2>Action Payload</h2><span class="pill">Builder-ready</span></div>
            <div class="bridge-status" id="bridge-status">Local preview. Add <code>?bridge=http://...</code> or <code>?visionboard=http://localhost:3000/api/visionboard</code> to send actions.</div>
            <div class="bridge-controls" aria-label="Bridge endpoints">
              <div class="bridge-field">
                <label for="builder-bridge-input">Builder Bridge</label>
                <input class="bridge-input" id="builder-bridge-input" type="url" placeholder="http://localhost:8787/artifact-action">
              </div>
              <div class="bridge-field">
                <label for="visionboard-bridge-input">Spark Visionboard API</label>
                <input class="bridge-input" id="visionboard-bridge-input" type="url" placeholder="http://localhost:3000/api/visionboard">
              </div>
              <button class="bridge-save" id="save-bridge-settings" type="button">Save Bridges</button>
            </div>
            <pre class="trace-pre" id="action-payload">{escape(json.dumps(model["trace"], indent=2))}</pre>
          </div>
        </aside>
      </section>
      <section class="section-band" id="packets" style="margin-top: 1rem;">
        <div class="section-header">
          <h2>Wiki Packet Library</h2>
          <span class="pill">{len(model["pages"])} packets</span>
        </div>
        <table class="pages-table">
          <thead><tr><th>Packet</th><th>Family</th><th>Authority</th><th>Source</th></tr></thead>
          <tbody id="pages-list">{page_rows}</tbody>
        </table>
      </section>
    </main>
  </div>
  <script>
    const model = JSON.parse(document.getElementById('spark-kb-data').textContent);
    const search = document.getElementById('search');
    const resultCount = document.getElementById('result-count');
    const actionPayload = document.getElementById('action-payload');
    const bridgeStatus = document.getElementById('bridge-status');
    const selectedInspector = document.getElementById('selected-inspector');
    const builderBridgeInput = document.getElementById('builder-bridge-input');
    const visionboardBridgeInput = document.getElementById('visionboard-bridge-input');
    const saveBridgeSettings = document.getElementById('save-bridge-settings');
    const themeToggle = document.getElementById('theme-toggle');
    const themeLabel = document.getElementById('theme-label');
    let activeFamily = 'all';

    function applyTheme(theme) {{
      const normalized = theme === 'light' ? 'light' : 'navy-dark';
      document.documentElement.setAttribute('data-theme', normalized);
      window.localStorage.setItem('sparkKbTheme', normalized);
      if (themeLabel) themeLabel.textContent = normalized === 'light' ? 'Light' : 'Dark';
    }}

    applyTheme(window.localStorage.getItem('sparkKbTheme') || 'navy-dark');

    if (themeToggle) {{
      themeToggle.addEventListener('click', () => {{
        const current = document.documentElement.getAttribute('data-theme') || 'navy-dark';
        applyTheme(current === 'light' ? 'navy-dark' : 'light');
      }});
    }}

    function endpointFromQuery(name, storageKey) {{
      const params = new URLSearchParams(window.location.search);
      return params.get(name) || window.localStorage.getItem(storageKey) || '';
    }}

    let builderBridgeEndpoint = endpointFromQuery('bridge', 'sparkBuilderBridgeUrl');
    let visionboardApiBaseUrl = endpointFromQuery('visionboard', 'sparkVisionboardApiBaseUrl')
      || model.canvas_board?.visionboard_api?.default_base_url
      || '';

    function setBridgeStatus(message, mode = '') {{
      bridgeStatus.textContent = message;
      bridgeStatus.classList.toggle('is-live', mode === 'live');
      bridgeStatus.classList.toggle('is-error', mode === 'error');
    }}

    function refreshBridgeStatus() {{
      if (builderBridgeInput) builderBridgeInput.value = builderBridgeEndpoint;
      if (visionboardBridgeInput) visionboardBridgeInput.value = visionboardApiBaseUrl;
      if (builderBridgeEndpoint || visionboardApiBaseUrl) {{
        setBridgeStatus(
          `Bridge enabled${{builderBridgeEndpoint ? ' / Builder' : ''}}${{visionboardApiBaseUrl ? ' / Spark Visionboard' : ''}}`,
          'live'
        );
      }} else {{
        setBridgeStatus('Local preview only. Set Builder Bridge or Spark Visionboard API to send actions.');
      }}
    }}

    function persistEndpoint(storageKey, value) {{
      if (value) {{
        window.localStorage.setItem(storageKey, value);
      }} else {{
        window.localStorage.removeItem(storageKey);
      }}
    }}

    if (saveBridgeSettings) {{
      saveBridgeSettings.addEventListener('click', () => {{
        builderBridgeEndpoint = builderBridgeInput?.value.trim() || '';
        visionboardApiBaseUrl = visionboardBridgeInput?.value.trim() || '';
        persistEndpoint('sparkBuilderBridgeUrl', builderBridgeEndpoint);
        persistEndpoint('sparkVisionboardApiBaseUrl', visionboardApiBaseUrl);
        refreshBridgeStatus();
      }});
    }}
    document.getElementById('create-visionboard-board')?.addEventListener('click', createVisionboardBoard);

    refreshBridgeStatus();

    async function createVisionboardBoard() {{
      if (!visionboardApiBaseUrl) {{
        setBridgeStatus('Set Spark Visionboard API before creating a board.', 'error');
        return;
      }}
      const board = model.canvas_board?.board || {{}};
      const endpoint = `${{visionboardApiBaseUrl.replace(/\\/$/, '')}}/boards`;
      const request = {{
        name: board.name || 'Spark Memory Wiki Visionboard Projection',
        objects: board.objects || {{}},
        layers: board.layers || [],
        viewport: board.viewport || {{ x: 0, y: 0, zoom: 1 }},
      }};
      actionPayload.textContent = JSON.stringify({{ action: 'create_visionboard_board', endpoint, request }}, null, 2);
      try {{
        const result = await postJson(endpoint, request);
        const boardId = result.board?.id || result.board_id || '';
        actionPayload.textContent = JSON.stringify({{ action: 'create_visionboard_board', endpoint, request, result }}, null, 2);
        setBridgeStatus(`Spark Visionboard created${{boardId ? `: ${{boardId}}` : ''}}.`, 'live');
      }} catch (error) {{
        setBridgeStatus(`Spark Visionboard create failed: ${{error.message}}`, 'error');
      }}
    }}

    function matchesSearch(element, term) {{
      if (!term) return true;
      return element.textContent.toLowerCase().includes(term);
    }}

    function escapeHtml(value) {{
      return String(value ?? '').replace(/[&<>"']/g, (char) => ({{
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
      }}[char]));
    }}

    function applyFilters() {{
      const term = search.value.trim().toLowerCase();
      let visibleTimeline = 0;
      document.querySelectorAll('.timeline-item').forEach((item) => {{
        const familyMatch = activeFamily === 'all' || item.dataset.family === activeFamily;
        const visible = familyMatch && matchesSearch(item, term);
        item.classList.toggle('is-hidden', !visible);
        if (visible) visibleTimeline += 1;
      }});
      document.querySelectorAll('.page-row').forEach((row) => {{
        const familyMatch = activeFamily === 'all' || row.dataset.family === activeFamily;
        row.classList.toggle('is-hidden', !(familyMatch && matchesSearch(row, term)));
      }});
      resultCount.textContent = `${{visibleTimeline}} visible`;
    }}

    document.querySelectorAll('.filter-chip[data-family]').forEach((button) => {{
      button.addEventListener('click', () => {{
        activeFamily = button.dataset.family;
        document.querySelectorAll('.filter-chip').forEach((chip) => chip.classList.remove('is-active'));
        button.classList.add('is-active');
        applyFilters();
      }});
    }});
    search.addEventListener('input', applyFilters);

    function highlightCanvasObject(canvasObjectId) {{
      document.querySelectorAll('.canvas-object').forEach((element) => {{
        const selected = Boolean(canvasObjectId) && element.dataset.canvasObjectId === canvasObjectId;
        const dimmed = Boolean(canvasObjectId) && !selected && !element.classList.contains('canvas-connector');
        element.classList.toggle('is-selected', selected);
        element.classList.toggle('is-dimmed', dimmed);
      }});
    }}

    function selectTimelineItem(itemId) {{
      const item = model.timeline.find((entry) => entry.id === itemId);
      document.querySelectorAll('.timeline-item').forEach((element) => {{
        element.classList.toggle('is-selected', element.dataset.itemId === itemId);
      }});
      highlightCanvasObject(item?.canvas_object_id || '');
      if (item) {{
        renderSelectedItem(item);
        actionPayload.textContent = JSON.stringify(buildActionPayload('inspect', item), null, 2);
      }}
    }}

    function renderSelectedItem(item) {{
      const sourcePills = (item.source_links || [])
        .map((source) => source.href
          ? `<a class="pill" href="${{escapeHtml(source.href)}}">${{escapeHtml(source.path)}}</a>`
          : `<span class="pill">${{escapeHtml(source.path)}}</span>`)
        .join('');
      const turnPills = (item.turn_ids || [])
        .map((turn) => `<span class="pill">${{escapeHtml(turn)}}</span>`)
        .join('');
      selectedInspector.innerHTML = `
        <div>
          <div class="timeline-kind">${{escapeHtml(item.kind)}} <span>${{escapeHtml(item.timestamp || 'snapshot order')}}</span></div>
          <h3 class="selected-title">${{escapeHtml(item.title)}}</h3>
          <p class="selected-detail">${{escapeHtml(item.detail || 'No detail captured.')}}</p>
        </div>
        <div class="selected-grid">
          <div class="selected-cell"><div class="metric-label">Family</div><div>${{escapeHtml(item.family)}}</div></div>
          <div class="selected-cell"><div class="metric-label">Authority</div><div>${{escapeHtml(item.authority)}}</div></div>
          <div class="selected-cell"><div class="metric-label">Visionboard Object</div><div>${{escapeHtml(item.canvas_object_id || '')}}</div></div>
          <div class="selected-cell"><div class="metric-label">Session</div><div>${{escapeHtml(item.session_id || '')}}</div></div>
        </div>
        <div class="timeline-meta">${{turnPills}}${{sourcePills}}</div>
      `;
    }}

    function buildActionPayload(action, item) {{
      const diagramPackets = model.canvas_board?.diagram_packets || [];
      return {{
        action,
        artifact: {{
          title: model.title,
          generated_at: model.generated_at,
          owner_system: 'domain-chip-memory',
          authority: 'visualization_only'
        }},
        timeline_item_id: item?.id,
        canvas_object_id: item?.canvas_object_id,
        title: item?.title,
        detail: item?.detail,
        authority: item?.authority,
        wiki_family: item?.family,
        source_paths: item?.source_paths || [],
        source_links: item?.source_links || [],
        session_id: item?.session_id || '',
        turn_ids: item?.turn_ids || [],
        spark_visionboard: {{
          schema: model.canvas_board?.schema,
          board_id: model.canvas_board?.board?.id,
          board_name: model.canvas_board?.board?.name,
          diagram_packet_ids: diagramPackets.map((packet) => packet.id),
          configured_base_url: visionboardApiBaseUrl || null,
          default_base_url: model.canvas_board?.visionboard_api?.default_base_url
        }},
        artifact_outputs: model.artifact_outputs || {{}},
        visionboard_instruction:
          action === 'generate_diagram'
            ? `Create a technical Spark Visionboard diagram for: ${{item?.title || 'selected wiki item'}}. Preserve provenance from source paths: ${{(item?.source_paths || []).join(', ')}}.`
            : '',
        note: 'Prepared for Spark Builder or Spark Visionboard bridge; artifact does not mutate memory directly.'
      }};
    }}

    async function postJson(endpoint, payload) {{
      const response = await fetch(endpoint, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(payload)
      }});
      const text = await response.text();
      let parsed = text;
      try {{ parsed = JSON.parse(text); }} catch (error) {{}}
      if (!response.ok) {{
        throw new Error(typeof parsed === 'string' ? parsed : JSON.stringify(parsed));
      }}
      return parsed;
    }}

    async function sendAction(action, item) {{
      const payload = buildActionPayload(action, item);
      actionPayload.textContent = JSON.stringify(payload, null, 2);

      if (action === 'generate_diagram' && visionboardApiBaseUrl) {{
        try {{
          const endpoint = `${{visionboardApiBaseUrl.replace(/\\/$/, '')}}/generate`;
          const result = await postJson(endpoint, {{
            instruction: payload.visionboard_instruction,
            style: 'technical',
            board: model.canvas_board?.board
          }});
          actionPayload.textContent = JSON.stringify({{ request: payload, visionboard_result: result }}, null, 2);
          setBridgeStatus(`Spark Visionboard generated ${{result.objects_created || 0}} objects on board ${{result.board_id || payload.spark_visionboard.board_id}}.`, 'live');
          return;
        }} catch (error) {{
          setBridgeStatus(`Spark Visionboard bridge failed: ${{error.message}}`, 'error');
          return;
        }}
      }}

      if (builderBridgeEndpoint) {{
        try {{
          const result = await postJson(builderBridgeEndpoint, payload);
          actionPayload.textContent = JSON.stringify({{ request: payload, bridge_result: result }}, null, 2);
          setBridgeStatus(`Builder bridge accepted ${{action}}.`, 'live');
          return;
        }} catch (error) {{
          setBridgeStatus(`Builder bridge failed: ${{error.message}}`, 'error');
          return;
        }}
      }}

      setBridgeStatus('Local preview only. Set Builder Bridge or Spark Visionboard API to send actions.');
    }}

    document.querySelectorAll('.timeline-item').forEach((itemElement) => {{
      itemElement.addEventListener('click', (event) => {{
        if (event.target.closest('button')) return;
        selectTimelineItem(itemElement.dataset.itemId);
      }});
      itemElement.addEventListener('keydown', (event) => {{
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault();
        selectTimelineItem(itemElement.dataset.itemId);
      }});
    }});

    document.querySelectorAll('[data-action]').forEach((button) => {{
      button.addEventListener('click', async () => {{
        const item = model.timeline.find((entry) => entry.id === button.dataset.itemId);
        if (item) {{
          selectTimelineItem(item.id);
        }}
        await sendAction(button.dataset.action, item);
      }});
    }});
  </script>
</body>
</html>
"""


def _spark_logo_markup() -> str:
    return """
<div class="brand-lockup" aria-label="Spark LLM Wiki">
  <svg class="spark-mark" viewBox="0 0 264 113" preserveAspectRatio="xMidYMid meet" aria-hidden="true" fill="none">
    <path fill="currentColor" d="M189.07 0.85c-24.3 4.4-39.5 14.7-80.5 54.5-35.2 34.2-37.3 35.9-49.8 39.7-18.4 5.6-39.1-3.2-47.4-20-6.5-13.2-2.6-32.5 8.4-42.1 8.7-7.7 14.1-9.6 27.3-9.6 14.7 0 19.4 2.1 37.4 16.5 12.8 10.3 12.8 10.3 15.4 7.6 2.7-2.7 2.7-2.7-1.3-6.2-25.2-21.9-34.3-26.7-51-26.8-14.7 0-25.7 4.6-35 14.6-30.7 33.2-.9 83.4 44.4 74.8 14-2.6 23.6-9.7 54.3-39.8 46.8-46 63.7-56.2 92.8-56.3 61.2-.1 73.1 80.1 14.2 95.2-24 6.1-50.2-3-81.4-28.3-10.1-8.2-11.3-8.6-14.6-4.5-2.7 3.3 25.8 25.1 43.3 33.2 31.9 14.8 63.1 11.8 82.9-8 31.2-31.2 15.8-83.8-27.5-94-6.8-1.6-24.1-1.8-31.9-.5Z" />
  </svg>
  <svg class="spark-wordmark" viewBox="0 0 218 59" preserveAspectRatio="xMidYMid meet" aria-hidden="true" fill="none">
    <g transform="translate(-0.253195,59) scale(0.1,-0.1)" fill="currentColor">
      <path d="M52 435c-38-16-56-56-47-101 9-50 42-65 153-69 100-3 122-13 122-55 0-40-31-50-153-50-112 0-117-1-117-21 0-20 4-20 129-17 155 4 181 17 181 94 0 66-30 84-136 84-101 0-130 10-137 45-9 52 18 65 143 65 103 0 110 1 110 20 0 26-192 29-248 5Z" />
      <path d="M573 443c-31-6-70-48-77-84-14-72-7-349 9-356 24-9 28 1 31 74 1 38 3 69 3 71 1 1 14-4 31-13 73-38 229-11 257 45 17 34 16 163-1 204-23 56-134 82-253 59Zm180-44c63-29 64-209 2-233-53-20-187-2-207 28-10 14-10 168 0 182 22 33 151 48 205 23Z" />
      <path d="M1152 443c-10-4-162-303-162-319 0-2 10-4 23-4 19 0 31 21 86 140 35 77 70 140 76 140 6 0 22-24 34-52 82-188 104-228 127-228h23l-18 43c-113 256-142 299-189 280Z" />
      <path d="M1520 285c0-158 1-165 20-165 19 0 20 7 20 114 0 63 3 122 6 131 10 25 58 45 109 45 38 0 45 3 45 20 0 25-79 28-124 5-35-18-36-18-36 0 0 8-9 15-20 15-19 0-20-7-20-165Z" />
      <path d="M1880 355c0-228 1-235 20-235 16 0 20 7 20 33 0 26 10 42 46 77l45 45 37-40c20-22 51-57 67-78 23-30 37-38 55-35 23 3 21 6-35 73-33 39-66 78-74 88-13 16-8 25 60 93 72 72 73 74 44 74-25 0-48-18-130-100-55-55-103-100-107-100-5 0-8 77-8 170 0 163-1 170-20 170-19 0-20-7-20-235Z" />
    </g>
  </svg>
  <span class="spark-divider" aria-hidden="true"></span>
  <span class="spark-product"><span>/</span>wiki</span>
</div>"""


def _family_label(family: str) -> str:
    cleaned = str(family or "").strip()
    for prefix in ("memory_kb_", "builder_llm_", "spark_"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            break
    return cleaned.replace("_", " ").replace("-", " ").title() or "Wiki"


def _render_stat(label: str, value: str, help_text: str) -> str:
    return f"""
<div class="stat-card">
  <div class="metric-label">{escape(label)}</div>
  <div class="metric-value">{escape(value)}</div>
  <div class="metric-help">{escape(help_text)}</div>
</div>"""


def _render_timeline_item(item: dict[str, Any]) -> str:
    source_pills = "".join(
        f'<a class="pill" href="{escape(source["href"])}">{escape(source["path"])}</a>'
        if source.get("href")
        else f'<span class="pill">{escape(source["path"])}</span>'
        for source in item.get("source_links", [])
    )
    turn_pills = "".join(f'<span class="pill">{escape(turn)}</span>' for turn in item["turn_ids"])
    timestamp = escape(item["timestamp"] or "snapshot order")
    detail = escape(item["detail"] or "No detail captured.")
    return f"""
<article class="timeline-item" tabindex="0" data-item-id="{escape(item["id"])}" data-canvas-object-id="{escape(item.get("canvas_object_id", ""))}" data-family="{escape(item["family"])}" data-kind="{escape(item["kind"])}">
  <div class="timeline-kind">{escape(item["kind"])} <span>{timestamp}</span></div>
  <h3 class="timeline-title">{escape(item["title"])}</h3>
  <p class="timeline-detail">{detail}</p>
  <div class="timeline-meta">
    <span class="pill">{escape(item["family"])}</span>
    <span class="pill">{escape(item["authority"])}</span>
    {turn_pills}
    {source_pills}
  </div>
  <div class="action-row">
    <button class="action-button" data-action="ask_agent" data-item-id="{escape(item["id"])}">Ask Agent</button>
    <button class="action-button" data-action="find_support" data-item-id="{escape(item["id"])}">Find Support</button>
    <button class="action-button" data-action="generate_diagram" data-item-id="{escape(item["id"])}">Generate Diagram</button>
  </div>
</article>"""


def _render_page_row(page: dict[str, Any]) -> str:
    return f"""
<tr class="page-row" data-family="{escape(page["wiki_family"])}">
  <td>
    <a href="{escape(page["href"])}">{escape(page["title"])}</a>
    <div class="page-summary">{escape(page["summary"] or page["excerpt"])}</div>
  </td>
  <td><span class="pill">{escape(page["wiki_family"])}</span></td>
  <td><span class="pill">{escape(page["authority"])}</span></td>
  <td><span class="pill">{escape(page["source_of_truth"])}</span></td>
</tr>"""


def _render_canvas_board(canvas_board: dict[str, Any]) -> str:
    board = canvas_board.get("board") or {}
    objects = board.get("objects") or {}
    visible_objects = [obj for obj in objects.values() if isinstance(obj, dict) and obj.get("visible", True)]
    if not visible_objects:
        return '<div class="empty-state">No Spark Visionboard projection found.</div>'
    min_x = min(int(obj.get("x") or 0) for obj in visible_objects)
    min_y = min(int(obj.get("y") or 0) for obj in visible_objects)
    max_x = max(int(obj.get("x") or 0) + int(obj.get("width") or 1) for obj in visible_objects)
    max_y = max(int(obj.get("y") or 0) + int(obj.get("height") or 1) for obj in visible_objects)
    pad = 40
    view_box = f"{min_x - pad} {min_y - pad} {max_x - min_x + pad * 2} {max_y - min_y + pad * 2}"
    connector_markup = []
    object_markup = []
    for obj in sorted(visible_objects, key=lambda item: int(item.get("zIndex") or 0)):
        if obj.get("type") == "connector":
            connector_markup.append(_render_canvas_connector(obj))
        elif obj.get("type") in {"shape", "sticky", "frame"}:
            object_markup.append(_render_canvas_object(obj))
    return f"""
<div class="canvas-preview-wrap">
  <svg class="canvas-preview" viewBox="{escape(view_box)}" role="img" aria-label="Spark Visionboard projection">
    <defs>
      <marker id="canvasArrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#2FCA94"></path>
      </marker>
    </defs>
    <rect x="{min_x - pad}" y="{min_y - pad}" width="{max_x - min_x + pad * 2}" height="{max_y - min_y + pad * 2}" fill="#141820"></rect>
    <g>{''.join(connector_markup)}</g>
    <g>{''.join(object_markup)}</g>
  </svg>
</div>"""


def _render_canvas_connector(obj: dict[str, Any]) -> str:
    points = obj.get("points") or []
    if len(points) < 2:
        return ""
    point_text = " ".join(f"{int(point.get('x') or 0)},{int(point.get('y') or 0)}" for point in points)
    stroke = escape(str(obj.get("stroke") or "#2FCA94"))
    dash = ' stroke-dasharray="8 8"' if obj.get("dashed") else ""
    marker = ' marker-end="url(#canvasArrow)"' if obj.get("endArrow") else ""
    label = escape(str(obj.get("label") or ""))
    mid = points[len(points) // 2]
    label_markup = (
        f'<text x="{int(mid.get("x") or 0) + 6}" y="{int(mid.get("y") or 0) - 6}" fill="#8890B0" font-size="11" font-family="DM Mono, Consolas, monospace">{label}</text>'
        if label
        else ""
    )
    return (
        f'<g class="canvas-object canvas-connector" data-canvas-object-id="{escape(str(obj.get("id") or ""))}">'
        f'<polyline points="{point_text}" fill="none" stroke="{stroke}" stroke-width="{int(obj.get("strokeWidth") or 2)}"{dash}{marker}></polyline>'
        f"{label_markup}</g>"
    )


def _render_canvas_object(obj: dict[str, Any]) -> str:
    object_id = escape(str(obj.get("id") or ""))
    x = int(obj.get("x") or 0)
    y = int(obj.get("y") or 0)
    width = int(obj.get("width") or 1)
    height = int(obj.get("height") or 1)
    obj_type = str(obj.get("type") or "")
    if obj_type == "frame":
        label = escape(str(obj.get("label") or "Frame"))
        return (
            f'<g class="canvas-object" data-canvas-object-id="{object_id}">'
            f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="8" fill="{escape(str(obj.get("backgroundColor") or "rgba(24,28,38,0.72)"))}" stroke="#2A2E40"></rect>'
            f'<text x="{x + 18}" y="{y + 26}" fill="#506070" font-size="13" font-family="DM Mono, Consolas, monospace">{label}</text>'
            f"</g>"
        )
    if obj_type == "sticky":
        fill = {
            "green": "#16352C",
            "blue": "#172B3D",
            "purple": "#2A2440",
            "yellow": "#34331E",
            "orange": "#3A2A1E",
            "pink": "#3A2032",
        }.get(str(obj.get("color") or ""), "#141820")
        stroke = {
            "green": "#2FCA94",
            "blue": "#90C8E0",
            "purple": "#B8A8DC",
            "yellow": "#D8C868",
            "orange": "#D8A068",
            "pink": "#D890B8",
        }.get(str(obj.get("color") or ""), "#2A2E40")
        return _render_canvas_labeled_rect(obj, x, y, width, height, fill=fill, stroke=stroke, label=str(obj.get("content") or ""))
    return _render_canvas_labeled_rect(
        obj,
        x,
        y,
        width,
        height,
        fill=str(obj.get("fill") or "#141820"),
        stroke=str(obj.get("stroke") or "#2FCA94"),
        label=str(obj.get("content") or obj.get("label") or ""),
    )


def _render_canvas_labeled_rect(
    obj: dict[str, Any],
    x: int,
    y: int,
    width: int,
    height: int,
    *,
    fill: str,
    stroke: str,
    label: str,
) -> str:
    lines = [line.strip() for line in label.splitlines() if line.strip()][:3]
    text_lines = []
    start_y = y + max(24, height // 2 - (len(lines) - 1) * 9)
    for index, line in enumerate(lines):
        fill_color = "#F0F0F4" if index == 0 else "#8890B0"
        font_size = 14 if index == 0 else 11
        text_lines.append(
            f'<text x="{x + 16}" y="{start_y + index * 20}" fill="{fill_color}" font-size="{font_size}" font-family="DM Mono, Consolas, monospace">{escape(line[:34])}</text>'
        )
    return (
        f'<g class="canvas-object" data-canvas-object-id="{escape(str(obj.get("id") or ""))}">'
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="6" fill="{escape(fill)}" stroke="{escape(stroke)}" stroke-width="2"></rect>'
        f"{''.join(text_lines)}</g>"
    )
