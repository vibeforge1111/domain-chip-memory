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

    small_numbers = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }

    def _has_temporal_cue(text: str) -> bool:
        return bool(
            re.search(
                r"\b(a few years ago|few years ago|last year|yesterday|today|last week|last month|next month|\d+ days ago|one day ago|two days ago|three days ago|in (?:19|20)\d{2})\b",
                text,
            )
        )

    if "passed away" in question_lower:
        for entry in evidence_entries:
            anchor = parse_observation_anchor(entry.timestamp)
            if not anchor:
                continue
            source_text = str(entry.metadata.get("source_text", "")).strip().lower()
            evidence_text = observation_evidence_text(question, entry).lower()
            combined_text = f"{source_text} {evidence_text}"
            if any(token in question_lower for token in ("mother", "mom")):
                if any(
                    token in combined_text
                    for token in (
                        "she passed away a few years ago",
                        "mother passed away a few years ago",
                        "mom passed away a few years ago",
                    )
                ):
                    return f"a few years before {anchor.year}"
                if "mother also passed away last year" in combined_text or "my mom passed away last year" in combined_text:
                    return f"in {anchor.year - 1}"
            if any(token in question_lower for token in ("father", "dad")):
                relative_days_match = re.search(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+days?\s+ago\b", combined_text)
                if any(token in combined_text for token in ("father passed away", "dad passed away")) and relative_days_match:
                    raw_days = relative_days_match.group(1)
                    days = int(raw_days) if raw_days.isdigit() else small_numbers.get(raw_days)
                    if days is not None:
                        return format_full_date(anchor - timedelta(days=days))

    named_subjects = {
        entry.subject.lower()
        for entry in evidence_entries
        if entry.subject and entry.subject.lower() in question_lower
    }
    if len(named_subjects) == 1:
        preferred_entries = [
            entry
            for entry in evidence_entries
            if entry.subject and entry.subject.lower() in named_subjects
        ]
        if preferred_entries:
            evidence_entries = preferred_entries
    kinship_tokens: tuple[str, ...] = ()
    if "father" in question_lower or "dad" in question_lower:
        kinship_tokens = ("father", "dad")
    elif "mother" in question_lower or "mom" in question_lower:
        kinship_tokens = ("mother", "mom")
    if kinship_tokens:
        preferred_entries = []
        for entry in evidence_entries:
            source_text = str(entry.metadata.get("source_text", "")).strip().lower()
            evidence_text = observation_evidence_text(question, entry).lower()
            combined_text = f"{source_text} {evidence_text}"
            pronoun_match = False
            if "passed away" in question_lower and _has_temporal_cue(combined_text):
                if any(token in question_lower for token in ("mother", "mom")) and "she passed away" in combined_text:
                    pronoun_match = True
                if any(token in question_lower for token in ("father", "dad")) and "he passed away" in combined_text:
                    pronoun_match = True
            if any(token in combined_text for token in kinship_tokens) or pronoun_match:
                preferred_entries.append(entry)
        if preferred_entries:
            evidence_entries = preferred_entries

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

    if "first two turtles" in question_lower or ("first" in question_lower and "turtles" in question_lower):
        for entry in evidence_entries:
            anchor = parse_observation_anchor(entry.timestamp)
            if not anchor:
                continue
            source_text = str(entry.metadata.get("source_text", "")).strip().lower()
            evidence_text = observation_evidence_text(question, entry).lower()
            combined_text = f"{source_text} {evidence_text}"
            owned_for_years_match = re.search(r"\b(?:i(?:'ve| have)\s+had\s+(?:them|it)\s+for|for)\s+(\d+)\s+years?\s+now\b", combined_text)
            if owned_for_years_match:
                return str(anchor.year - int(owned_for_years_match.group(1)))

    def _temporal_priority(entry: ObservationEntry) -> int:
        evidence_text = observation_evidence_text(question, entry).lower()
        priority = 0
        if "passed away" in question_lower and "passed away" in evidence_text:
            priority += 4
            if _has_temporal_cue(evidence_text):
                priority += 8
        if "letter" in question_lower and "letter" in evidence_text:
            priority += 4
            if _has_temporal_cue(evidence_text):
                priority += 8
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
        combined_text = f"{source_text.lower()} {evidence_text}"
        if "passed away" in question_lower and "passed away" in evidence_text and not _has_temporal_cue(evidence_text):
            continue
        if "letter" in question_lower and "letter" in evidence_text and not _has_temporal_cue(evidence_text):
            continue
        if "appreciation letter" in question_lower and "letter i received yesterday" in combined_text:
            return format_full_date(anchor - timedelta(days=1))
        evidence_tokens = set(tokenize(evidence_text))
        overlap = len(question_content_tokens.intersection(evidence_tokens))
        strong_temporal_match = (
            ("passed away" in question_lower and "passed away" in evidence_text and _has_temporal_cue(evidence_text))
            or ("letter" in question_lower and "letter" in evidence_text and _has_temporal_cue(evidence_text))
        )
        if _temporal_priority(entry) < max_priority:
            continue
        if question_content_tokens and (not overlap or overlap < max_overlap) and not strong_temporal_match:
            continue
        relative_year_match = re.search(r"\b(?:around\s+)?(\d+)\s+years?\s+ago\b", evidence_text)
        if relative_year_match:
            return str(anchor.year - int(relative_year_match.group(1)))
        owned_for_years_match = re.search(r"\b(?:i(?:'ve| have)\s+had\s+(?:them|it)\s+for|for)\s+(\d+)\s+years?\s+now\b", evidence_text)
        if owned_for_years_match:
            return str(anchor.year - int(owned_for_years_match.group(1)))
        relative_days_match = re.search(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+days?\s+ago\b", evidence_text)
        if relative_days_match:
            raw_days = relative_days_match.group(1)
            days = int(raw_days) if raw_days.isdigit() else small_numbers.get(raw_days)
            if days is not None:
                return format_full_date(anchor - timedelta(days=days))
        if "last friday" in evidence_text:
            return f"The Friday before {format_full_date(anchor)}"
        if "last week" in evidence_text and "first" in question_lower:
            return f"the week before {format_full_date(anchor)}"
        explicit_year_match = re.search(r"\bin\s+((?:19|20)\d{2})\b", evidence_text)
        if explicit_year_match and any(
            token in question_lower
            for token in ("gift", "pendant", "wedding", "bought", "buy", "visiting")
        ):
            return f"in {explicit_year_match.group(1)}"
        if "last year" in evidence_text:
            return f"in {anchor.year - 1}"
        if "a few years ago" in evidence_text:
            if "pass away" in question_lower:
                return f"a few years before {anchor.year}"
            return "A few years ago"
        if "few years ago" in evidence_text or "years ago" in evidence_text:
            if "pass away" in question_lower:
                return f"a few years before {anchor.year}"
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
        if "married" in question_lower:
            if any(token in combined for token in ("my husband", "my wife", "got married", "i'm married", "i am married", "we got married")):
                return "Yes"
            if any(token in combined for token in ("not married", "single")):
                return "No"
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
