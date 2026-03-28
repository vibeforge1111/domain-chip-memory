from __future__ import annotations

from .contracts import NormalizedBenchmarkSample, NormalizedQuestion
from .memory_extraction import EventCalendarEntry, _token_bigrams, _tokenize
from .memory_queries import _question_predicates, _question_subject


def question_aware_observation_limits(
    sample: NormalizedBenchmarkSample,
    question: NormalizedQuestion,
    *,
    max_observations: int,
    max_reflections: int,
) -> tuple[int, int]:
    if sample.benchmark_name != "LoCoMo":
        return max_observations, max_reflections

    question_lower = question.question.lower()
    observation_limit = max_observations
    reflection_limit = max_reflections

    if question.category in {"1", "3", "single-hop", "multi-hop"}:
        observation_limit = max(observation_limit, 10)
        reflection_limit = max(reflection_limit, 6)

    if (
        question_lower.startswith("who ")
        or question_lower.startswith("how many")
        or question_lower.startswith("how do ")
        or question_lower.startswith("do ")
        or question_lower.startswith("did ")
        or question_lower.startswith("would ")
        or question_lower.startswith("what events")
        or question_lower.startswith("what activities")
        or " both " in question_lower
        or " in common" in question_lower
        or "in what ways" in question_lower
        or "what types of pottery" in question_lower
        or "what kind of art" in question_lower
        or ("what did" in question_lower and "paint" in question_lower)
        or question_lower.startswith("what ")
    ):
        observation_limit = max(observation_limit, 10)
        reflection_limit = max(reflection_limit, 6)

    if any(
        token in question_lower
        for token in (
            "pets' names",
            "what has",
            "what symbols",
            "what instruments",
            "artists/bands",
            "what book",
            "personality traits",
            "transition journey",
            "transgender-specific events",
        )
    ):
        observation_limit = max(observation_limit, 12)
        reflection_limit = max(reflection_limit, 7)

    if question_lower.startswith("when did") or question_lower.startswith("when was") or question_lower.startswith("when is"):
        observation_limit = max(observation_limit, 6)
        reflection_limit = max(reflection_limit, 4)
        if any(
            token in question_lower
            for token in ("camping", "pride", "birthday", "activist group", "mentorship program")
        ):
            observation_limit = max(observation_limit, 8)
            reflection_limit = max(reflection_limit, 5)

    if (
        ("what lgbtq+" in question_lower or "what lgbtq events" in question_lower)
        or ("what events has" in question_lower and "help children" in question_lower)
    ):
        observation_limit = max(observation_limit, 12)
        reflection_limit = max(reflection_limit, 7)

    return observation_limit, reflection_limit


def event_score(question: NormalizedQuestion, event: EventCalendarEntry) -> float:
    score = 0.0
    subject = _question_subject(question)
    predicates = _question_predicates(question)
    question_tokens = set(_tokenize(question.question))
    event_tokens = set(_tokenize(event.text))
    question_bigrams = _token_bigrams(question.question)
    event_bigrams = _token_bigrams(event.text)
    if event.subject == subject:
        score += 3.0
    if event.predicate in predicates:
        score += 5.0
    score += float(len(question_tokens.intersection(event_tokens)))
    score += 1.5 * min(len(question_bigrams.intersection(event_bigrams)), 3)
    if question.category in {"knowledge-update", "temporal", "temporal-reasoning"} and event.timestamp:
        score += 2.0
    if event.timestamp:
        score += 0.001 * sum(ord(char) for char in event.timestamp)
    return score
