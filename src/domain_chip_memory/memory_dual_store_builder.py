from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .contracts import AnswerCandidate, NormalizedBenchmarkSample, NormalizedQuestion
from .memory_builder_sections import append_retrieved_entries, build_entry_metadata
from .memory_extraction import ObservationEntry
from .runs import BaselinePromptPacket, RetrievedContextItem


def build_dual_store_event_calendar_hybrid_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    max_observations: int,
    top_k_events: int,
    max_topic_support: int,
    run_id: str,
    build_observation_log: Callable[[NormalizedBenchmarkSample], list[ObservationEntry]],
    reflect_observations: Callable[[list[ObservationEntry]], list[ObservationEntry]],
    build_event_calendar: Callable[[NormalizedBenchmarkSample], list[Any]],
    has_active_current_state_deletion: Callable[..., bool],
    is_current_state_question: Callable[[NormalizedQuestion], bool],
    question_subjects: Callable[[NormalizedQuestion], list[str]],
    question_predicates: Callable[[NormalizedQuestion], list[str]],
    observation_score: Callable[[NormalizedQuestion, ObservationEntry], float],
    event_score: Callable[[NormalizedQuestion, Any], float],
    select_current_state_entries: Callable[..., list[ObservationEntry]],
    topical_episode_support: Callable[..., tuple[str, list[ObservationEntry]]],
    select_evidence_entries: Callable[..., list[ObservationEntry]],
    dedupe_observations: Callable[[list[ObservationEntry]], list[ObservationEntry]],
    observation_evidence_text: Callable[[NormalizedQuestion, ObservationEntry], str],
    evidence_score: Callable[[NormalizedQuestion, ObservationEntry], float],
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
        reflected = reflect_observations(observations)
        events = build_event_calendar(sample)
        stable_window = sorted(
            observations,
            key=lambda entry: (entry.timestamp or "", entry.observation_id),
        )[-max_observations:]
        for question in sample.questions:
            current_state_deleted = has_active_current_state_deletion(
                question,
                observations,
                is_current_state_question=is_current_state_question,
                question_subjects=question_subjects,
                question_predicates=question_predicates,
            )
            ranked_reflections = sorted(
                reflected,
                key=lambda entry: (observation_score(question, entry), entry.timestamp or "", entry.observation_id),
                reverse=True,
            )[:2]
            current_state_entries = select_current_state_entries(
                question,
                reflected,
                limit=2,
                score_entry=lambda entry: observation_score(question, entry),
                preferred_predicates=set(question_predicates(question)),
            )
            ranked_events = sorted(
                events,
                key=lambda entry: (event_score(question, entry), entry.timestamp or "", entry.event_id),
                reverse=True,
            )[:top_k_events]
            topic_summary = ""
            topical_support: list[ObservationEntry] = []
            if sample.benchmark_name == "LoCoMo":
                topic_summary, topical_support = topical_episode_support(
                    question,
                    stable_window,
                    observations,
                    max_support=max_topic_support,
                )
            evidence_entries = select_evidence_entries(
                question,
                dedupe_observations([*stable_window, *topical_support, *observations]),
                limit=max(4, max_topic_support + 2),
            )

            context_blocks = ["stable_memory_window:"]
            retrieved_items: list[RetrievedContextItem] = []
            append_retrieved_entries(
                context_blocks,
                retrieved_items,
                stable_window,
                header=None,
                line_builder=lambda entry: f"observation: {entry.text}",
                score_builder=lambda _entry: 0.25,
                strategy="hybrid_observation_window",
                memory_role=strategy_memory_role("hybrid_observation_window"),
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
                ranked_events,
                header="event_calendar:",
                line_builder=lambda entry: f"event: {f'{entry.timestamp} ' if entry.timestamp else ''}{entry.text}",
                score_builder=lambda entry: event_score(question, entry),
                strategy="event_calendar",
                memory_role=strategy_memory_role("event_calendar"),
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

            raw_candidate_pool = [*stable_window, *ranked_events, *observations, *ranked_reflections]
            answer_text = choose_answer_candidate(
                question,
                evidence_entries,
                ranked_reflections,
                raw_candidate_pool if (is_dated_state_question(question) or is_relative_state_question(question)) else dedupe_observations(raw_candidate_pool),
            )
            ambiguous_relative_state = has_ambiguous_relative_state_anchor(question, raw_candidate_pool)
            referential_ambiguity = has_referential_ambiguity(question, raw_candidate_pool)
            answer_source = "evidence_memory" if evidence_entries else "belief_memory"
            if should_use_current_state_exact_value(question) and current_state_entries:
                current_state_value = str(current_state_entries[0].metadata.get("value", "")).strip()
                if current_state_value:
                    answer_text = current_state_value
                    answer_source = "current_state_memory"
            elif current_state_deleted:
                answer_text = "unknown"
                answer_source = "current_state_deletion"
            elif referential_ambiguity and answer_text.lower() == "unknown":
                answer_source = "referential_ambiguity"
            elif ambiguous_relative_state and answer_text.lower() == "unknown":
                answer_source = "temporal_ambiguity"
            if ranked_events:
                top_entry = ranked_events[0]
                answer_value = str(top_entry.metadata.get("value", "")).strip()
                event_answer_text = (
                    answer_value
                    if should_use_current_state_exact_value(question) and answer_value
                    else answer_candidate_surface_text(
                        top_entry.subject,
                        top_entry.predicate,
                        top_entry.metadata.get("value", ""),
                        top_entry.text,
                    )
                )
                if (
                    not question.should_abstain
                    and not current_state_deleted
                    and is_current_state_question(question)
                    and not current_state_entries
                    and "location" in question_predicates(question)
                    and event_answer_text
                ):
                    answer_text = event_answer_text
                    answer_source = "event_calendar"
                elif not answer_text and event_answer_text:
                    answer_text = event_answer_text
                    answer_source = "event_calendar"
            answer_candidates: list[AnswerCandidate] = []
            if answer_text:
                answer_candidate = build_answer_candidate(
                    question.question,
                    answer_text,
                    source=answer_source,
                    metadata={"question_id": question.question_id},
                )
                answer_candidates.append(answer_candidate)
                context_blocks.append(f"answer_candidate: {answer_candidate.text}")

            packets.append(
                BaselinePromptPacket(
                    benchmark_name=sample.benchmark_name,
                    baseline_name="dual_store_event_calendar_hybrid",
                    sample_id=sample.sample_id,
                    question_id=question.question_id,
                    question=question.question,
                    assembled_context="\n\n".join(context_blocks),
                    retrieved_context_items=retrieved_items,
                    metadata={
                        "route": "dual_store_event_calendar_hybrid",
                        "max_observations": max_observations,
                        "top_k_events": top_k_events,
                        "max_topic_support": max_topic_support,
                        "primary_answer_candidate_type": answer_candidates[0].candidate_type if answer_candidates else None,
                    },
                    answer_candidates=answer_candidates,
                )
            )

    manifest = build_run_manifest(
        samples,
        baseline_name="dual_store_event_calendar_hybrid",
        run_id=run_id,
        metadata={
            "baseline_type": "candidate_memory_system",
            "system_name": "Dual-Store Event Calendar Hybrid",
            "max_observations": max_observations,
            "top_k_events": top_k_events,
            "max_topic_support": max_topic_support,
        },
    )
    return manifest.to_dict(), packets
