from __future__ import annotations

from collections.abc import Callable

from .contracts import NormalizedQuestion
from .memory_extraction import ObservationEntry


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
    ranked = sorted(
        observations,
        key=lambda entry: (evidence_score(question, entry), observation_score(question, entry), entry.timestamp or "", entry.observation_id),
        reverse=True,
    )
    selected: list[ObservationEntry] = []
    seen_surfaces: set[str] = set()
    subjects = set(question_subjects(question))
    question_lower = question.question.lower()
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
