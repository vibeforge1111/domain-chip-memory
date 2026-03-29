from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .contracts import AnswerCandidate, NormalizedBenchmarkSample, NormalizedQuestion
from .memory_builder_sections import append_retrieved_entries, build_entry_metadata
from .memory_extraction import EventCalendarEntry, ObservationEntry
from .runs import BaselinePromptPacket, RetrievedContextItem


def _event_as_observation(entry: EventCalendarEntry) -> ObservationEntry:
    metadata = dict(entry.metadata)
    metadata.setdefault("source_text", entry.text)
    metadata["event_id"] = entry.event_id
    metadata["rehydrated_from"] = "event_calendar"
    return ObservationEntry(
        observation_id=f"{entry.event_id}:typed-event",
        subject=entry.subject,
        predicate=entry.predicate,
        text=entry.text,
        session_id=entry.session_id,
        turn_ids=list(entry.turn_ids),
        timestamp=entry.timestamp,
        metadata=metadata,
    )


def _compact_observation(
    entry: ObservationEntry,
    *,
    answer_candidate_surface_text: Callable[[str, str, str, str], str],
) -> ObservationEntry:
    metadata = dict(entry.metadata)
    source_text = str(metadata.get("source_text", "")).strip() or entry.text
    value = str(metadata.get("value", "")).strip()
    compact_text = answer_candidate_surface_text(entry.subject, entry.predicate, value, source_text).strip()
    if not compact_text:
        compact_text = value or entry.text
    if value and (compact_text == source_text or len(compact_text) > max(120, len(value) * 3)):
        compact_text = value
    metadata["source_text"] = source_text
    metadata["typed_state_surface"] = compact_text
    metadata["typed_state_compact"] = True
    return ObservationEntry(
        observation_id=f"{entry.observation_id}:typed",
        subject=entry.subject,
        predicate=entry.predicate,
        text=compact_text,
        session_id=entry.session_id,
        turn_ids=list(entry.turn_ids),
        timestamp=entry.timestamp,
        metadata=metadata,
    )


def build_typed_state_update_memory_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    max_observations: int,
    max_reflections: int,
    top_k_events: int,
    max_topic_support: int,
    run_id: str,
    build_observation_log: Callable[[NormalizedBenchmarkSample], list[ObservationEntry]],
    reflect_observations: Callable[[list[ObservationEntry]], list[ObservationEntry]],
    build_event_calendar: Callable[[NormalizedBenchmarkSample], list[EventCalendarEntry]],
    raw_user_turn_entries: Callable[[NormalizedBenchmarkSample], list[ObservationEntry]],
    build_current_state_view: Callable[[list[ObservationEntry]], list[ObservationEntry]],
    has_active_current_state_deletion: Callable[..., bool],
    is_current_state_question: Callable[[NormalizedQuestion], bool],
    question_subjects: Callable[[NormalizedQuestion], list[str]],
    question_predicates: Callable[[NormalizedQuestion], list[str]],
    question_aware_observation_limits: Callable[..., tuple[int, int]],
    is_preference_question: Callable[[NormalizedQuestion], bool],
    select_preference_support_entries: Callable[..., list[ObservationEntry]],
    observation_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    event_score: Callable[[NormalizedQuestion, EventCalendarEntry], float],
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
    answer_candidate_surface_text: Callable[[str, str, str, str], str],
    build_answer_candidate: Callable[..., AnswerCandidate],
    build_run_manifest: Callable[..., Any],
    strategy_memory_role: Callable[[str], str],
) -> tuple[dict[str, Any], list[BaselinePromptPacket]]:
    packets: list[BaselinePromptPacket] = []
    for sample in samples:
        observations = build_observation_log(sample)
        raw_entries = raw_user_turn_entries(sample)
        events = build_event_calendar(sample)
        event_observations = [_event_as_observation(entry) for entry in events]
        merged_updates = dedupe_observations([*event_observations, *observations])
        typed_state_view = [
            _compact_observation(entry, answer_candidate_surface_text=answer_candidate_surface_text)
            for entry in build_current_state_view(merged_updates)
            if entry.predicate != "raw_turn"
        ]
        reflected = [
            _compact_observation(entry, answer_candidate_surface_text=answer_candidate_surface_text)
            for entry in reflect_observations(observations)
            if entry.predicate != "raw_turn"
        ]
        for question in sample.questions:
            current_state_deleted = has_active_current_state_deletion(
                question,
                merged_updates,
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
                preference_support = [
                    _compact_observation(entry, answer_candidate_surface_text=answer_candidate_surface_text)
                    for entry in select_preference_support_entries(
                        question,
                        raw_entries,
                        limit=observation_limit,
                    )
                ]
            stable_window = dedupe_observations(
                sorted(
                    typed_state_view,
                    key=lambda entry: (
                        evidence_score(question, entry),
                        observation_score(question, entry),
                        entry.timestamp or "",
                        entry.observation_id,
                    ),
                    reverse=True,
                )
            )[:observation_limit]
            ranked_reflections = sorted(
                reflected,
                key=lambda entry: (observation_score(question, entry), entry.timestamp or "", entry.observation_id),
                reverse=True,
            )[:reflection_limit]
            ranked_events = sorted(
                events,
                key=lambda entry: (event_score(question, entry), entry.timestamp or "", entry.event_id),
                reverse=True,
            )[:top_k_events]
            typed_ranked_events = [
                _compact_observation(_event_as_observation(entry), answer_candidate_surface_text=answer_candidate_surface_text)
                for entry in ranked_events
            ]
            current_state_entries = select_current_state_entries(
                question,
                typed_state_view,
                limit=3,
                score_entry=lambda entry: observation_score(question, entry),
                preferred_predicates=set(question_predicates(question)),
            )
            topic_summary = ""
            topical_support: list[ObservationEntry] = []
            if sample.benchmark_name == "LoCoMo":
                topic_summary, raw_topical_support = topical_episode_support(
                    question,
                    observations[:observation_limit] if observations else observations,
                    observations,
                    max_support=max_topic_support,
                )
                topical_support = [
                    _compact_observation(entry, answer_candidate_surface_text=answer_candidate_surface_text)
                    for entry in raw_topical_support
                ]
            typed_updates = [
                _compact_observation(entry, answer_candidate_surface_text=answer_candidate_surface_text)
                for entry in merged_updates
                if entry.predicate != "raw_turn"
            ]
            update_history = dedupe_observations(
                sorted(
                    [
                        entry
                        for entry in typed_updates
                        if evidence_score(question, entry) > 0 or observation_score(question, entry) > 0
                    ],
                    key=lambda entry: (
                        evidence_score(question, entry),
                        observation_score(question, entry),
                        entry.timestamp or "",
                        entry.observation_id,
                    ),
                    reverse=True,
                )
            )[: max(observation_limit, 4)]
            evidence_pool = dedupe_observations(
                [
                    *current_state_entries,
                    *update_history,
                    *typed_ranked_events,
                    *preference_support,
                    *stable_window,
                    *topical_support,
                    *typed_state_view,
                ]
            )
            evidence_entries = select_evidence_entries(
                question,
                evidence_pool,
                limit=max(5, max_topic_support + 3),
            )
            candidate_pool = dedupe_observations(
                [
                    *current_state_entries,
                    *update_history,
                    *typed_ranked_events,
                    *preference_support,
                    *stable_window,
                    *topical_support,
                    *typed_state_view,
                    *ranked_reflections,
                ]
            )
            answer_context_entries = dedupe_observations(
                [
                    *current_state_entries,
                    *evidence_entries,
                    *typed_ranked_events,
                    *preference_support,
                    *topical_support,
                    *stable_window,
                    *ranked_reflections,
                ]
            )
            aggregate_pool = candidate_pool
            if sample.benchmark_name == "LongMemEval" and question_needs_raw_aggregate_context(question):
                aggregate_pool = dedupe_observations([*candidate_pool, *raw_entries])
            aggregate_support_entries = (
                select_aggregate_support_entries(question, aggregate_pool)
                if sample.benchmark_name == "LongMemEval"
                else []
            )

            context_blocks = ["typed_state_memory:"]
            retrieved_items: list[RetrievedContextItem] = []
            append_retrieved_entries(
                context_blocks,
                retrieved_items,
                stable_window,
                header=None,
                line_builder=lambda entry: f"state: {entry.text}",
                score_builder=lambda entry: observation_score(question, entry),
                strategy="typed_state_memory",
                memory_role=strategy_memory_role("typed_state_memory"),
                metadata_builder=build_entry_metadata,
            )

            if update_history:
                append_retrieved_entries(
                    context_blocks,
                    retrieved_items,
                    update_history,
                    header="update_history:",
                    line_builder=lambda entry: f"update: {entry.text}",
                    score_builder=lambda entry: observation_score(question, entry),
                    strategy="typed_update_history",
                    memory_role=strategy_memory_role("typed_update_history"),
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

            if typed_ranked_events:
                append_retrieved_entries(
                    context_blocks,
                    retrieved_items,
                    typed_ranked_events,
                    header="event_calendar:",
                    line_builder=lambda entry: f"event: {entry.text}",
                    score_builder=lambda entry: observation_score(question, entry),
                    strategy="event_calendar",
                    memory_role=strategy_memory_role("event_calendar"),
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
                metadata_builder=build_entry_metadata,
            )

            answer_text = choose_answer_candidate(
                question,
                evidence_entries,
                ranked_reflections,
                candidate_pool if (is_dated_state_question(question) or is_relative_state_question(question)) else answer_context_entries,
                aggregate_pool,
            )
            ambiguous_relative_state = has_ambiguous_relative_state_anchor(question, candidate_pool)
            referential_ambiguity = has_referential_ambiguity(question, candidate_pool)
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
                elif aggregate_support_entries:
                    source = "aggregate_memory"
                elif current_state_entries:
                    source = "typed_state_memory"
                elif update_history:
                    source = "typed_update_history"
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
                    baseline_name="typed_state_update_memory",
                    sample_id=sample.sample_id,
                    question_id=question.question_id,
                    question=question.question,
                    assembled_context="\n\n".join(context_blocks),
                    retrieved_context_items=retrieved_items,
                    metadata={
                        "route": "typed_state_update_memory",
                        "max_observations": max_observations,
                        "max_reflections": max_reflections,
                        "top_k_events": top_k_events,
                        "max_topic_support": max_topic_support,
                        "primary_answer_candidate_type": answer_candidates[0].candidate_type if answer_candidates else None,
                    },
                    answer_candidates=answer_candidates,
                )
            )

    manifest = build_run_manifest(
        samples,
        baseline_name="typed_state_update_memory",
        run_id=run_id,
        metadata={
            "baseline_type": "candidate_memory_system",
            "system_name": "Typed State Update Memory",
            "max_observations": max_observations,
            "max_reflections": max_reflections,
            "top_k_events": top_k_events,
            "max_topic_support": max_topic_support,
        },
    )
    return manifest.to_dict(), packets
