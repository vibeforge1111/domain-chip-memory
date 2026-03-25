from __future__ import annotations

import re

from .contracts import AnswerCandidate, AnswerCandidateType


_CURRENCY_PATTERN = re.compile(r"^\$\d+(?:,\d{3})*(?:\.\d+)?$")
_NUMERIC_PATTERN = re.compile(r"^\d+(?:\.\d+)?$")
_DATE_PATTERN = re.compile(
    r"^(?:\d{1,2}\s+)?(?:january|february|march|april|may|june|july|august|september|october|november|december)"
    r"(?:\s+\d{1,2}(?:st|nd|rd|th)?)?(?:\s+\d{4})?$|^\d{4}$",
    re.IGNORECASE,
)
_PREFERENCE_MARKERS = (
    "recommend",
    "suggest",
    "advice",
    "tips",
    "ideas",
    "what should i",
    "what do you think",
    "could there be a reason",
)


def looks_like_current_state_question(question: str) -> bool:
    question_lower = question.lower()
    if any(marker in question_lower for marker in (" now?", " currently", "at the moment", "these days")):
        return True
    if "current " not in question_lower:
        return False
    mutable_state_tokens = (
        "live",
        "prefer",
        "role",
        "job",
        "city",
        "status",
        "routine",
        "project",
        "working",
        "doing",
        "using",
        "focus",
        "relationship",
    )
    return any(token in question_lower for token in mutable_state_tokens)


def infer_answer_candidate_type(question: str, answer_text: str) -> AnswerCandidateType:
    cleaned = answer_text.strip()
    cleaned_lower = cleaned.lower()
    question_lower = question.lower()

    if cleaned_lower == "unknown":
        return "abstain"
    if _CURRENCY_PATTERN.fullmatch(cleaned):
        return "currency"
    if _NUMERIC_PATTERN.fullmatch(cleaned):
        return "exact_numeric"
    if _DATE_PATTERN.fullmatch(cleaned) or question_lower.startswith("when "):
        return "date"
    if looks_like_current_state_question(question):
        return "current_state"
    if question_lower.startswith("where ") or " where " in question_lower:
        return "location"
    if any(marker in question_lower for marker in _PREFERENCE_MARKERS):
        return "preference"
    return "generic"


def build_answer_candidate(
    question: str,
    answer_text: str,
    *,
    source: str,
    metadata: dict[str, object] | None = None,
) -> AnswerCandidate:
    return AnswerCandidate(
        text=answer_text,
        candidate_type=infer_answer_candidate_type(question, answer_text),
        source=source,
        metadata=dict(metadata or {}),
    )
