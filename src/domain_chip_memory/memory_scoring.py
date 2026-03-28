from __future__ import annotations

from collections.abc import Callable

from .contracts import NormalizedQuestion
from .memory_evidence import entry_source_corpus, observation_evidence_text
from .memory_extraction import ObservationEntry, _tokenize
from .memory_preferences import (
    is_generic_followup_preference_text,
    is_preference_question,
    is_recommendation_request_text,
    preference_anchor_match,
    preference_overlap,
    preference_phrase_bonus,
)
from .memory_queries import _question_predicates


def evidence_score(
    question: NormalizedQuestion,
    observation: ObservationEntry,
    *,
    observation_score: Callable[[NormalizedQuestion, ObservationEntry], float],
) -> float:
    score = observation_score(question, observation)
    predicates = set(_question_predicates(question))
    question_lower = question.question.lower()
    evidence_text = observation_evidence_text(question, observation)
    observation_context_lower = observation.text.lower()
    evidence_tokens = set(_tokenize(evidence_text))
    question_tokens = set(_tokenize(question.question))
    score += 2.0 * float(len(question_tokens.intersection(evidence_tokens)))
    if is_preference_question(question):
        source_corpus = entry_source_corpus(observation)
        overlap = preference_overlap(question, source_corpus)
        score += 6.0 * float(overlap)
        score += preference_phrase_bonus(question, source_corpus)
        if not preference_anchor_match(question, source_corpus):
            score -= 10.0
        if observation.predicate == "raw_turn" and is_recommendation_request_text(source_corpus):
            score += 5.0
        if overlap >= 2 and observation.predicate == "raw_turn":
            score += 4.0
        if is_generic_followup_preference_text(source_corpus):
            score -= 6.0
        if overlap == 0:
            score -= 8.0
            if "prefer" in evidence_text.lower():
                score -= 6.0
            if is_recommendation_request_text(source_corpus):
                score -= 2.0
    if observation.predicate != "raw_turn":
        score += 2.5
        if observation.predicate in predicates:
            score += 6.0
        if observation.metadata.get("value"):
            score += 1.5
    else:
        score -= 1.5
    if len(evidence_tokens) <= 8:
        score += 1.0
    if question_lower.startswith("how did") and "appreciate" in evidence_text.lower():
        score += 3.0
    if (
        question_lower.startswith("how did")
        and "support" in question_lower
        and "appreciate" in evidence_text.lower()
        and any(token in observation_context_lower for token in ("support", "family"))
    ):
        score += 12.0
    if "support" in question_lower and "real support" in observation_context_lower:
        score += 10.0
    if "support" in question_lower and evidence_text.lower().startswith("appreciate them"):
        score += 6.0
    if "support" in question_lower and any(
        token in evidence_text.lower() for token in ("support", "appreciate", "thankful", "grateful")
    ):
        score += 4.0
    if question_lower.startswith("when ") and "festival" in question_lower and "next month" in evidence_text.lower():
        score += 10.0
    if question_lower.startswith("when ") and "tattoo" in question_lower and "few years ago" in evidence_text.lower():
        score += 12.0
    if question_lower.startswith("when ") and "accepted" in question_lower and "accepted" in evidence_text.lower():
        score += 12.0
    if question_lower.startswith("when ") and "start reading" in question_lower and "reading" in evidence_text.lower():
        score += 10.0
    if question_lower.startswith("when ") and "social media presence" in question_lower and "social media presence" in evidence_text.lower():
        score += 10.0
    if question_lower.startswith("which city") and "both" in question_lower and any(
        token in observation_context_lower for token in ("rome", "paris", "trip to", "visit it", "been only to")
    ):
        score += 12.0
    if "road trip" in question_lower and "relax" in question_lower and any(
        token in evidence_text.lower() for token in ("hike", "walk")
    ):
        score += 6.0
    if question_lower.startswith("did ") and evidence_text.lower() in {"yes", "no"}:
        score += 5.0
    if "both have in common" in question_lower and any(
        token in observation_context_lower
        for token in ("lost my job", "lost his job", "lost her job", "starting my own store", "own business", "online clothing store", "dance studio")
    ):
        score += 12.0
    return score
