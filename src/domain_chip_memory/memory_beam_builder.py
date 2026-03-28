from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .contracts import NormalizedBenchmarkSample, NormalizedQuestion
from .runs import BaselinePromptPacket, RetrievedContextItem


def build_beam_ready_temporal_atom_router_packets(
    samples: list[NormalizedBenchmarkSample],
    *,
    top_k_atoms: int,
    include_rehydrated_sessions: int,
    run_id: str,
    extract_memory_atoms: Callable[[NormalizedBenchmarkSample], list[Any]],
    session_lookup: Callable[[NormalizedBenchmarkSample], dict[str, Any]],
    choose_atoms: Callable[[NormalizedQuestion, list[Any], int], list[Any]],
    atom_score: Callable[[NormalizedQuestion, Any], float],
    serialize_session: Callable[[Any], str],
    should_use_current_state_exact_value: Callable[[NormalizedQuestion], bool],
    answer_candidate_surface_text: Callable[[str, str, str, str], str],
    build_answer_candidate: Callable[..., Any],
    build_run_manifest: Callable[..., Any],
    strategy_memory_role: Callable[[str], str],
) -> tuple[dict[str, Any], list[BaselinePromptPacket]]:
    packets: list[BaselinePromptPacket] = []
    for sample in samples:
        atoms = extract_memory_atoms(sample)
        sessions = session_lookup(sample)
        for question in sample.questions:
            chosen_atoms = choose_atoms(question, atoms, top_k_atoms)
            rehydrated_session_ids: list[str] = []
            for atom in chosen_atoms:
                if atom.session_id not in rehydrated_session_ids:
                    rehydrated_session_ids.append(atom.session_id)
            rehydrated_session_ids = rehydrated_session_ids[:include_rehydrated_sessions]

            retrieved_items: list[RetrievedContextItem] = []
            context_blocks: list[str] = []
            for atom in chosen_atoms:
                atom_line = f"memory: {atom.source_text}"
                context_blocks.append(atom_line)
                retrieved_items.append(
                    RetrievedContextItem(
                        session_id=atom.session_id,
                        turn_ids=[atom.turn_id],
                        score=atom_score(question, atom),
                        strategy="temporal_atom_router",
                        text=atom_line,
                        memory_role=strategy_memory_role("temporal_atom_router"),
                        metadata={
                            "atom_id": atom.atom_id,
                            "subject": atom.subject,
                            "predicate": atom.predicate,
                            "timestamp": atom.timestamp,
                        },
                    )
                )

            for session_id in rehydrated_session_ids:
                session = sessions[session_id]
                session_text = serialize_session(session)
                context_blocks.append(session_text)
                retrieved_items.append(
                    RetrievedContextItem(
                        session_id=session.session_id,
                        turn_ids=[turn.turn_id for turn in session.turns],
                        score=0.5,
                        strategy="source_rehydration",
                        text=session_text,
                        memory_role=strategy_memory_role("source_rehydration"),
                        metadata={"timestamp": session.timestamp},
                    )
                )

            if chosen_atoms:
                primary_atom = chosen_atoms[0]
                answer_text = (
                    primary_atom.value.strip()
                    if should_use_current_state_exact_value(question) and primary_atom.value
                    else answer_candidate_surface_text(
                        primary_atom.subject,
                        primary_atom.predicate,
                        primary_atom.value,
                        primary_atom.source_text,
                    )
                )
                answer_candidate = build_answer_candidate(
                    question.question,
                    answer_text,
                    source="temporal_atom_router",
                    metadata={"question_id": question.question_id},
                )
                context_blocks.append(f"answer_candidate: {answer_candidate.text}")
                answer_candidates = [answer_candidate]
            else:
                answer_candidates = []

            assembled_context = "\n\n".join(context_blocks)
            packets.append(
                BaselinePromptPacket(
                    benchmark_name=sample.benchmark_name,
                    baseline_name="beam_temporal_atom_router",
                    sample_id=sample.sample_id,
                    question_id=question.question_id,
                    question=question.question,
                    assembled_context=assembled_context,
                    retrieved_context_items=retrieved_items,
                    metadata={
                        "route": "temporal_atom_router",
                        "top_k_atoms": top_k_atoms,
                        "include_rehydrated_sessions": include_rehydrated_sessions,
                        "primary_answer_candidate_type": answer_candidates[0].candidate_type if answer_candidates else None,
                    },
                    answer_candidates=answer_candidates,
                )
            )

    manifest = build_run_manifest(
        samples,
        baseline_name="beam_temporal_atom_router",
        run_id=run_id,
        metadata={
            "baseline_type": "candidate_memory_system",
            "system_name": "Beam-Ready Temporal Atom Router",
            "top_k_atoms": top_k_atoms,
            "include_rehydrated_sessions": include_rehydrated_sessions,
        },
    )
    return manifest.to_dict(), packets
