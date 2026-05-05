from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .contracts import JsonDict


WIKI_PACKET_SOURCE_CLASS = "obsidian_llm_wiki_packets"
DEFAULT_WIKI_PACKET_AUTHORITY = "supporting_not_authoritative"


@dataclass(frozen=True)
class MarkdownKnowledgePacket:
    packet_id: str
    title: str
    text: str
    source_path: str
    source_class: str = WIKI_PACKET_SOURCE_CLASS
    tags: list[str] = field(default_factory=list)
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class WikiPacketHit:
    source_class: str
    packet_id: str
    title: str
    text: str
    score: float
    provenance: JsonDict
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class WikiPacketRetrievalResult:
    query: str
    hits: list[WikiPacketHit]
    trace: JsonDict = field(default_factory=dict)


def build_wiki_packet_reader_contract_summary() -> JsonDict:
    return {
        "contract_name": "ObsidianLlmWikiPacketReader",
        "source_class": WIKI_PACKET_SOURCE_CLASS,
        "authority": "supporting_not_authoritative",
        "runtime_role": "compiled_project_knowledge",
        "inputs": ["markdown_files", "obsidian_vault_dirs", "llm_wiki_packet_dirs"],
        "outputs": ["WikiPacketHit", "MarkdownKnowledgePacketInventory"],
        "normalized_metadata_fields": [
            "wiki_family",
            "owner_system",
            "authority",
            "scope_kind",
            "source_of_truth",
            "status",
            "freshness",
            "generated_at",
            "last_verified_at",
            "source_path",
        ],
        "non_override_rules": [
            "Wiki packets cannot close user-level focus or plan.",
            "Wiki packets cannot override current_state for mutable user facts.",
            "Wiki packets are ignored when query overlap is zero.",
            "Every hit must carry source_path provenance.",
        ],
    }


def discover_markdown_knowledge_packets(
    paths: list[str | Path],
    *,
    max_file_bytes: int = 200_000,
    page_limit: int = 200,
) -> JsonDict:
    packets = read_markdown_knowledge_packets(paths, max_file_bytes=max_file_bytes)
    pages = [_packet_inventory_page(packet) for packet in packets]
    pages.sort(key=lambda page: (str(page.get("wiki_family") or ""), str(page.get("source_path") or "")))
    family_counts = Counter(str(page.get("wiki_family") or "unknown") for page in pages)
    authority_counts = Counter(str(page.get("authority") or "unknown") for page in pages)
    owner_counts = Counter(str(page.get("owner_system") or "unknown") for page in pages)
    source_of_truth_counts = Counter(str(page.get("source_of_truth") or "unknown") for page in pages)
    freshness_counts = Counter(str(page.get("freshness") or "unknown") for page in pages)
    normalized_limit = max(0, int(page_limit or 0))
    return {
        "contract_name": "MarkdownKnowledgePacketInventory",
        "operation": "discover_markdown_knowledge_packets",
        "source_class": WIKI_PACKET_SOURCE_CLASS,
        "authority": DEFAULT_WIKI_PACKET_AUTHORITY,
        "roots": [_path_inventory(raw_path) for raw_path in paths],
        "packet_count": len(pages),
        "family_counts": dict(sorted(family_counts.items())),
        "authority_counts": dict(sorted(authority_counts.items())),
        "owner_system_counts": dict(sorted(owner_counts.items())),
        "source_of_truth_counts": dict(sorted(source_of_truth_counts.items())),
        "freshness_counts": dict(sorted(freshness_counts.items())),
        "pages": pages[:normalized_limit],
        "page_limit": normalized_limit,
        "dropped_page_count": max(0, len(pages) - normalized_limit),
        "non_override_rules": [
            "Inventory rows are discovery metadata, not prompt instructions.",
            "Memory KB pages are downstream of governed memory snapshots.",
            "Builder LLM wiki pages remain supporting_not_authoritative.",
            "Current-state memory must be queried directly for mutable user facts.",
        ],
    }


def read_markdown_knowledge_packets(
    paths: list[str | Path],
    *,
    max_file_bytes: int = 200_000,
) -> list[MarkdownKnowledgePacket]:
    packets: list[MarkdownKnowledgePacket] = []
    for file_path in _iter_markdown_files(paths):
        try:
            if file_path.stat().st_size > max_file_bytes:
                continue
            raw_text = file_path.read_text(encoding="utf-8")
        except Exception:
            continue
        title, body, frontmatter = _parse_markdown_packet(raw_text=raw_text, fallback_title=file_path.stem)
        text = _compact_markdown_text(body)
        if not text:
            continue
        packets.append(
            MarkdownKnowledgePacket(
                packet_id=str(file_path.resolve()),
                title=title,
                text=text,
                source_path=str(file_path.resolve()),
                tags=_extract_tags(raw_text=raw_text, frontmatter=frontmatter),
                metadata={
                    "file_name": file_path.name,
                    "frontmatter": frontmatter,
                    **_normalized_wiki_packet_metadata(file_path=file_path, frontmatter=frontmatter),
                    "word_count": len(text.split()),
                },
            )
        )
    return packets


def retrieve_markdown_knowledge_packets(
    *,
    paths: list[str | Path],
    query: str,
    top_k: int = 5,
    max_file_bytes: int = 200_000,
) -> WikiPacketRetrievalResult:
    normalized_query = str(query or "").strip()
    packets = read_markdown_knowledge_packets(paths, max_file_bytes=max_file_bytes)
    query_tokens = _query_tokens(normalized_query)
    scored: list[tuple[float, MarkdownKnowledgePacket, list[str]]] = []
    for packet in packets:
        score, reasons = _score_packet(packet=packet, query_tokens=query_tokens)
        if score <= 0:
            continue
        scored.append((score, packet, reasons))
    scored.sort(key=lambda item: item[0], reverse=True)
    hits = [
        WikiPacketHit(
            source_class=WIKI_PACKET_SOURCE_CLASS,
            packet_id=packet.packet_id,
            title=packet.title,
            text=_clip_text(packet.text, max_chars=1600),
            score=round(score, 3),
            provenance={
                "source": WIKI_PACKET_SOURCE_CLASS,
                "source_path": packet.source_path,
                "title": packet.title,
                "reasons": reasons,
            },
            metadata={
                **packet.metadata,
                "tags": packet.tags,
                "authority": str(packet.metadata.get("authority") or DEFAULT_WIKI_PACKET_AUTHORITY),
            },
        )
        for score, packet, reasons in scored[: max(1, int(top_k or 1))]
    ]
    return WikiPacketRetrievalResult(
        query=normalized_query,
        hits=hits,
        trace={
            "operation": "retrieve_markdown_knowledge_packets",
            "source_class": WIKI_PACKET_SOURCE_CLASS,
            "packet_count": len(packets),
            "hit_count": len(hits),
            "top_k": max(1, int(top_k or 1)),
        },
    )


def _packet_inventory_page(packet: MarkdownKnowledgePacket) -> JsonDict:
    metadata = dict(packet.metadata or {})
    return {
        "packet_id": packet.packet_id,
        "title": packet.title,
        "source_path": packet.source_path,
        "source_class": packet.source_class,
        "wiki_family": str(metadata.get("wiki_family") or "unknown"),
        "owner_system": str(metadata.get("owner_system") or "unknown"),
        "authority": str(metadata.get("authority") or DEFAULT_WIKI_PACKET_AUTHORITY),
        "scope_kind": str(metadata.get("scope_kind") or "unknown"),
        "source_of_truth": str(metadata.get("source_of_truth") or "unknown"),
        "status": str(metadata.get("status") or "unknown"),
        "freshness": str(metadata.get("freshness") or "unknown"),
        "generated_at": str(metadata.get("generated_at") or ""),
        "last_verified_at": str(metadata.get("last_verified_at") or ""),
        "tags": list(packet.tags),
        "word_count": int(metadata.get("word_count") or 0),
    }


def _path_inventory(raw_path: str | Path) -> JsonDict:
    path = Path(raw_path).expanduser()
    return {
        "path": str(path),
        "exists": path.exists(),
        "kind": "file" if path.is_file() else ("directory" if path.is_dir() else "missing"),
    }


def _iter_markdown_files(paths: list[str | Path]) -> list[Path]:
    files: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if path.is_file() and path.suffix.lower() == ".md":
            files.append(path)
            continue
        if path.is_dir():
            files.extend(sorted(item for item in path.rglob("*.md") if item.is_file()))
    return sorted(set(files), key=lambda item: str(item).casefold())


def _parse_markdown_packet(*, raw_text: str, fallback_title: str) -> tuple[str, str, JsonDict]:
    text = raw_text.replace("\r\n", "\n")
    frontmatter: JsonDict = {}
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end >= 0:
            frontmatter_text = text[4:end]
            frontmatter = _parse_simple_frontmatter(frontmatter_text)
            body = text[end + 5 :]
    title = str(frontmatter.get("title") or "").strip()
    if not title:
        heading = re.search(r"^\s*#\s+(.+?)\s*$", body, flags=re.MULTILINE)
        title = heading.group(1).strip() if heading else fallback_title
    return title, body, frontmatter


def _parse_simple_frontmatter(text: str) -> JsonDict:
    payload: JsonDict = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        payload[key.strip()] = value.strip().strip('"').strip("'")
    return payload


def _normalized_wiki_packet_metadata(*, file_path: Path, frontmatter: JsonDict) -> JsonDict:
    family = _wiki_family_from_path(file_path=file_path, frontmatter=frontmatter)
    owner_system = _frontmatter_string(frontmatter, "owner_system") or _default_owner_system(family)
    source_of_truth = _frontmatter_string(frontmatter, "source_of_truth") or _default_source_of_truth(family)
    authority = _frontmatter_string(frontmatter, "authority") or DEFAULT_WIKI_PACKET_AUTHORITY
    return {
        "source_path": str(file_path.resolve()),
        "source_class": WIKI_PACKET_SOURCE_CLASS,
        "wiki_family": family,
        "owner_system": owner_system,
        "authority": authority,
        "scope_kind": _frontmatter_string(frontmatter, "scope_kind") or _default_scope_kind(family),
        "source_of_truth": source_of_truth,
        "status": _frontmatter_string(frontmatter, "status") or "unknown",
        "freshness": _frontmatter_string(frontmatter, "freshness") or _default_freshness(frontmatter),
        "generated_at": _frontmatter_string(frontmatter, "generated_at")
        or _frontmatter_string(frontmatter, "date_modified")
        or _frontmatter_string(frontmatter, "date_created"),
        "last_verified_at": _frontmatter_string(frontmatter, "last_verified_at"),
    }


def _frontmatter_string(frontmatter: JsonDict, key: str) -> str:
    value = str(frontmatter.get(key) or "").strip()
    return value


def _wiki_family_from_path(*, file_path: Path, frontmatter: JsonDict) -> str:
    explicit = _frontmatter_string(frontmatter, "wiki_family") or _frontmatter_string(frontmatter, "family")
    if explicit:
        return explicit
    parts = [part.casefold().replace("_", "-") for part in file_path.parts]
    if "current-state" in parts:
        return "memory_kb_current_state"
    if "evidence" in parts:
        return "memory_kb_evidence"
    if "events" in parts:
        return "memory_kb_event"
    if "syntheses" in parts:
        return "memory_kb_synthesis"
    if "outputs" in parts:
        return "memory_kb_output"
    if "sources" in parts:
        return "memory_kb_source"
    if "diagnostics" in parts:
        return "diagnostics"
    return "builder_llm_wiki"


def _default_owner_system(wiki_family: str) -> str:
    if wiki_family.startswith("memory_kb_"):
        return "domain-chip-memory"
    if wiki_family == "diagnostics":
        return "spark-intelligence-builder"
    return "spark-intelligence-builder"


def _default_source_of_truth(wiki_family: str) -> str:
    if wiki_family.startswith("memory_kb_"):
        return "SparkMemorySDK"
    if wiki_family == "diagnostics":
        return "diagnostics"
    return "builder_llm_wiki"


def _default_scope_kind(wiki_family: str) -> str:
    if wiki_family.startswith("memory_kb_"):
        return "governed_memory"
    if wiki_family == "diagnostics":
        return "diagnostics"
    return "project_or_system"


def _default_freshness(frontmatter: JsonDict) -> str:
    if _frontmatter_string(frontmatter, "last_verified_at"):
        return "verified"
    if _frontmatter_string(frontmatter, "generated_at") or _frontmatter_string(frontmatter, "date_modified"):
        return "generated"
    return "unknown"


def _extract_tags(*, raw_text: str, frontmatter: JsonDict) -> list[str]:
    tags: set[str] = set()
    frontmatter_tags = str(frontmatter.get("tags") or "").strip()
    if frontmatter_tags:
        tags.update(token.strip("[] ,#") for token in frontmatter_tags.split(","))
    tags.update(match.group(1) for match in re.finditer(r"(?<!\w)#([A-Za-z0-9_/-]+)", raw_text))
    return sorted(tag for tag in tags if tag)


def _compact_markdown_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == "---":
            continue
        lines.append(stripped)
    return "\n".join(lines)


def _score_packet(*, packet: MarkdownKnowledgePacket, query_tokens: set[str]) -> tuple[float, list[str]]:
    if not query_tokens:
        return 0.0, []
    title = packet.title.casefold()
    text = packet.text.casefold()
    tags = " ".join(packet.tags).casefold()
    score = 0.0
    reasons: list[str] = []
    title_hits = {token for token in query_tokens if token in title}
    text_hits = {token for token in query_tokens if token in text}
    tag_hits = {token for token in query_tokens if token in tags}
    if title_hits:
        score += len(title_hits) * 8.0
        reasons.append(f"title_overlap:{len(title_hits)}")
    if text_hits:
        score += min(30.0, len(text_hits) * 3.0)
        reasons.append(f"text_overlap:{len(text_hits)}")
    if tag_hits:
        score += len(tag_hits) * 5.0
        reasons.append(f"tag_overlap:{len(tag_hits)}")
    return score, reasons


def _query_tokens(query: str) -> set[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "based",
        "did",
        "do",
        "for",
        "from",
        "have",
        "i",
        "in",
        "is",
        "it",
        "me",
        "my",
        "of",
        "on",
        "our",
        "should",
        "the",
        "this",
        "to",
        "was",
        "what",
        "where",
        "with",
        "you",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_-]*", str(query or "").casefold())
        if token and token not in stopwords
    }


def _clip_text(text: str, *, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
