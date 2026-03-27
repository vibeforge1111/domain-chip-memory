from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from .answer_candidates import looks_like_current_state_question
from .memory_updates import build_current_state_view, has_active_state_deletion

if TYPE_CHECKING:
    from .contracts import NormalizedQuestion
    from .memory_systems import ObservationEntry


def is_current_state_question(question: "NormalizedQuestion") -> bool:
    return looks_like_current_state_question(question.question)


def select_current_state_entries(
    question: "NormalizedQuestion",
    reflected: list["ObservationEntry"],
    *,
    limit: int = 2,
    score_entry: Callable[["ObservationEntry"], float] | None = None,
    preferred_predicates: set[str] | None = None,
) -> list["ObservationEntry"]:
    if not is_current_state_question(question):
        return []
    ranked = sorted(
        reflected,
        key=lambda entry: (
            score_entry(entry) if score_entry is not None else 0.0,
            entry.timestamp or "",
            entry.observation_id,
        ),
        reverse=True,
    )
    if preferred_predicates:
        preferred_entries = [entry for entry in ranked if entry.predicate in preferred_predicates]
        if not preferred_entries:
            return []
        ranked = preferred_entries
    seen_surfaces: set[str] = set()
    selected: list[ObservationEntry] = []
    for entry in ranked:
        if entry.predicate == "raw_turn":
            continue
        surface = entry.text.strip().lower()
        if not surface or surface in seen_surfaces:
            continue
        seen_surfaces.add(surface)
        selected.append(entry)
        if len(selected) >= limit:
            break
    return selected
