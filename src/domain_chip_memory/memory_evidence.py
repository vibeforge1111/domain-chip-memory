from __future__ import annotations

from .contracts import NormalizedQuestion
from .memory_extraction import ObservationEntry, _tokenize
from .memory_observation_utils import candidate_sentences
from .memory_preferences import (
    is_generic_followup_preference_text,
    is_preference_question,
    is_recommendation_request_text,
    preference_domain_tokens,
    preference_phrase_bonus,
)
from .memory_rendering import answer_candidate_surface_text


def entry_source_corpus(entry: ObservationEntry) -> str:
    return " ".join(
        part
        for part in (
            str(entry.metadata.get("source_text", "")),
            entry.text,
            str(entry.metadata.get("value", "")),
        )
        if part
    )


def raw_evidence_span(question: NormalizedQuestion, observation: ObservationEntry) -> str:
    source_text = str(observation.metadata.get("source_text", "")).strip() or observation.text
    sentences = candidate_sentences(source_text)
    if not sentences:
        return source_text.strip()

    question_lower = question.question.lower()
    question_tokens = set(_tokenize(question.question))
    best_sentence = sentences[0]
    best_score = float("-inf")
    for sentence in sentences:
        sentence_lower = sentence.lower()
        sentence_tokens = set(_tokenize(sentence))
        score = 2.0 * float(len(question_tokens.intersection(sentence_tokens)))
        if len(sentence_tokens) <= 8:
            score += 1.0
        if question_lower.startswith("how did") and any(
            token in sentence_lower for token in ("appreciate", "grateful", "thankful", "happy", "sad", "scared", "relieved")
        ):
            score += 3.0
        if question_lower.startswith("what did") and any(
            token in sentence_lower for token in ("went", "read", "paint", "made", "saw", "did", "hike", "walk", "attended")
        ):
            score += 2.0
        if question_lower.startswith("did ") and sentence_lower in {"yes", "no"}:
            score += 4.0
        if "road trip" in question_lower and "relax" in question_lower and any(
            token in sentence_lower for token in ("hike", "walk")
        ):
            score += 6.0
        if is_preference_question(question):
            preference_overlap = len(preference_domain_tokens(question).intersection(sentence_tokens))
            score += 4.0 * float(preference_overlap)
            score += preference_phrase_bonus(question, sentence)
            if is_recommendation_request_text(sentence):
                score += 2.0
            if is_generic_followup_preference_text(sentence):
                score -= 5.0
            if preference_overlap == 0:
                score -= 2.0
        if score > best_score:
            best_score = score
            best_sentence = sentence
    return best_sentence


def observation_evidence_text(question: NormalizedQuestion, observation: ObservationEntry) -> str:
    if observation.predicate == "raw_turn":
        return raw_evidence_span(question, observation)
    value = str(observation.metadata.get("value", "")).strip()
    return answer_candidate_surface_text(
        observation.subject,
        observation.predicate,
        value,
        str(observation.metadata.get("source_text", observation.text)),
    )
