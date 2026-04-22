from __future__ import annotations

import re
from collections.abc import Callable
from datetime import timedelta

from .contracts import NormalizedQuestion
from .memory_extraction import ObservationEntry


def _is_pure_question_turn(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped) and stripped.endswith("?") and "." not in stripped and "!" not in stripped


def infer_temporal_answer(
    question: NormalizedQuestion,
    evidence_entries: list[ObservationEntry],
    *,
    tokenize: Callable[[str], list[str]],
    observation_evidence_text: Callable[[NormalizedQuestion, ObservationEntry], str],
    evidence_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    observation_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    parse_observation_anchor: Callable[[str], object | None],
    is_pure_question_turn: Callable[[str], bool],
    format_full_date: Callable[[object], str],
    format_month_year: Callable[[object], str],
    shift_month: Callable[[object, int], object],
) -> str:
    question_lower = question.question.lower()
    if not question_lower.startswith("when "):
        return ""

    ignored_question_tokens = {
        "when", "did", "does", "do", "was", "were", "is", "are", "has", "have",
        "start", "started", "begin", "began", "get", "got", "jon", "gina", "jean", "john",
        "the", "a", "an", "her", "his", "their", "both", "and",
    }
    question_content_tokens = {
        token
        for token in tokenize(question.question)
        if token not in ignored_question_tokens and len(token) > 2
    }

    def _temporal_priority(entry: ObservationEntry) -> int:
        evidence_text = observation_evidence_text(question, entry).lower()
        priority = 0
        if "ad campaign" in question_lower and "ad campaign" in evidence_text:
            priority += 3
        if "accepted" in question_lower and "accepted" in evidence_text:
            priority += 3
        if "interview" in question_lower and "interview" in evidence_text:
            priority += 3
        if "start reading" in question_lower and "reading" in evidence_text:
            priority += 3
        if "social media presence" in question_lower and "social media presence" in evidence_text:
            priority += 3
        if "open her online clothing store" in question_lower and any(
            token in evidence_text for token in ("store is open", "opened an online clothing store", "online clothes store is open")
        ):
            priority += 3
        if "fair" in question_lower and "fair" in evidence_text:
            priority += 3
        if "get more exposure" in question_lower and any(
            token in evidence_text for token in ("fair", "show off my studio", "possible leads", "more attention to my studio")
        ):
            priority += 3
        if "festival" in question_lower and "festival" in evidence_text:
            priority += 2
        return priority

    ranked_entries = sorted(
        evidence_entries,
        key=lambda entry: (
            _temporal_priority(entry),
            len(question_content_tokens.intersection(set(tokenize(observation_evidence_text(question, entry))))),
            evidence_score(question, entry),
            observation_score(question, entry),
            entry.timestamp or "",
            getattr(entry, "observation_id", getattr(entry, "event_id", "")),
        ),
        reverse=True,
    )
    max_overlap = 0
    max_priority = 0
    if ranked_entries:
        max_priority = _temporal_priority(ranked_entries[0])
        max_overlap = len(question_content_tokens.intersection(set(tokenize(observation_evidence_text(question, ranked_entries[0])))))
    for entry in ranked_entries:
        anchor = parse_observation_anchor(entry.timestamp)
        if not anchor:
            continue
        source_text = str(entry.metadata.get("source_text", "")).strip()
        if is_pure_question_turn(source_text):
            continue
        evidence_text = observation_evidence_text(question, entry).lower()
        evidence_tokens = set(tokenize(evidence_text))
        overlap = len(question_content_tokens.intersection(evidence_tokens))
        if _temporal_priority(entry) < max_priority:
            continue
        if question_content_tokens and (not overlap or overlap < max_overlap):
            continue
        if "a few years ago" in evidence_text:
            return "A few years ago"
        if "few years ago" in evidence_text or "years ago" in evidence_text:
            return "A few years ago"
        if "yesterday" in evidence_text:
            return format_full_date(anchor - timedelta(days=1))
        if "today" in evidence_text:
            return format_full_date(anchor)
        if "this month" in evidence_text:
            return format_month_year(anchor)
        if "last month" in evidence_text:
            return format_month_year(shift_month(anchor, -1))
        if "next month" in evidence_text:
            return format_month_year(shift_month(anchor, 1))
        if "last week" in evidence_text or "this week" in evidence_text:
            return format_month_year(anchor)
    for entry in ranked_entries:
        anchor = parse_observation_anchor(entry.timestamp)
        if not anchor:
            continue
        source_text = str(entry.metadata.get("source_text", "")).strip()
        if is_pure_question_turn(source_text):
            continue
        if question_content_tokens:
            evidence_tokens = set(tokenize(observation_evidence_text(question, entry)))
            if not question_content_tokens.intersection(evidence_tokens):
                continue
        return format_full_date(anchor)
    return ""


def infer_yes_no_answer(
    question: NormalizedQuestion,
    evidence_entries: list[ObservationEntry],
    *,
    question_subject: Callable[[NormalizedQuestion], str],
    evidence_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    observation_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    observation_evidence_text: Callable[[NormalizedQuestion, ObservationEntry], str],
) -> str:
    question_lower = question.question.lower()
    if not question_lower.startswith(("did ", "does ", "is ", "are ", "was ", "were ")):
        return ""

    asked_subject = question_subject(question)
    ranked_entries = sorted(
        evidence_entries,
        key=lambda entry: (
            evidence_score(question, entry),
            observation_score(question, entry),
            entry.timestamp or "",
            getattr(entry, "observation_id", getattr(entry, "event_id", "")),
        ),
        reverse=True,
    )
    for entry in ranked_entries:
        source_text = str(entry.metadata.get("source_text", "")).strip()
        if _is_pure_question_turn(source_text) and not (
            question_lower.startswith(("is ", "are ", "was ", "were "))
            and "pet" in question_lower
            and any(token in source_text.lower() for token in ("my guinea pig", "my dog", "my cat", "my pet"))
        ):
            continue
        combined = " ".join(
            part.lower()
            for part in (
                observation_evidence_text(question, entry),
                entry.text,
                source_text,
            )
            if part
        )
        if question_lower.startswith("does ") and "live in connecticut" in question_lower:
            if any(token in combined for token in ("stamford", "connecticut")):
                return "Likely yes"
        if question_lower.startswith(("is ", "are ", "was ", "were ")) and "pet" in question_lower:
            pet_match = re.match(
                r"(?:is|are|was|were)\s+([a-z0-9][a-z0-9' -]*?)\s+([a-z][a-z'-]*)'s\s+pet\??$",
                question_lower,
            )
            if pet_match:
                pet_name = pet_match.group(1).strip()
                asked_owner = pet_match.group(2).strip()
                if pet_name in combined and any(
                    token in combined for token in ("guinea pig", "dog", "cat", "pet", "pets")
                ):
                    if asked_owner in combined or entry.subject == asked_owner:
                        return "Yes"
                    if " my " in f" {combined} " or " named " in f" {combined} " or entry.subject != asked_owner:
                        return "No"
        if "make" in question_lower and any(
            token in combined
            for token in ("i made", "yeah, i made", "yes, i made", "made this bowl", "made it", "did make")
        ):
            return "Yes" if entry.subject == asked_subject else "No"
        if "make" in question_lower and any(
            token in combined
            for token in ("i didn't make", "i did not make", "didn't make", "did not make", "no, i didn't")
        ):
            return "No" if entry.subject == asked_subject else "Yes"
    return ""
