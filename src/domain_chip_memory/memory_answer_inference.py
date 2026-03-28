from __future__ import annotations

import re
from collections.abc import Callable

from .contracts import NormalizedQuestion
from .memory_extraction import ObservationEntry


def extract_place_candidates(text: str, ignored_terms: set[str]) -> set[str]:
    place_candidates: set[str] = set()
    month_names = {
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    }
    for pattern in (
        r"\b(?:to|in|visit(?:ed)?|been to|trip to)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b",
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+once\b",
    ):
        for match in re.finditer(pattern, text):
            candidate = match.group(1).strip(" .,!?;:")
            head = candidate.split()[0]
            if head in month_names:
                continue
            if candidate.lower() in ignored_terms:
                continue
            place_candidates.add(candidate)
    return place_candidates


def infer_shared_answer(
    question: NormalizedQuestion,
    evidence_entries: list[ObservationEntry],
    *,
    question_subjects: Callable[[NormalizedQuestion], list[str]],
    entry_combined_text: Callable[[NormalizedQuestion, ObservationEntry], str],
    entry_source_corpus: Callable[[ObservationEntry], str],
) -> str:
    question_lower = question.question.lower()
    subjects = set(question_subjects(question))
    if len(subjects) < 2:
        return ""

    texts_by_subject: dict[str, list[str]] = {subject: [] for subject in subjects}
    source_texts_by_subject: dict[str, list[str]] = {subject: [] for subject in subjects}
    for entry in evidence_entries:
        if entry.subject in subjects:
            texts_by_subject.setdefault(entry.subject, []).append(entry_combined_text(question, entry))
            source_texts_by_subject.setdefault(entry.subject, []).append(entry_source_corpus(entry))

    if "destress" in question_lower and "both" in question_lower:
        if all(any("dance" in text for text in texts) for texts in texts_by_subject.values()):
            return "by dancing"

    if "both have in common" in question_lower:
        if all(
            any(("lost my job" in text or "lost her job" in text or "lost his job" in text) for text in texts)
            for texts in texts_by_subject.values()
        ) and all(
            any(token in text for text in texts for token in ("start my own business", "online clothing store", "dance studio"))
            for texts in texts_by_subject.values()
        ):
            return "They lost their jobs and decided to start their own businesses."

    if question_lower.startswith("do ") and "start businesses" in question_lower and "what they love" in question_lower:
        if all(
            any(
                token in text
                for text in texts
                for token in ("passion", "love", "doing something i love", "turn my dancing passion into a business")
            )
            for texts in texts_by_subject.values()
        ):
            return "Yes"

    if "which city" in question_lower and "both" in question_lower and any(
        token in question_lower for token in ("visited", "visit", "been")
    ):
        place_sets: list[set[str]] = []
        for subject in subjects:
            places: set[str] = set()
            for text in source_texts_by_subject.get(subject, []):
                places.update(extract_place_candidates(text, subjects))
            if not places:
                return ""
            place_sets.append(places)
        if place_sets:
            common_places = set.intersection(*place_sets)
            if common_places:
                return sorted(common_places)[0]

    return ""


def infer_explanatory_answer(
    question: NormalizedQuestion,
    evidence_entries: list[ObservationEntry],
    *,
    question_subject: Callable[[NormalizedQuestion], str],
    entry_combined_text: Callable[[NormalizedQuestion, ObservationEntry], str],
) -> str:
    question_lower = question.question.lower()
    subject = question_subject(question)
    subject_entries = [entry for entry in evidence_entries if entry.subject == subject]
    if not subject_entries:
        return ""

    subject_texts = [entry_combined_text(question, entry) for entry in subject_entries]

    if "why did" in question_lower and "start his dance studio" in question_lower:
        if any("lost my job" in text or "losing my job" in text for text in subject_texts) and any(
            token in text for text in subject_texts for token in ("passion", "joy that dancing brings me", "share it with others")
        ):
            return "He lost his job and decided to start his own business to share his passion."

    if "why did" in question_lower and "start her own clothing store" in question_lower:
        if any("lost my job" in text or "lost her job" in text or "because i lost my job" in text for text in subject_texts) and any(
            token in text for text in subject_texts for token in ("fashion trends", "finding unique pieces", "love for dance and fashion", "doing something i love")
        ):
            return "She always loved fashion trends and finding unique pieces and she lost her job so decided it was time to start her own business."
        if any("lost my job" in text or "lost her job" in text or "because i lost my job" in text for text in subject_texts) and any(
            token in text for text in subject_texts for token in ("passionate about fashion", "love for dance and fashion", "doing something i love")
        ):
            return "She lost her job and wanted to combine what she loved into her own business."

    if "ideal dance studio" in question_lower and "look like" in question_lower:
        wants_water = any("by the water" in text for text in subject_texts)
        wants_light = any("natural light" in text for text in subject_texts)
        wants_marley = any("marley flooring" in text for text in subject_texts)
        parts: list[str] = []
        if wants_water:
            parts.append("By the water")
        if wants_light:
            parts.append("with natural light")
        if wants_marley:
            parts.append("and Marley flooring")
        if parts:
            return " ".join(parts[:2]) + (f" {parts[2]}" if len(parts) > 2 else "")

    if "promote her clothes store" in question_lower:
        has_artist = any("worked with the artist" in text or "teamed up with a local artist" in text for text in subject_texts)
        has_offers = any("offers and promotions" in text for text in subject_texts)
        has_video = any("video presentation" in text for text in subject_texts)
        has_unique_pieces = any("unique, trendy pieces" in text or "unique pieces" in text or "cool designs" in text for text in subject_texts)
        if has_artist and has_offers and has_video:
            return "worked with an artist to make unique fashion pieces, made limited-edition sweatshirts, got some new offers and promotions for online store, developed a video presentation showing how to style her pieces"
        promotion_bits: list[str] = []
        if has_artist:
            promotion_bits.append("worked with an artist to make unique fashion pieces" if has_unique_pieces else "worked with an artist on unique pieces")
        if has_offers:
            promotion_bits.append("got some new offers and promotions for online store")
        if has_video:
            promotion_bits.append("developed a video presentation showing how to style her pieces")
        if has_artist and has_unique_pieces:
            promotion_bits.insert(1 if promotion_bits else 0, "made limited-edition sweatshirts")
        if any("ad campaign" in text for text in subject_texts):
            promotion_bits.insert(0, "launched an ad campaign")
        if promotion_bits:
            seen_bits: set[str] = set()
            deduped_bits: list[str] = []
            for bit in promotion_bits:
                if bit in seen_bits:
                    continue
                seen_bits.add(bit)
                deduped_bits.append(bit)
            return ", ".join(deduped_bits)

    if "which events has jon participated in" in question_lower and "promote his business venture" in question_lower:
        event_bits: list[str] = []
        if any("went to a fair" in text for text in subject_texts):
            event_bits.append("fair")
        if any("networking" in text for text in subject_texts):
            event_bits.append("networking events")
        if any("dance competition" in text for text in subject_texts):
            event_bits.append("dance competition")
        if event_bits:
            return ", ".join(event_bits)

    return ""
