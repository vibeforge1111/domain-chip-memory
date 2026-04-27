from __future__ import annotations

from collections.abc import Callable
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .contracts import NormalizedQuestion
    from .memory_extraction import ObservationEntry


def observation_id_sort_key(observation_id: str | None) -> tuple[tuple[int, Any], ...]:
    parts = re.split(r"(\d+)", str(observation_id or ""))
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part)
        for part in parts
        if part != ""
    )


def entry_sort_key(observation: "ObservationEntry") -> tuple[str, tuple[Any, ...]]:
    return observation.timestamp or "", observation_id_sort_key(observation.observation_id)


def state_deletion_target(observation: "ObservationEntry") -> str:
    if observation.predicate != "state_deletion":
        return ""
    return str(observation.metadata.get("target_predicate", "")).strip()


def active_state_entity_key(observation: "ObservationEntry", *, predicate: str | None = None) -> str:
    resolved_predicate = str(predicate or observation.predicate or "").strip()
    if resolved_predicate.startswith("profile.current_"):
        return resolved_predicate
    return str(observation.metadata.get("entity_key", "")).strip()


def build_current_state_view(observations: list["ObservationEntry"]) -> list["ObservationEntry"]:
    latest_by_key: dict[tuple[str, str, str], ObservationEntry] = {}
    deleted_after_by_predicate: dict[tuple[str, str], tuple[str, str]] = {}
    deleted_after_by_key: dict[tuple[str, str, str], tuple[str, str]] = {}
    passthrough: list[ObservationEntry] = []
    for observation in sorted(observations, key=entry_sort_key):
        if observation.predicate == "raw_turn":
            passthrough.append(observation)
            continue
        deletion_target = state_deletion_target(observation)
        if deletion_target:
            deletion_key = (
                active_state_entity_key(observation, predicate=deletion_target)
                if deletion_target.startswith("entity.") or deletion_target.startswith("profile.current_")
                else ""
            )
            if deletion_key:
                deleted_after_by_key[(observation.subject, deletion_target, deletion_key)] = entry_sort_key(observation)
            else:
                deleted_after_by_predicate[(observation.subject, deletion_target)] = entry_sort_key(observation)
            for key, current in list(latest_by_key.items()):
                if (
                    key[:2] == (observation.subject, deletion_target)
                    and (not deletion_key or key[2] == deletion_key)
                    and entry_sort_key(current) <= entry_sort_key(observation)
                ):
                    del latest_by_key[key]
            continue
        key = (
            observation.subject,
            observation.predicate,
            active_state_entity_key(observation),
        )
        deleted_after = deleted_after_by_key.get(key) or deleted_after_by_predicate.get((observation.subject, observation.predicate))
        if deleted_after is not None and entry_sort_key(observation) <= deleted_after:
            continue
        current = latest_by_key.get(key)
        if current is None or entry_sort_key(observation) >= entry_sort_key(current):
            latest_by_key[key] = observation
    return sorted(
        [*latest_by_key.values(), *passthrough],
        key=entry_sort_key,
    )


def has_active_state_deletion(
    observations: list["ObservationEntry"],
    *,
    subject: str,
    predicate: str,
    entity_key: str | None = None,
) -> bool:
    deleted = False
    for observation in sorted(observations, key=entry_sort_key):
        if observation.subject != subject:
            continue
        if state_deletion_target(observation) == predicate and (
            not entity_key or active_state_entity_key(observation, predicate=predicate) == entity_key
        ):
            deleted = True
            continue
        if observation.predicate == predicate and (
            not entity_key or active_state_entity_key(observation, predicate=predicate) == entity_key
        ):
            deleted = False
    return deleted


def has_active_current_state_deletion(
    question: "NormalizedQuestion",
    observations: list["ObservationEntry"],
    *,
    is_current_state_question: Callable[["NormalizedQuestion"], bool],
    question_subjects: Callable[["NormalizedQuestion"], list[str]],
    question_predicates: Callable[["NormalizedQuestion"], list[str]],
) -> bool:
    if not is_current_state_question(question):
        return False
    predicates = set(question_predicates(question))
    if not predicates:
        return False
    return any(
        has_active_state_deletion(observations, subject=subject, predicate=predicate)
        for subject in question_subjects(question)
        for predicate in predicates
    )
