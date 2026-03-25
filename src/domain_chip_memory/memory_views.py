from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from .answer_candidates import looks_like_current_state_question

if TYPE_CHECKING:
    from .contracts import NormalizedQuestion
    from .memory_systems import ObservationEntry


def is_current_state_question(question: "NormalizedQuestion") -> bool:
    return looks_like_current_state_question(question.question)


def build_current_state_view(observations: list["ObservationEntry"]) -> list["ObservationEntry"]:
    latest_by_key: dict[tuple[str, str, str], ObservationEntry] = {}
    passthrough: list[ObservationEntry] = []
    for observation in observations:
        if observation.predicate == "raw_turn":
            passthrough.append(observation)
            continue
        key = (
            observation.subject,
            observation.predicate,
            str(observation.metadata.get("entity_key", "")),
        )
        current = latest_by_key.get(key)
        if current is None or (observation.timestamp or "") >= (current.timestamp or ""):
            latest_by_key[key] = observation
    return sorted(
        [*latest_by_key.values(), *passthrough],
        key=lambda entry: (entry.timestamp or "", entry.observation_id),
    )


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
