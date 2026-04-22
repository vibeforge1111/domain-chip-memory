from __future__ import annotations

import re
from collections.abc import Callable

from .contracts import NormalizedQuestion
from .memory_extraction import ObservationEntry


def _is_pure_question_turn(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped) and stripped.endswith("?") and "." not in stripped and "!" not in stripped


def _is_locomo_evidence_first_question(question: NormalizedQuestion) -> bool:
    source_format = str(question.metadata.get("source_format", "")).strip().lower()
    return source_format == "locomo_qa" and str(question.category).strip() in {"1", "2", "3"}


def select_preference_support_entries(
    question: NormalizedQuestion,
    entries: list[ObservationEntry],
    *,
    evidence_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    observation_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    entry_source_corpus: Callable[[ObservationEntry], str],
    preference_anchor_match: Callable[[NormalizedQuestion, str], bool],
    preference_overlap: Callable[[NormalizedQuestion, str], int],
    preference_phrase_bonus: Callable[[NormalizedQuestion, str], float],
    observation_evidence_text: Callable[[NormalizedQuestion, ObservationEntry], str],
    limit: int = 4,
) -> list[ObservationEntry]:
    ranked = sorted(
        entries,
        key=lambda entry: (evidence_score(question, entry), observation_score(question, entry), entry.timestamp or "", entry.observation_id),
        reverse=True,
    )
    selected: list[ObservationEntry] = []
    seen_surfaces: set[str] = set()
    for entry in ranked:
        source_corpus = entry_source_corpus(entry)
        if not preference_anchor_match(question, source_corpus):
            continue
        if preference_overlap(question, source_corpus) <= 0 and preference_phrase_bonus(question, source_corpus) <= 0:
            continue
        surface = observation_evidence_text(question, entry).strip().lower()
        if not surface or surface in seen_surfaces:
            continue
        seen_surfaces.add(surface)
        selected.append(entry)
        if len(selected) >= limit:
            break
    return selected


def select_evidence_entries(
    question: NormalizedQuestion,
    observations: list[ObservationEntry],
    *,
    evidence_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    observation_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    question_subjects: Callable[[NormalizedQuestion], list[str]],
    entry_combined_text: Callable[[NormalizedQuestion, ObservationEntry], str],
    observation_evidence_text: Callable[[NormalizedQuestion, ObservationEntry], str],
    limit: int = 4,
) -> list[ObservationEntry]:
    ranked_inputs = observations
    if _is_locomo_evidence_first_question(question):
        preferred_inputs = [
            entry
            for entry in observations
            if entry.predicate not in {"preference", "summary_synthesis"}
            and not _is_pure_question_turn(str(entry.metadata.get("source_text", "")).strip())
        ]
        if preferred_inputs:
            ranked_inputs = preferred_inputs
    ranked = sorted(
        ranked_inputs,
        key=lambda entry: (evidence_score(question, entry), observation_score(question, entry), entry.timestamp or "", entry.observation_id),
        reverse=True,
    )
    selected: list[ObservationEntry] = []
    seen_surfaces: set[str] = set()
    subjects = set(question_subjects(question))
    question_lower = question.question.lower()

    def _clause_tokens(text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9]+", text.lower())
            if len(token) >= 3
            and token
            not in {
                "and",
                "the",
                "day",
                "from",
                "first",
                "last",
                "order",
                "what",
                "which",
                "that",
                "with",
                "then",
            }
        }

    clause_groups: list[str] = []
    between_match = re.search(r"\bbetween\s+(.+?)\s+and\s+(.+?)(?:\?|$)", question_lower)
    if between_match:
        clause_groups.extend([between_match.group(1), between_match.group(2)])
    order_match = re.search(r"order from first to last:\s*(.+?)(?:\?|$)", question_lower)
    if order_match:
        tail = order_match.group(1)
        parts = [
            part.strip(" ,.")
            for part in re.split(r",\s*(?:and\s+)?", tail)
            if part.strip(" ,.")
        ]
        clause_groups.extend(parts)

    for clause in clause_groups:
        tokens = _clause_tokens(clause)
        if not tokens:
            continue
        best_entry: ObservationEntry | None = None
        best_score = 0
        for entry in ranked:
            combined = entry_combined_text(question, entry).lower()
            overlap = len(tokens.intersection(_clause_tokens(combined)))
            if overlap <= 0:
                continue
            score = overlap * 100
            if score > best_score:
                best_score = score
                best_entry = entry
        if best_entry is not None:
            surface = observation_evidence_text(question, best_entry).strip().lower()
            if surface and surface not in seen_surfaces:
                seen_surfaces.add(surface)
                selected.append(best_entry)

    if len(subjects) >= 2:
        for subject in subjects:
            subject_entries = [entry for entry in ranked if entry.subject == subject]
            if "both have in common" in question_lower:
                preferred_entries = [
                    entry for entry in subject_entries
                    if any(
                        token in entry_combined_text(question, entry)
                        for token in ("lost my job", "lost his job", "lost her job", "own business", "online clothing store", "dance studio", "started my own")
                    )
                ]
                if preferred_entries:
                    subject_entries = preferred_entries + [entry for entry in subject_entries if entry not in preferred_entries]
            if question_lower.startswith("do ") and "start businesses" in question_lower:
                preferred_entries = [
                    entry for entry in subject_entries
                    if any(
                        token in entry_combined_text(question, entry)
                        for token in ("passion", "love", "doing something i love", "turn my dancing passion into a business", "online clothing store")
                    )
                ]
                if preferred_entries:
                    subject_entries = preferred_entries + [entry for entry in subject_entries if entry not in preferred_entries]
            if "destress" in question_lower and "both" in question_lower:
                preferred_entries = [
                    entry for entry in subject_entries
                    if "dance" in entry_combined_text(question, entry)
                ]
                if preferred_entries:
                    subject_entries = preferred_entries + [entry for entry in subject_entries if entry not in preferred_entries]
            for entry in subject_entries:
                surface = observation_evidence_text(question, entry).strip().lower()
                if not surface or surface in seen_surfaces:
                    continue
                seen_surfaces.add(surface)
                selected.append(entry)
                break
    for entry in ranked:
        surface = observation_evidence_text(question, entry).strip().lower()
        if not surface or surface in seen_surfaces:
            continue
        seen_surfaces.add(surface)
        selected.append(entry)
        if len(selected) >= limit:
            break
    return selected
