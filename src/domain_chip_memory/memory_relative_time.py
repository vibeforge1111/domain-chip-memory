from __future__ import annotations

import re
from datetime import datetime

from .memory_extraction import EventCalendarEntry, ObservationEntry, _normalize_value
from .memory_time import parse_observation_anchor


def parse_generic_relative_anchor_phrase(anchor_phrase: str) -> tuple[str | None, str | None]:
    normalized = anchor_phrase.strip().lower()
    valid_bases = {
        "that change",
        "that update",
        "that correction",
        "that move",
        "that relocation",
        "that deletion",
        "that removal",
        "that forget",
        "that one",
    }
    if normalized in valid_bases:
        return None, normalized
    match = re.match(r"^that\s+(earlier|later|first|last)\s+(.+)$", normalized)
    if not match:
        return None, None
    modifier = match.group(1)
    base_phrase = f"that {match.group(2).strip()}"
    if base_phrase not in valid_bases:
        return None, None
    return modifier, base_phrase


def generic_relative_anchor_candidates(
    base_phrase: str,
    target_predicates: list[str],
    candidate_entries: list[ObservationEntry | EventCalendarEntry],
) -> list[datetime]:
    def _unique_sorted_anchors(anchors: list[datetime]) -> list[datetime]:
        return sorted(set(anchors))

    deletion_phrases = {"that deletion", "that removal", "that forget"}
    if base_phrase in deletion_phrases:
        return _unique_sorted_anchors(
            [
                anchor
                for entry in candidate_entries
                if entry.predicate == "state_deletion"
                and str(entry.metadata.get("target_predicate", "")).strip() in target_predicates
                for anchor in [parse_observation_anchor(entry.timestamp or "")]
                if anchor is not None
            ]
        )

    if base_phrase == "that one":
        combined_anchors = [
            anchor
            for entry in candidate_entries
            if entry.predicate == "state_deletion"
            and str(entry.metadata.get("target_predicate", "")).strip() in target_predicates
            for anchor in [parse_observation_anchor(entry.timestamp or "")]
            if anchor is not None
        ]

    dated_state_markers = [
        (
            anchor,
            entry.predicate,
            _normalize_value(str(entry.metadata.get("value", "") or entry.text)),
        )
        for entry in sorted(
            [
                entry
                for entry in candidate_entries
                if entry.predicate in target_predicates and parse_observation_anchor(entry.timestamp or "")
            ],
            key=lambda entry: (
                parse_observation_anchor(entry.timestamp or ""),
                getattr(entry, "observation_id", getattr(entry, "event_id", "")),
            ),
        )
        for anchor in [parse_observation_anchor(entry.timestamp or "")]
        if anchor is not None
    ]
    unique_state_markers = list(dict.fromkeys(dated_state_markers))
    unique_state_anchors = [anchor for anchor, _, _ in unique_state_markers]
    if len(unique_state_anchors) <= 1:
        state_transition_anchors: list[datetime] = []
    else:
        state_transition_anchors = unique_state_anchors[1:]
    if base_phrase == "that one":
        return _unique_sorted_anchors(combined_anchors + state_transition_anchors)
    return _unique_sorted_anchors(state_transition_anchors)


def infer_generic_relative_anchor_time(
    anchor_phrase: str,
    target_predicates: list[str],
    candidate_entries: list[ObservationEntry | EventCalendarEntry],
) -> datetime | None:
    modifier, base_phrase = parse_generic_relative_anchor_phrase(anchor_phrase)
    location_only_phrases = {"that move", "that relocation"}
    if base_phrase is None:
        return None
    if base_phrase in location_only_phrases and "location" not in target_predicates:
        return None
    candidates = generic_relative_anchor_candidates(base_phrase, target_predicates, candidate_entries)
    if not candidates:
        return None
    if modifier in {"earlier", "first"}:
        return candidates[0]
    return candidates[-1]


def has_ambiguous_generic_relative_anchor(
    anchor_phrase: str,
    target_predicates: list[str],
    candidate_entries: list[ObservationEntry | EventCalendarEntry],
) -> bool:
    modifier, base_phrase = parse_generic_relative_anchor_phrase(anchor_phrase)
    generic_phrases = {"that change", "that update", "that correction"}
    location_only_phrases = {"that move", "that relocation"}
    deletion_phrases = {"that deletion", "that removal", "that forget"}
    if base_phrase in location_only_phrases and "location" not in target_predicates:
        return False
    if base_phrase is None:
        return False
    if base_phrase == "that one":
        state_candidates = generic_relative_anchor_candidates("that update", target_predicates, candidate_entries)
        deletion_candidates = generic_relative_anchor_candidates("that deletion", target_predicates, candidate_entries)
        if state_candidates and deletion_candidates:
            return True
        combined_candidates = generic_relative_anchor_candidates(base_phrase, target_predicates, candidate_entries)
        return len(combined_candidates) > 1
    candidates = generic_relative_anchor_candidates(base_phrase, target_predicates, candidate_entries)
    if modifier in {"earlier", "later"}:
        return len(candidates) > 2
    if modifier in {"first", "last"}:
        return False
    if base_phrase in generic_phrases.union(location_only_phrases):
        state_markers = {
            (
                parse_observation_anchor(entry.timestamp or ""),
                entry.predicate,
                _normalize_value(str(entry.metadata.get("value", "") or entry.text)),
            )
            for entry in candidate_entries
            if entry.predicate in target_predicates and parse_observation_anchor(entry.timestamp or "")
        }
        return len(state_markers) > 2
    if base_phrase in deletion_phrases:
        deletion_markers = {
            (
                parse_observation_anchor(entry.timestamp or ""),
                str(entry.metadata.get("target_predicate", "")).strip(),
            )
            for entry in candidate_entries
            if entry.predicate == "state_deletion"
            and str(entry.metadata.get("target_predicate", "")).strip() in target_predicates
            and parse_observation_anchor(entry.timestamp or "")
        }
        return len(deletion_markers) > 1
    return False
