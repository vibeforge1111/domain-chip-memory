from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from .contracts import AnswerCandidate, NormalizedBenchmarkSample, NormalizedQuestion
from .memory_builder_sections import append_retrieved_entries, build_entry_metadata
from .memory_extraction import ObservationEntry, _tokenize
from .runs import BaselinePromptPacket, RetrievedContextItem

_NEGATION_PATTERNS = (
    " never ",
    " not ",
    " no ",
    " without ",
    " didn't ",
    " dont ",
    " don't ",
    " havent ",
    " haven't ",
    " hasnt ",
    " hasn't ",
    " wasnt ",
    " wasn't ",
)

_CONTRADICTION_FOCUS_STOPWORDS = {
    "about",
    "and",
    "can",
    "did",
    "for",
    "have",
    "handled",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "project",
    "the",
    "this",
    "to",
    "with",
    "worked",
    "you",
}

_CONTRADICTION_ASSERTIVE_PATTERNS = (
    "implemented",
    "implement",
    "integrated",
    "integrate",
    "fixed",
    "added",
    "used",
    "using",
    "obtained",
    "replace",
    "replacing",
    "managed",
    "tested",
)

_CONTRADICTION_HELP_PATTERNS = (
    "can you help",
    "can you review",
    "can you provide",
    "please provide",
    "walk me through",
    "starting from scratch",
    "i'm not sure",
    "im not sure",
    "i want to make sure",
    "review my code",
    "provide an example",
    "tutorial",
    "tutorials",
)

def _compact_source_text(entry: ObservationEntry) -> str:
    source_text = str(entry.metadata.get("source_text", "")).strip() or entry.text.strip()
    source_text = re.sub(r"```.*?```", "", source_text, flags=re.DOTALL).strip()
    source_text = re.split(r"(?<=[.!?])\s+", source_text)[0].strip()
    source_text = re.sub(
        r"^(?:i'm|im|i am)\s+(?:currently\s+|working on\s+|trying to\s+|planning to\s+|finalizing\s+|having trouble with\s+)?",
        "",
        source_text,
        flags=re.IGNORECASE,
    )
    source_text = re.sub(r"\b(?:can|could)\s+you\s+help\s+me\b.*$", "", source_text, flags=re.IGNORECASE).strip(" ,;:-")
    return source_text or entry.text.strip()


def _is_contradiction_question(question: NormalizedQuestion) -> bool:
    return question.category == "contradiction_resolution" or "contradiction" in question.question_id.lower()


def _question_focus_tokens(question: NormalizedQuestion) -> set[str]:
    return {
        token
        for token in _tokenize(question.question.lower())
        if len(token) >= 3 and token not in _CONTRADICTION_FOCUS_STOPWORDS
    }


def _entry_claim_text(entry: ObservationEntry) -> str:
    return str(entry.metadata.get("source_text", "")).strip() or entry.text.strip()


def _claim_is_negated(text: str) -> bool:
    normalized_text = re.sub(r"\s+", " ", text.lower()).strip()
    normalized = f" {normalized_text} "
    return any(pattern in normalized for pattern in _NEGATION_PATTERNS)


def _is_locomo_evidence_first_question(question: NormalizedQuestion) -> bool:
    source_format = str(question.metadata.get("source_format", "")).strip().lower()
    return source_format == "locomo_qa" and str(question.category).strip() in {"1", "2", "3"}


def _question_prefers_temporal_reconstruction(question: NormalizedQuestion) -> bool:
    question_lower = question.question.lower()
    return any(
        cue in question_lower
        for cue in (
            "when did",
            "when was",
            "how long",
            "how many days",
            "how many weeks",
            "how many months",
            "how many years",
            "before ",
            "after ",
            "between ",
            "first ",
            "last ",
            "earlier ",
            "later ",
        )
    )


def _normalized_surface_text(text: str) -> str:
    return " ".join(str(text).lower().strip().split())


def _answer_matches_entries(answer_text: str, entries: list[ObservationEntry]) -> bool:
    normalized_answer = _normalized_surface_text(answer_text)
    if not normalized_answer:
        return False
    for entry in entries:
        candidate_surfaces = (
            entry.text,
            str(entry.metadata.get("source_text", "")),
            str(entry.metadata.get("value", "")),
        )
        if any(normalized_answer in _normalized_surface_text(surface) for surface in candidate_surfaces if surface):
            return True
    return False


def _contradiction_entry_score(question: NormalizedQuestion, entry: ObservationEntry) -> float:
    claim_text = _entry_claim_text(entry)
    normalized_claim = re.sub(r"\s+", " ", claim_text.lower()).strip()
    normalized = f" {normalized_claim} "
    focus_overlap = len(_question_focus_tokens(question).intersection(set(_tokenize(normalized))))
    score = 8.0 * float(focus_overlap)
    score += 4.0 * float(sum(1 for pattern in _CONTRADICTION_ASSERTIVE_PATTERNS if pattern in normalized))
    score -= 5.0 * float(sum(1 for pattern in _CONTRADICTION_HELP_PATTERNS if pattern in normalized))
    if entry.predicate == "raw_turn":
        score += 3.0
    if "?" in claim_text:
        score -= 3.0
    token_count = len(_tokenize(claim_text))
    if token_count > 36:
        score -= min(token_count - 36, 48) * 0.25
    return score


def _select_contradiction_support_entries(
    question: NormalizedQuestion,
    entries: list[ObservationEntry],
    *,
    dedupe_observations: Callable[[list[ObservationEntry]], list[ObservationEntry]],
    limit: int = 4,
) -> list[ObservationEntry]:
    if not _is_contradiction_question(question):
        return []
    focus_tokens = _question_focus_tokens(question)
    ranked = sorted(
        dedupe_observations(entries),
        key=lambda entry: (
            _contradiction_entry_score(question, entry),
            len(focus_tokens.intersection(set(_tokenize(_entry_claim_text(entry).lower())))),
            entry.timestamp or "",
            entry.observation_id,
        ),
        reverse=True,
    )
    candidates = [
        entry
        for entry in ranked
        if focus_tokens.intersection(set(_tokenize(_entry_claim_text(entry).lower())))
    ]
    if not candidates:
        return []
    selected: list[ObservationEntry] = []
    negated = [entry for entry in candidates if _claim_is_negated(_entry_claim_text(entry))]
    affirmative = [entry for entry in candidates if not _claim_is_negated(_entry_claim_text(entry))]
    if negated:
        selected.append(negated[0])
    if affirmative:
        selected.append(affirmative[0])
    for entry in candidates:
        if entry in selected:
            continue
        selected.append(entry)
        if len(selected) >= limit:
            break
    return dedupe_observations(selected[:limit])


def _build_synthesis_entries(
    question: NormalizedQuestion,
    entries: list[ObservationEntry],
    *,
    evidence_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    observation_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    dedupe_observations: Callable[[list[ObservationEntry]], list[ObservationEntry]],
    limit: int = 4,
) -> list[ObservationEntry]:
    ranked = sorted(
        entries,
        key=lambda entry: (evidence_score(question, entry), observation_score(question, entry), entry.timestamp or "", entry.observation_id),
        reverse=True,
    )
    selected: list[ObservationEntry] = []
    seen_texts: set[str] = set()
    for entry in ranked:
        compact_text = _compact_source_text(entry)
        normalized = compact_text.lower()
        if not compact_text or normalized in seen_texts:
            continue
        seen_texts.add(normalized)
        metadata = dict(entry.metadata)
        metadata.setdefault("source_text", compact_text)
        metadata["synthesized_from"] = entry.observation_id
        selected.append(
            ObservationEntry(
                observation_id=f"{entry.observation_id}:summary",
                subject=entry.subject,
                predicate="summary_synthesis",
                text=compact_text,
                session_id=entry.session_id,
                turn_ids=list(entry.turn_ids),
                timestamp=entry.timestamp,
                metadata=metadata,
            )
        )
        if len(selected) >= limit:
            break
    return dedupe_observations(selected)


def build_summary_synthesis_memory_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    max_observations: int,
    max_reflections: int,
    max_topic_support: int,
    run_id: str,
    build_observation_log: Callable[[NormalizedBenchmarkSample], list[ObservationEntry]],
    reflect_observations: Callable[[list[ObservationEntry]], list[ObservationEntry]],
    raw_user_turn_entries: Callable[[NormalizedBenchmarkSample], list[ObservationEntry]],
    has_active_current_state_deletion: Callable[..., bool],
    is_current_state_question: Callable[[NormalizedQuestion], bool],
    question_subjects: Callable[[NormalizedQuestion], list[str]],
    question_predicates: Callable[[NormalizedQuestion], list[str]],
    question_aware_observation_limits: Callable[..., tuple[int, int]],
    is_preference_question: Callable[[NormalizedQuestion], bool],
    select_preference_support_entries: Callable[..., list[ObservationEntry]],
    observation_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    select_current_state_entries: Callable[..., list[ObservationEntry]],
    topical_episode_support: Callable[..., tuple[str, list[ObservationEntry]]],
    dedupe_observations: Callable[[list[ObservationEntry]], list[ObservationEntry]],
    select_evidence_entries: Callable[..., list[ObservationEntry]],
    question_needs_raw_aggregate_context: Callable[[NormalizedQuestion], bool],
    select_aggregate_support_entries: Callable[[NormalizedQuestion, list[ObservationEntry]], list[ObservationEntry]],
    observation_evidence_text: Callable[[NormalizedQuestion, ObservationEntry], str],
    evidence_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    entry_source_corpus: Callable[[ObservationEntry], str],
    choose_answer_candidate: Callable[..., str],
    is_dated_state_question: Callable[[NormalizedQuestion], bool],
    is_relative_state_question: Callable[[NormalizedQuestion], bool],
    has_ambiguous_relative_state_anchor: Callable[[NormalizedQuestion, list[Any]], bool],
    has_referential_ambiguity: Callable[[NormalizedQuestion, list[Any]], bool],
    should_use_current_state_exact_value: Callable[[NormalizedQuestion], bool],
    build_answer_candidate: Callable[..., AnswerCandidate],
    build_run_manifest: Callable[..., Any],
    strategy_memory_role: Callable[[str], str],
) -> tuple[dict[str, Any], list[BaselinePromptPacket]]:
    packets: list[BaselinePromptPacket] = []
    for sample in samples:
        observations = build_observation_log(sample)
        raw_entries = raw_user_turn_entries(sample)
        for question in sample.questions:
            question_predicate_set = set(question_predicates(question))
            question_observations = [
                entry
                for entry in observations
                if not (
                    entry.metadata.get("typed_conversational")
                    and entry.predicate not in question_predicate_set
                    and not (
                        _question_prefers_temporal_reconstruction(question)
                        and entry.predicate in {"loss_event", "gift_event"}
                    )
                )
            ]
            question_structured_observations = [
                entry for entry in question_observations if entry.predicate != "raw_turn"
            ]
            question_reflected = reflect_observations(question_observations)
            current_state_deleted = has_active_current_state_deletion(
                question,
                question_observations,
                is_current_state_question=is_current_state_question,
                question_subjects=question_subjects,
                question_predicates=question_predicates,
            )
            observation_limit, reflection_limit = question_aware_observation_limits(
                sample,
                question,
                max_observations=max_observations,
                max_reflections=max_reflections,
            )
            preference_support: list[ObservationEntry] = []
            if sample.benchmark_name == "LongMemEval" and is_preference_question(question):
                preference_support = select_preference_support_entries(
                    question,
                    raw_entries,
                    limit=observation_limit,
                )
            stable_window = dedupe_observations(
                sorted(
                    question_observations,
                    key=lambda entry: (observation_score(question, entry), entry.timestamp or "", entry.observation_id),
                    reverse=True,
                )
            )[:observation_limit]
            ranked_reflections = sorted(
                question_reflected,
                key=lambda entry: (observation_score(question, entry), entry.timestamp or "", entry.observation_id),
                reverse=True,
            )[:reflection_limit]
            current_state_entries = select_current_state_entries(
                question,
                question_reflected,
                limit=2,
                score_entry=lambda entry: observation_score(question, entry),
                preferred_predicates=set(question_predicates(question)),
            )
            topic_summary = ""
            topical_support: list[ObservationEntry] = []
            if sample.benchmark_name == "LoCoMo":
                topic_summary, topical_support = topical_episode_support(
                    question,
                    stable_window,
                    question_observations,
                    max_support=max_topic_support,
                )
            contradiction_support = _select_contradiction_support_entries(
                question,
                [*raw_entries, *question_observations, *question_structured_observations],
                dedupe_observations=dedupe_observations,
                limit=max(4, max_topic_support + 2),
            )
            synthesis_entries = _build_synthesis_entries(
                question,
                dedupe_observations([*contradiction_support, *question_structured_observations, *stable_window, *ranked_reflections]),
                evidence_score=evidence_score,
                observation_score=observation_score,
                dedupe_observations=dedupe_observations,
                limit=max(3, max_topic_support + 1),
            )
            evidence_pool = dedupe_observations(
                [
                    *contradiction_support,
                    *synthesis_entries,
                    *current_state_entries,
                    *preference_support,
                    *stable_window,
                    *topical_support,
                    *question_structured_observations,
                    *question_observations,
                ]
            )
            evidence_entries = select_evidence_entries(
                question,
                evidence_pool,
                limit=max(5, max_topic_support + 3),
            )
            raw_candidate_pool = [
                *contradiction_support,
                *synthesis_entries,
                *current_state_entries,
                *preference_support,
                *stable_window,
                *topical_support,
                *question_structured_observations,
                *question_observations,
                *ranked_reflections,
            ]
            candidate_pool = dedupe_observations(raw_candidate_pool)
            aggregate_pool = candidate_pool
            if sample.benchmark_name == "LongMemEval" and question_needs_raw_aggregate_context(question):
                aggregate_pool = dedupe_observations([*candidate_pool, *raw_entries])
            aggregate_support_entries = (
                select_aggregate_support_entries(question, aggregate_pool)
                if sample.benchmark_name == "LongMemEval"
                else []
            )

            context_blocks = ["summary_synthesis_window:"]
            retrieved_items: list[RetrievedContextItem] = []
            append_retrieved_entries(
                context_blocks,
                retrieved_items,
                contradiction_support,
                header="contradiction_memory:" if contradiction_support else None,
                line_builder=lambda entry: f"claim: {_entry_claim_text(entry)}",
                score_builder=lambda entry: _contradiction_entry_score(question, entry),
                strategy="summary_synthesis_memory",
                memory_role=strategy_memory_role("summary_synthesis_memory"),
                metadata_builder=build_entry_metadata,
            )
            append_retrieved_entries(
                context_blocks,
                retrieved_items,
                synthesis_entries,
                header=None,
                line_builder=lambda entry: f"synthesis: {entry.text}",
                score_builder=lambda entry: evidence_score(question, entry),
                strategy="summary_synthesis_memory",
                memory_role=strategy_memory_role("summary_synthesis_memory"),
                metadata_builder=build_entry_metadata,
            )
            append_retrieved_entries(
                context_blocks,
                retrieved_items,
                evidence_entries,
                header="evidence_memory:",
                line_builder=lambda entry: f"evidence: {observation_evidence_text(question, entry)}",
                score_builder=lambda entry: evidence_score(question, entry),
                strategy="evidence_memory",
                memory_role=strategy_memory_role("evidence_memory"),
                metadata_builder=lambda entry: build_entry_metadata(entry, include_topic_id=True),
            )

            if aggregate_support_entries:
                append_retrieved_entries(
                    context_blocks,
                    retrieved_items,
                    aggregate_support_entries,
                    header="aggregate_memory:",
                    line_builder=lambda entry: f"aggregate: {entry_source_corpus(entry)}",
                    score_builder=lambda entry: evidence_score(question, entry),
                    strategy="aggregate_memory",
                    memory_role=strategy_memory_role("aggregate_memory"),
                    metadata_builder=build_entry_metadata,
                )

            if topical_support:
                if topic_summary:
                    context_blocks.append("topical_episode:")
                    context_blocks.append(f"topic_summary: {topic_summary}")
                    topical_header = None
                else:
                    topical_header = "topical_episode:"
                append_retrieved_entries(
                    context_blocks,
                    retrieved_items,
                    topical_support,
                    header=topical_header,
                    line_builder=lambda entry: f"episode_observation: {entry.text}",
                    score_builder=lambda entry: observation_score(question, entry),
                    strategy="topic_continuity",
                    memory_role=strategy_memory_role("topic_continuity"),
                    metadata_builder=lambda entry: build_entry_metadata(entry, include_topic_id=True),
                )

            if current_state_entries:
                append_retrieved_entries(
                    context_blocks,
                    retrieved_items,
                    current_state_entries,
                    header="current_state_memory:",
                    line_builder=lambda entry: f"current_state: {entry.text}",
                    score_builder=lambda entry: observation_score(question, entry),
                    strategy="current_state_memory",
                    memory_role=strategy_memory_role("current_state_memory"),
                    metadata_builder=build_entry_metadata,
                )

            append_retrieved_entries(
                context_blocks,
                retrieved_items,
                ranked_reflections,
                header="belief_memory:",
                line_builder=lambda entry: f"reflection: {entry.text}",
                score_builder=lambda entry: observation_score(question, entry),
                strategy="belief_memory",
                memory_role=strategy_memory_role("belief_memory"),
                metadata_builder=lambda entry: build_entry_metadata(entry, include_media_fields=True),
            )

            answer_evidence_entries = evidence_entries
            answer_context_entries = (
                raw_candidate_pool if (is_dated_state_question(question) or is_relative_state_question(question)) else candidate_pool
            )
            if sample.benchmark_name == "LoCoMo" and _is_locomo_evidence_first_question(question):
                if _question_prefers_temporal_reconstruction(question):
                    locomo_evidence_first_entries = dedupe_observations(
                        [
                            *[entry for entry in evidence_entries if entry.predicate != "summary_synthesis"],
                        ]
                    )
                else:
                    locomo_evidence_first_entries = dedupe_observations(
                        [
                            *[entry for entry in evidence_entries if entry.predicate != "summary_synthesis"],
                            *topical_support,
                            *[entry for entry in ranked_reflections if entry.predicate != "summary_synthesis"],
                            *current_state_entries,
                            *preference_support,
                        ]
                    )
                if locomo_evidence_first_entries:
                    answer_evidence_entries = locomo_evidence_first_entries
                    answer_context_entries = dedupe_observations(
                        [
                            *locomo_evidence_first_entries,
                            *stable_window,
                            *topical_support,
                            *question_structured_observations,
                            *question_observations,
                        ]
                    )
            if _question_prefers_temporal_reconstruction(question):
                typed_temporal_entries = [
                    entry
                    for entry in question_observations
                    if entry.metadata.get("typed_conversational")
                    and entry.predicate in {"loss_event", "gift_event"}
                ]
                if typed_temporal_entries:
                    answer_evidence_entries = dedupe_observations(
                        [*typed_temporal_entries, *answer_evidence_entries]
                    )
                    answer_context_entries = dedupe_observations(
                        [*typed_temporal_entries, *answer_context_entries]
                    )

            answer_text = choose_answer_candidate(
                question,
                answer_evidence_entries,
                ranked_reflections,
                answer_context_entries,
                aggregate_pool,
            )
            ambiguous_relative_state = has_ambiguous_relative_state_anchor(question, raw_candidate_pool)
            referential_ambiguity = has_referential_ambiguity(question, raw_candidate_pool)
            if should_use_current_state_exact_value(question) and current_state_entries:
                current_state_value = str(current_state_entries[0].metadata.get("value", "")).strip()
                if current_state_value:
                    answer_text = current_state_value
            elif current_state_deleted:
                answer_text = "unknown"

            answer_candidates: list[AnswerCandidate] = []
            if answer_text:
                source = "belief_memory"
                if should_use_current_state_exact_value(question) and current_state_entries:
                    source = "current_state_memory"
                elif current_state_deleted:
                    source = "current_state_deletion"
                elif referential_ambiguity and answer_text.lower() == "unknown":
                    source = "referential_ambiguity"
                elif ambiguous_relative_state and answer_text.lower() == "unknown":
                    source = "temporal_ambiguity"
                elif sample.benchmark_name == "LoCoMo" and _is_locomo_evidence_first_question(question):
                    if _answer_matches_entries(answer_text, evidence_entries):
                        source = "evidence_memory"
                    elif _answer_matches_entries(answer_text, ranked_reflections):
                        source = "belief_memory"
                    elif _answer_matches_entries(answer_text, topical_support):
                        source = "topic_continuity"
                    elif _answer_matches_entries(answer_text, synthesis_entries):
                        source = "aggregate_memory"
                    elif evidence_entries:
                        source = "evidence_memory"
                elif (is_dated_state_question(question) or is_relative_state_question(question)) and evidence_entries:
                    source = "evidence_memory"
                elif synthesis_entries:
                    source = "aggregate_memory"
                elif evidence_entries:
                    source = "evidence_memory"
                answer_candidate = build_answer_candidate(
                    question.question,
                    answer_text,
                    source=source,
                    metadata={"question_id": question.question_id},
                )
                answer_candidates.append(answer_candidate)
                context_blocks.append(f"answer_candidate: {answer_candidate.text}")

            packets.append(
                BaselinePromptPacket(
                    benchmark_name=sample.benchmark_name,
                    baseline_name="summary_synthesis_memory",
                    sample_id=sample.sample_id,
                    question_id=question.question_id,
                    question=question.question,
                    assembled_context="\n\n".join(context_blocks),
                    retrieved_context_items=retrieved_items,
                    metadata={
                        "route": "summary_synthesis_memory",
                        "max_observations": observation_limit,
                        "max_reflections": reflection_limit,
                        "max_topic_support": max_topic_support,
                        "primary_answer_candidate_type": answer_candidates[0].candidate_type if answer_candidates else None,
                    },
                    answer_candidates=answer_candidates,
                )
            )

    manifest = build_run_manifest(
        samples,
        baseline_name="summary_synthesis_memory",
        run_id=run_id,
        metadata={
            "baseline_type": "candidate_memory_system",
            "system_name": "Summary Synthesis Memory",
            "max_observations": max_observations,
            "max_reflections": max_reflections,
            "max_topic_support": max_topic_support,
        },
    )
    return manifest.to_dict(), packets
