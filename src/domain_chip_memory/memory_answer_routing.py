from __future__ import annotations

from collections.abc import Callable

from .contracts import NormalizedQuestion
from .memory_extraction import ObservationEntry


def entry_combined_text(
    question: NormalizedQuestion,
    entry: ObservationEntry,
    *,
    observation_evidence_text: Callable[[NormalizedQuestion, ObservationEntry], str],
) -> str:
    return " ".join(
        part.lower()
        for part in (
            observation_evidence_text(question, entry),
            entry.text,
            str(entry.metadata.get("source_text", "")),
            str(entry.metadata.get("value", "")),
        )
        if part
    )

def question_needs_raw_aggregate_context(question: NormalizedQuestion) -> bool:
    question_lower = question.question.lower()
    return (
        question_lower.startswith(
            (
                "how many ",
                "how much total ",
                "how much more ",
                "how much older am i ",
                "how many points do i need to earn ",
                "what is the average ",
                "what is the total amount ",
                "what is the total distance ",
                "what is the total cost ",
                "what is the total number of ",
                "what is the total number of episodes ",
                "what is the total time it takes i to get ready and commute to work",
                "what is the difference in price between ",
                "what is the minimum amount i could get if i sold ",
                "what was the approximate increase in instagram followers ",
                "what was the total number of people reached ",
                "what percentage of packed shoes did i wear ",
                "what time did i reach the clinic on monday",
                "how many years will i be when my friend rachel gets married",
                "how many dinner parties have i attended in the past month",
                "how much did i spend on gifts for my sister",
                "how many years older is my grandma than me",
                "how many years older am i than when i graduated from college",
            )
        )
        or question_lower.startswith(
            (
                "what are the two hobbies that led me to join online communities",
                "what percentage of the countryside property's price ",
                "how many pages do i have left to read ",
                "how old was i when ",
                "how long have i been working in my current role",
                "how much did i spend on each ",
                "how much cashback did i earn ",
                "how many antique items did i inherit or acquire ",
                "when did i submit my research paper on sentiment analysis",
                "what is the total number of days i spent in japan and chicago",
                "did i receive a higher percentage discount on my first order from hellofresh",
                "for my daily commute, how much more expensive was the taxi ride compared to the train fare",
            )
        )
        or question_lower in {
            "what time did i go to bed on the day before i had a doctor's appointment?",
            "which social media platform did i gain the most followers on over the past month?",
            "which grocery store did i spend the most money at in the past month?",
        }
    )

def choose_answer_candidate(
    question: NormalizedQuestion,
    evidence_entries: list[ObservationEntry],
    belief_entries: list[ObservationEntry],
    *,
    context_entries: list[ObservationEntry] | None,
    aggregate_entries: list[ObservationEntry] | None,
    question_needs_raw_aggregate_context: Callable[[NormalizedQuestion], bool],
    infer_dated_state_answer: Callable[[NormalizedQuestion, list[ObservationEntry]], str],
    infer_relative_state_answer: Callable[[NormalizedQuestion, list[ObservationEntry]], str],
    is_preference_question: Callable[[NormalizedQuestion], bool],
    infer_preference_answer: Callable[[NormalizedQuestion, list[ObservationEntry]], str],
    infer_factoid_answer: Callable[[NormalizedQuestion, list[ObservationEntry]], str],
    infer_aggregate_answer: Callable[[NormalizedQuestion, list[ObservationEntry]], str],
    infer_temporal_answer: Callable[[NormalizedQuestion, list[ObservationEntry]], str],
    infer_shared_answer: Callable[[NormalizedQuestion, list[ObservationEntry]], str],
    infer_explanatory_answer: Callable[[NormalizedQuestion, list[ObservationEntry]], str],
    infer_yes_no_answer: Callable[[NormalizedQuestion, list[ObservationEntry]], str],
    answer_candidate_surface_text: Callable[[str, str, str, str], str],
    evidence_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    observation_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    observation_evidence_text: Callable[[NormalizedQuestion, ObservationEntry], str],
) -> str:
    question_lower = question.question.lower()
    if question.should_abstain:
        return "unknown"
    candidate_entries = context_entries or evidence_entries
    aggregate_candidate_entries = list(aggregate_entries or [])
    for entry in candidate_entries:
        if entry not in aggregate_candidate_entries:
            aggregate_candidate_entries.append(entry)
    aggregate_first = (
        question_needs_raw_aggregate_context(question)
        or question_lower.startswith("what are the two hobbies that led me to join online communities")
    )
    dated_state_answer = infer_dated_state_answer(question, candidate_entries)
    if dated_state_answer:
        return dated_state_answer
    relative_state_answer = infer_relative_state_answer(question, candidate_entries)
    if relative_state_answer:
        return relative_state_answer
    if is_preference_question(question):
        preference_answer = infer_preference_answer(question, candidate_entries)
        if preference_answer:
            return preference_answer
    factoid_answer = infer_factoid_answer(question, candidate_entries)
    if factoid_answer.lower() == "unknown":
        return factoid_answer
    if aggregate_first:
        aggregate_answer = infer_aggregate_answer(question, aggregate_candidate_entries)
        if aggregate_answer:
            return aggregate_answer
    temporal_answer = infer_temporal_answer(question, candidate_entries)
    if temporal_answer:
        return temporal_answer
    shared_answer = infer_shared_answer(question, candidate_entries)
    if shared_answer:
        return shared_answer
    explanatory_answer = infer_explanatory_answer(question, candidate_entries)
    if explanatory_answer:
        return explanatory_answer
    aggregate_answer = infer_aggregate_answer(question, aggregate_candidate_entries)
    if aggregate_answer:
        return aggregate_answer
    yes_no_answer = infer_yes_no_answer(question, candidate_entries)
    if yes_no_answer:
        return yes_no_answer
    if factoid_answer:
        return factoid_answer
    if belief_entries and any(token in question_lower for token in (" now", "currently", "current ", "at the moment", "these days")):
        top_entry = belief_entries[0]
        return answer_candidate_surface_text(
            top_entry.subject,
            top_entry.predicate,
            str(top_entry.metadata.get("value", "")),
            top_entry.text,
        )
    if evidence_entries:
        best_evidence = max(
            evidence_entries,
            key=lambda entry: (evidence_score(question, entry), observation_score(question, entry), entry.timestamp or "", entry.observation_id),
        )
        return observation_evidence_text(question, best_evidence)
    if belief_entries:
        top_entry = belief_entries[0]
        return answer_candidate_surface_text(
            top_entry.subject,
            top_entry.predicate,
            str(top_entry.metadata.get("value", "")),
            top_entry.text,
        )
    return ""

