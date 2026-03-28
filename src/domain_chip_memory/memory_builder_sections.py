from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .runs import RetrievedContextItem


def build_entry_metadata(
    entry: Any,
    *,
    include_topic_id: bool = False,
    include_media_fields: bool = False,
) -> dict[str, Any]:
    metadata = {
        "timestamp": getattr(entry, "timestamp", None),
        "predicate": getattr(entry, "predicate", None),
        "subject": getattr(entry, "subject", None),
    }
    entry_metadata = getattr(entry, "metadata", {})
    if include_topic_id:
        metadata["topic_id"] = entry_metadata.get("topic_id")
    if include_media_fields:
        for field_name in ("img_url", "blip_caption", "search_query"):
            if field_name in entry_metadata:
                metadata[field_name] = entry_metadata[field_name]
    return metadata


def append_retrieved_entries(
    context_blocks: list[str],
    retrieved_items: list[RetrievedContextItem],
    entries: list[Any],
    *,
    header: str | None,
    line_builder: Callable[[Any], str],
    score_builder: Callable[[Any], float],
    strategy: str,
    memory_role: str,
    metadata_builder: Callable[[Any], dict[str, Any]],
) -> None:
    if header is not None:
        context_blocks.append(header)
    for entry in entries:
        line = line_builder(entry)
        context_blocks.append(line)
        retrieved_items.append(
            RetrievedContextItem(
                session_id=entry.session_id,
                turn_ids=entry.turn_ids,
                score=score_builder(entry),
                strategy=strategy,
                text=line,
                memory_role=memory_role,
                metadata=metadata_builder(entry),
            )
        )
