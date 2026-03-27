from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .contracts import NormalizedQuestion
    from .memory_systems import ObservationEntry


def entry_sort_key(observation: "ObservationEntry") -> tuple[str, str]:
    return observation.timestamp or "", observation.observation_id


def state_deletion_target(observation: "ObservationEntry") -> str:
    if observation.predicate != "state_deletion":
        return ""
    return str(observation.metadata.get("target_predicate", "")).strip()


def build_current_state_view(observations: list["ObservationEntry"]) -> list["ObservationEntry"]:
    latest_by_key: dict[tuple[str, str, str], ObservationEntry] = {}
    deleted_after_by_predicate: dict[tuple[str, str], tuple[str, str]] = {}
    passthrough: list[ObservationEntry] = []
    for observation in sorted(observations, key=entry_sort_key):
        if observation.predicate == "raw_turn":
            passthrough.append(observation)
            continue
        deletion_target = state_deletion_target(observation)
        if deletion_target:
            deleted_after_by_predicate[(observation.subject, deletion_target)] = entry_sort_key(observation)
            for key, current in list(latest_by_key.items()):
                if key[:2] == (observation.subject, deletion_target) and entry_sort_key(current) <= entry_sort_key(observation):
                    del latest_by_key[key]
            continue
        deleted_after = deleted_after_by_predicate.get((observation.subject, observation.predicate))
        if deleted_after is not None and entry_sort_key(observation) <= deleted_after:
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


def has_active_state_deletion(
    observations: list["ObservationEntry"],
    *,
    subject: str,
    predicate: str,
) -> bool:
    deleted = False
    for observation in sorted(observations, key=entry_sort_key):
        if observation.subject != subject:
            continue
        if state_deletion_target(observation) == predicate:
            deleted = True
            continue
        if observation.predicate == predicate:
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
