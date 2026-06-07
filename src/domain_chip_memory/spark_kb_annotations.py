from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ALLOWED_DECISIONS = {
    "agent_note",
    "promote_to_lesson",
    "reject_as_noise",
    "needs_evidence",
    "ready_for_review",
}


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slugify(value: str, *, max_length: int = 96) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")
    slug = normalized or "annotation"
    if len(slug) <= max_length:
        return slug
    digest = hashlib.sha1(slug.encode("utf-8")).hexdigest()[:8]
    trimmed = slug[: max_length - len(digest) - 1].rstrip("-")
    return f"{trimmed}-{digest}" if trimmed else digest


def _redact_human_text(value: object) -> str:
    redacted = str(value or "")
    replacements = [
        (r"sscli_[A-Za-z0-9._-]+", "[redacted workspace token]"),
        (r"(?i)\bbearer\s+[A-Za-z0-9._-]{16,}", "Bearer [redacted token]"),
        (
            r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|secret|session[_-]?token)\s*[:=]\s*[A-Za-z0-9._:/+=-]{12,}",
            r"\1=[redacted]",
        ),
        (r"\bsk-[A-Za-z0-9]{20,}\b", "[redacted api key]"),
        (r"\b[A-Za-z]:\\[^\s\n\r]+", "[local path]"),
        (r"\b[A-Za-z0-9_-]{64,}\b", "[redacted opaque value]"),
    ]
    for pattern, replacement in replacements:
        redacted = re.sub(pattern, replacement, redacted)
    redacted = re.sub(r"(?i)\bCommand failed:[^\n\r]*", "[debug detail omitted]", redacted)
    redacted = re.sub(r"(?i)\b(traceback|stack trace|exception in thread)[^\n\r]*", "[debug detail omitted]", redacted)
    redacted = re.sub(r"(?i)\b(python\s+-m|pnpm\s+|npm\s+|curl\s+|powershell\s+|cmd\.exe)[^\n\r]*", "[command detail omitted]", redacted)
    safe_lines: list[str] = []
    for line in redacted.splitlines():
        if re.search(r"(?i)\b(traceback|stack trace|exception in thread|command failed:)\b", line):
            safe_lines.append("[debug detail omitted]")
        elif re.search(r"(?i)\b(python\s+-m|pnpm\s+|npm\s+|curl\s+|powershell\s+|cmd\.exe)\b", line):
            safe_lines.append("[command detail omitted]")
        else:
            safe_lines.append(line)
    return "\n".join(safe_lines)


def _safe_line(value: object, *, max_chars: int = 220) -> str:
    cleaned = re.sub(r"\s+", " ", _redact_human_text(value)).strip()
    if len(cleaned) > max_chars:
        return cleaned[: max_chars - 1].rstrip() + "..."
    return cleaned


def _sanitize_packet(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _sanitize_packet(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_packet(item) for item in value]
    if isinstance(value, str):
        return _redact_human_text(value)
    return value


def _load_packet(packet_or_path: str | Path | dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    if isinstance(packet_or_path, dict):
        return dict(packet_or_path), None
    packet_path = Path(packet_or_path)
    try:
        payload = json.loads(packet_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON (spark_kb_annotations.py)") from exc
    if not isinstance(payload, dict):
        raise ValueError("Spark KB annotation packet must be a JSON object.")
    return payload, str(packet_path)


def _validate_packet(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if str(packet.get("schema") or "").strip() != "spark-kb-annotation.v1":
        errors.append("schema must be spark-kb-annotation.v1")
    if not str(packet.get("target_id") or "").strip():
        errors.append("target_id is required")
    if not str(packet.get("note") or "").strip():
        errors.append("note is required")
    decision = str(packet.get("decision") or "").strip()
    if decision and decision not in ALLOWED_DECISIONS:
        errors.append(f"decision must be one of {', '.join(sorted(ALLOWED_DECISIONS))}")
    return errors


def _annotation_frontmatter(
    *,
    title: str,
    imported_at: str,
    privacy_state: str,
    authority: str,
    decision: str,
    target_type: str,
    target_id: str,
) -> str:
    def q(value: str) -> str:
        return '"' + value.replace('"', '\\"') + '"'

    return "\n".join(
        [
            "---",
            f"title: {q(title)}",
            f"date_created: {imported_at[:10]}",
            f"date_modified: {imported_at[:10]}",
            f"generated_at: {q(imported_at)}",
            "type: spark_kb_annotation",
            "status: imported_local_review",
            f"privacy_state: {q(privacy_state)}",
            f"authority: {q(authority)}",
            f"decision: {q(decision)}",
            f"target_type: {q(target_type)}",
            f"target_id: {q(target_id)}",
            "owner_system: domain-chip-memory",
            "tags: [spark-kb, annotation, local-private]",
            "---",
            "",
        ]
    )


def import_spark_kb_annotation(
    output_dir: str | Path,
    packet_or_path: str | Path | dict[str, Any],
) -> dict[str, Any]:
    output_path = Path(output_dir)
    packet, source_file = _load_packet(packet_or_path)
    errors = _validate_packet(packet)
    if errors:
        raise ValueError("; ".join(errors))

    imported_at = _utc_timestamp()
    redacted_packet = _sanitize_packet(packet)
    target_type = _safe_line(redacted_packet.get("target_type") or "recursive_run", max_chars=80)
    target_id = _safe_line(redacted_packet.get("target_id") or "unknown-target", max_chars=140)
    target_label = _safe_line(redacted_packet.get("target_label") or target_id, max_chars=140)
    decision = _safe_line(redacted_packet.get("decision") or "agent_note", max_chars=80)
    note = _safe_line(redacted_packet.get("note") or "", max_chars=900)
    source_href = _safe_line(redacted_packet.get("source_href") or "", max_chars=220)
    privacy_state = _safe_line(redacted_packet.get("privacy_state") or "local/private", max_chars=80)
    authority = _safe_line(redacted_packet.get("authority") or "supporting_not_authoritative", max_chars=100)

    annotation_id_seed = str(packet.get("id") or packet.get("target_id") or target_label or imported_at)
    annotation_slug = _slugify(f"{target_label}-{decision}-{annotation_id_seed}")
    raw_dir = output_path / "raw" / "annotations"
    wiki_dir = output_path / "wiki" / "annotations"
    raw_dir.mkdir(parents=True, exist_ok=True)
    wiki_dir.mkdir(parents=True, exist_ok=True)

    raw_packet = {
        "schema": "spark-kb-annotation-import.v1",
        "imported_at": imported_at,
        "source_file": source_file,
        "packet": {
            **redacted_packet,
            "import_status": "imported_local_review",
        },
    }
    raw_file = raw_dir / f"{annotation_slug}.json"
    raw_file.write_text(json.dumps(raw_packet, indent=2) + "\n", encoding="utf-8")

    title = f"Annotation - {target_label}"
    markdown_file = wiki_dir / f"{annotation_slug}.md"
    markdown_lines = [
        _annotation_frontmatter(
            title=title,
            imported_at=imported_at,
            privacy_state=privacy_state,
            authority=authority,
            decision=decision,
            target_type=target_type,
            target_id=target_id,
        ),
        f"# {title}",
        "",
        "## Note",
        note,
        "",
        "## Review State",
        f"- Decision: `{decision}`",
        f"- Privacy: `{privacy_state}`",
        f"- Authority: `{authority}`",
        "- Claim boundary: supporting context only; live Workspace, tests, and traces still win.",
        "",
        "## Target",
        f"- Type: `{target_type}`",
        f"- ID: `{target_id}`",
        f"- Label: `{target_label}`",
    ]
    if source_href and "[local path]" not in source_href:
        markdown_lines.extend(["", "## Source", f"- {source_href}"])
    markdown_lines.extend(["", "## Raw Packet", f"- `raw/annotations/{raw_file.name}`", ""])
    markdown_file.write_text("\n".join(markdown_lines), encoding="utf-8")

    annotation_pages = sorted(path for path in wiki_dir.glob("*.md") if path.name != "_index.md")
    index_lines = [
        _annotation_frontmatter(
            title="Spark KB Annotations",
            imported_at=imported_at,
            privacy_state="local/private",
            authority="supporting_not_authoritative",
            decision="index",
            target_type="annotation_index",
            target_id="spark-kb-annotations",
        ),
        "# Spark KB Annotations",
        "",
        "Local/private notes imported from the LLM Wiki dashboard. These are review aids, not live runtime truth.",
        "",
        "## Notes",
    ]
    index_lines.extend(f"- [[annotations/{path.stem}]]" for path in annotation_pages)
    index_lines.append("")
    index_file = wiki_dir / "_index.md"
    index_file.write_text("\n".join(index_lines), encoding="utf-8")

    return {
        "schema": "spark-kb-annotation-import.v1",
        "imported": True,
        "imported_at": imported_at,
        "privacy_state": privacy_state,
        "authority": authority,
        "decision": decision,
        "target_type": target_type,
        "target_id": target_id,
        "target_label": target_label,
        "output_dir": str(output_path),
        "files": {
            "raw_packet": str(raw_file),
            "markdown_page": str(markdown_file),
            "index": str(index_file),
        },
        "claim_boundary": "supporting_context_only",
    }


def build_spark_kb_annotation_contract_summary() -> dict[str, Any]:
    return {
        "contract_name": "SparkKbAnnotationImport",
        "packet_schema": "spark-kb-annotation.v1",
        "claim_boundary": "supporting_context_only",
        "privacy_default": "local/private",
        "writes": ["raw/annotations/<annotation>.json", "wiki/annotations/<annotation>.md", "wiki/annotations/_index.md"],
        "redaction": [
            "workspace tokens",
            "access/refresh/session tokens",
            "api keys",
            "local paths",
            "long opaque strings",
            "command dumps and stack traces",
        ],
    }
