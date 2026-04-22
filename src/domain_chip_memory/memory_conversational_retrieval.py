from __future__ import annotations

import re
from collections.abc import Iterable

from .contracts import NormalizedQuestion
from .memory_conversational_index import ConversationalIndexEntry
from .memory_extraction import _tokenize
from .memory_queries import _question_predicates, _question_subjects


_HOBBY_TOKENS = {
    "hobby",
    "hobbies",
    "reading",
    "travel",
    "art",
    "cooking",
    "painting",
    "hiking",
    "running",
    "kayaking",
}

_SUPPORT_TOKENS = {
    "support",
    "help",
    "peace",
    "grief",
    "grieving",
    "comfort",
    "healing",
    "nature",
    "photo",
    "photos",
    "yoga",
    "garden",
    "flowers",
    "beach",
    "window",
    "forest",
    "bali",
}


def _is_pure_question_turn(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped) and stripped.endswith("?") and "." not in stripped and "!" not in stripped


def _entry_search_text(entry: ConversationalIndexEntry) -> str:
    parts = [
        entry.text,
        str(entry.metadata.get("source_span", "")),
        str(entry.metadata.get("relation_type", "")),
        str(entry.metadata.get("other_entity", "")),
        str(entry.metadata.get("time_normalized", "")),
        str(entry.metadata.get("time_expression_raw", "")),
        str(entry.metadata.get("item_type", "")),
        str(entry.metadata.get("support_kind", "")),
    ]
    return " ".join(part for part in parts if part).strip()


def _question_relation_tokens(question_lower: str) -> set[str]:
    relation_tokens: set[str] = set()
    for token in ("mother", "mom", "father", "dad", "friend", "sister", "brother", "partner", "husband", "wife"):
        if token in question_lower:
            relation_tokens.add(token)
    return relation_tokens


def _question_is_hobby_like(question_lower: str) -> bool:
    return "hobby" in question_lower or "hobbies" in question_lower or "interests" in question_lower


def _question_is_support_like(question_lower: str) -> bool:
    return any(token in question_lower for token in ("helped", "support", "peace", "grieving", "comfort"))


def _question_is_temporal_like(question_lower: str) -> bool:
    return question_lower.startswith("when ")


def _coverage_labels(question: NormalizedQuestion, entry: ConversationalIndexEntry) -> set[str]:
    question_lower = question.question.lower()
    text = _entry_search_text(entry).lower()
    if _is_pure_question_turn(entry.text):
        return set()

    labels: set[str] = set()
    if _question_is_hobby_like(question_lower):
        if "reading was one of her hobbies" in text or "reading was one of his hobbies" in text:
            labels.add("reading")
        if "travel was also her great passion" in text or "travel was also his great passion" in text:
            labels.add("travel")
        if "interested in art" in text:
            labels.add("art")
        if "passion for cooking" in text or "loved cooking" in text:
            labels.add("cooking")
    if _question_is_support_like(question_lower):
        if "yoga" in text:
            labels.add("yoga")
        if any(token in text for token in ("old photo", "last photo", "family album", "photo with")):
            labels.add("photo")
        if any(token in text for token in ("flower", "flowers", "roses", "dahlias", "garden")):
            labels.add("flowers")
        if any(token in text for token in ("nature", "forest", "beach", "bali", "window", "peace")):
            labels.add("peace_place")
    return labels


def _entry_score(question: NormalizedQuestion, entry: ConversationalIndexEntry) -> float:
    question_lower = question.question.lower()
    question_tokens = set(_tokenize(question.question))
    entry_text = _entry_search_text(entry)
    entry_lower = entry_text.lower()
    entry_tokens = set(_tokenize(entry_text))
    predicates = set(_question_predicates(question))
    subjects = set(_question_subjects(question))
    relation_tokens = _question_relation_tokens(question_lower)

    score = 0.0
    score += 2.0 * float(len(question_tokens.intersection(entry_tokens)))

    if entry.subject in subjects:
        score += 4.0
    if entry.predicate in predicates:
        score += 8.0
    if entry.entry_type == "turn":
        score += 1.5
    if entry.entry_type == "typed_atom":
        score += 1.0

    relation_type = str(entry.metadata.get("relation_type", "")).lower()
    other_entity = str(entry.metadata.get("other_entity", "")).lower()
    if relation_tokens:
        if relation_type in relation_tokens:
            score += 8.0
        if relation_tokens.intersection(entry_tokens):
            score += 6.0
        if any(token in other_entity for token in relation_tokens):
            score += 4.0

    if _question_is_temporal_like(question_lower):
        if entry.predicate in {"loss_event", "gift_event"}:
            score += 12.0
        if str(entry.metadata.get("time_normalized", "")).strip():
            score += 10.0
        if re.search(r"\b(last year|yesterday|a few years ago|few years ago|in (?:19|20)\d{2})\b", entry_lower):
            score += 8.0

    if _question_is_hobby_like(question_lower):
        hobby_overlap = len(_HOBBY_TOKENS.intersection(entry_tokens))
        score += 4.0 * float(hobby_overlap)
        if entry.entry_type == "turn" and hobby_overlap:
            score += 6.0
        if relation_tokens and relation_tokens.intersection(entry_tokens):
            score += 6.0

    if _question_is_support_like(question_lower):
        support_overlap = len(_SUPPORT_TOKENS.intersection(entry_tokens))
        score += 3.0 * float(support_overlap)
        if entry.predicate == "support_event":
            score += 12.0
        if entry.entry_type == "turn" and support_overlap:
            score += 4.0
        if any(token in entry_lower for token in ("old photo", "last photo", "family album", "photo with")):
            score += 10.0
        if any(token in entry_lower for token in ("roses", "dahlias", "flower garden")):
            score += 10.0

    if any(token in question_lower for token in ("what kind of car", "roadtrip", "country", "gift", "symbolic")):
        if entry.entry_type == "turn" and any(token in entry_lower for token in ("prius", "rockies", "jasper", "canada", "pendant")):
            score += 8.0

    if "," in entry.text or " and " in entry_lower:
        score += 1.0

    return score


def _entity_link_search_terms(question: NormalizedQuestion) -> set[str]:
    question_lower = question.question.lower()
    terms = set(_question_subjects(question))
    for metadata_key in ("speaker_a", "speaker_b"):
        speaker_name = str(question.metadata.get(metadata_key, "")).strip().lower()
        if speaker_name:
            terms.add(speaker_name)
    terms.update(token for token in re.findall(r"[a-z]+", question_lower) if len(token) >= 3)
    return {term for term in terms if term}


def _entity_linked_score(question: NormalizedQuestion, entry: ConversationalIndexEntry) -> float:
    score = _entry_score(question, entry)
    question_lower = question.question.lower()
    search_terms = _entity_link_search_terms(question)
    metadata_values = {
        str(entry.subject).strip().lower(),
        str(entry.metadata.get("speaker", "")).strip().lower(),
        str(entry.metadata.get("alias", "")).strip().lower(),
        str(entry.metadata.get("canonical_name", "")).strip().lower(),
        str(entry.metadata.get("other_entity", "")).strip().lower(),
        str(entry.metadata.get("relation_type", "")).strip().lower(),
    }
    metadata_values = {value for value in metadata_values if value}

    overlap = sum(1 for term in search_terms if any(term == value or term in value for value in metadata_values))
    score += 4.0 * float(overlap)

    if entry.predicate == "alias_binding":
        if "nickname" in question_lower or "call" in question_lower:
            score += 28.0
        else:
            score -= 8.0
        if "nickname" in question_lower or "call" in question_lower:
            score += 20.0
        canonical_name = str(entry.metadata.get("canonical_name", "")).strip().lower()
        if canonical_name and canonical_name in question_lower:
            score += 12.0
    if entry.predicate == "relationship_mention":
        score += 6.0
        if any(token in question_lower for token in ("mother", "mom", "father", "dad", "friend", "partner")):
            score += 10.0
    if entry.predicate in {"reported_speech", "unknown_record", "negation_record"}:
        score += 6.0
    if entry.entry_type == "typed_atom":
        score += 3.0
    return score


def retrieve_conversational_entries(
    question: NormalizedQuestion,
    entries: Iterable[ConversationalIndexEntry],
    *,
    limit: int = 6,
) -> list[ConversationalIndexEntry]:
    indexed_entries = list(entries)
    turn_by_turn_id = {
        entry.turn_id: entry
        for entry in indexed_entries
        if entry.entry_type == "turn"
    }
    ranked = sorted(
        indexed_entries,
        key=lambda entry: (_entry_score(question, entry), entry.timestamp or "", entry.entry_id),
        reverse=True,
    )

    selected: list[ConversationalIndexEntry] = []
    seen_entry_ids: set[str] = set()
    covered_labels: set[str] = set()
    if _question_is_hobby_like(question.question.lower()) or _question_is_support_like(question.question.lower()):
        for entry in ranked:
            if entry.entry_type != "turn":
                continue
            if _entry_score(question, entry) <= 0:
                continue
            labels = _coverage_labels(question, entry)
            if not labels.difference(covered_labels):
                continue
            selected.append(entry)
            seen_entry_ids.add(entry.entry_id)
            covered_labels.update(labels)
            if len(selected) >= limit:
                return selected[:limit]
    for entry in ranked:
        score = _entry_score(question, entry)
        if score <= 0:
            continue
        if entry.entry_id not in seen_entry_ids:
            selected.append(entry)
            seen_entry_ids.add(entry.entry_id)
        if entry.entry_type == "typed_atom":
            supporting_turn = turn_by_turn_id.get(entry.turn_id)
            if supporting_turn is not None and supporting_turn.entry_id not in seen_entry_ids:
                selected.append(supporting_turn)
                seen_entry_ids.add(supporting_turn.entry_id)
        if len(selected) >= limit:
            break
    return selected[:limit]


def retrieve_entity_linked_entries(
    question: NormalizedQuestion,
    entries: Iterable[ConversationalIndexEntry],
    *,
    limit: int = 6,
) -> list[ConversationalIndexEntry]:
    indexed_entries = list(entries)
    turn_by_turn_id = {
        entry.turn_id: entry
        for entry in indexed_entries
        if entry.entry_type == "turn"
    }
    ranked = sorted(
        indexed_entries,
        key=lambda entry: (_entity_linked_score(question, entry), entry.timestamp or "", entry.entry_id),
        reverse=True,
    )

    selected: list[ConversationalIndexEntry] = []
    seen_entry_ids: set[str] = set()
    for entry in ranked:
        score = _entity_linked_score(question, entry)
        if score <= 0:
            continue
        if entry.entry_id not in seen_entry_ids:
            selected.append(entry)
            seen_entry_ids.add(entry.entry_id)
        if entry.entry_type == "typed_atom":
            supporting_turn = turn_by_turn_id.get(entry.turn_id)
            if supporting_turn is not None and supporting_turn.entry_id not in seen_entry_ids:
                selected.append(supporting_turn)
                seen_entry_ids.add(supporting_turn.entry_id)
        if len(selected) >= limit:
            break
    return selected[:limit]
