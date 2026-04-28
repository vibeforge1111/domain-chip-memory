from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .contracts import JsonDict


WIKI_PACKET_SOURCE_CLASS = "obsidian_llm_wiki_packets"


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
        "outputs": ["WikiPacketHit"],
        "non_override_rules": [
            "Wiki packets cannot close user-level focus or plan.",
            "Wiki packets cannot override current_state for mutable user facts.",
            "Wiki packets are ignored when query overlap is zero.",
            "Every hit must carry source_path provenance.",
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
                "authority": "supporting_not_authoritative",
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
