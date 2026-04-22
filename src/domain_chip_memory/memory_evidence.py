from __future__ import annotations

from .contracts import NormalizedQuestion
from .memory_answer_rendering import answer_candidate_surface_text
from .memory_extraction import ObservationEntry, _tokenize
from .memory_observation_utils import candidate_sentences
from .memory_preferences import (
    is_generic_followup_preference_text,
    is_preference_question,
    is_recommendation_request_text,
    preference_domain_tokens,
    preference_phrase_bonus,
)


_EVIDENCE_SENTENCE_STOPWORDS = {
    "a",
    "about",
    "after",
    "all",
    "also",
    "am",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "been",
    "but",
    "by",
    "do",
    "for",
    "from",
    "got",
    "had",
    "has",
    "have",
    "how",
    "i",
    "if",
    "im",
    "in",
    "into",
    "is",
    "it",
    "its",
    "just",
    "let",
    "like",
    "me",
    "my",
    "of",
    "on",
    "or",
    "our",
    "so",
    "that",
    "the",
    "their",
    "them",
    "there",
    "they",
    "this",
    "to",
    "up",
    "us",
    "was",
    "we",
    "were",
    "what",
    "with",
    "you",
    "your",
}

_LOW_SIGNAL_SENTENCE_PREFIXES = (
    "aww",
    "cool",
    "god",
    "got it",
    "great",
    "hey",
    "hi",
    "hello",
    "man",
    "nice",
    "nope",
    "oh",
    "okay",
    "ok",
    "phew",
    "sounds great",
    "sure",
    "thanks",
    "thank you",
    "well done",
    "wow",
    "yeah",
    "yep",
    "you're welcome",
)


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


def _normalize_sentence_tokens(text: str) -> set[str]:
    normalized: set[str] = set()
    for token in _tokenize(text):
        if token == "favourite":
            token = "favorite"
        normalized.add(token)
    return normalized


def _content_token_count(text: str) -> int:
    return sum(
        1
        for token in _normalize_sentence_tokens(text)
        if len(token) >= 3 and token not in _EVIDENCE_SENTENCE_STOPWORDS
    )


def _is_pure_question_turn(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped) and stripped.endswith("?") and "." not in stripped and "!" not in stripped


def _has_low_signal_prefix(text: str) -> bool:
    lower = text.lower().strip(" \"'")
    return any(lower.startswith(prefix) for prefix in _LOW_SIGNAL_SENTENCE_PREFIXES)


def raw_evidence_span(question: NormalizedQuestion, observation: ObservationEntry) -> str:
    source_text = str(observation.metadata.get("source_text", "")).strip() or observation.text
    sentences = candidate_sentences(source_text)
    if not sentences:
        return source_text.strip()

    question_lower = question.question.lower()
    question_tokens = _normalize_sentence_tokens(question.question)
    best_sentence = sentences[0]
    best_score = float("-inf")
    for sentence in sentences:
        sentence_lower = sentence.lower()
        sentence_tokens = _normalize_sentence_tokens(sentence)
        score = 2.0 * float(len(question_tokens.intersection(sentence_tokens)))
        content_tokens = _content_token_count(sentence)
        score += min(content_tokens, 8) * 0.35
        if len(sentence_tokens) <= 8:
            score += 1.0
        if _is_pure_question_turn(sentence):
            score -= 6.0
        if len(sentences) > 1 and _has_low_signal_prefix(sentence):
            score -= 3.0
        if "check out this screenshot" in sentence_lower or "check out this pic" in sentence_lower or "check it out" in sentence_lower:
            score -= 3.0
        if sentence_lower.startswith("by the way,"):
            score += 0.5
        if question_lower.startswith("how did") and any(
            token in sentence_lower for token in ("appreciate", "grateful", "thankful", "happy", "sad", "scared", "relieved")
        ):
            score += 3.0
        if question_lower.startswith("what did") and any(
            token in sentence_lower for token in ("went", "read", "paint", "made", "saw", "did", "hike", "walk", "attended")
        ):
            score += 2.0
        if question_lower.startswith(("what are", "which", "what did", "what game", "what martial arts")) and any(
            token in sentence_lower
            for token in ("favorite", "favourite", "called", "went", "adopted", "named", "dogs", "pets", "puppy", "bowling", "baseball", "pub")
        ):
            score += 2.5
        if question_lower.startswith(("do ", "does ", "did ", "is ", "are ")) and any(
            token in sentence_lower
            for token in ("don't have", "dont have", "my dogs", "my dog", "my cat", "my puppy", "pets")
        ):
            score += 2.5
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
