from __future__ import annotations

from .contracts import (
    NormalizedBenchmarkSample,
    NormalizedQuestion,
    NormalizedSession,
    NormalizedTurn,
)


def demo_samples() -> list[NormalizedBenchmarkSample]:
    return [
        NormalizedBenchmarkSample(
            benchmark_name="LongMemEval",
            sample_id="demo-longmemeval-1",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2024-04-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="I live in London."),
                        NormalizedTurn(turn_id="s1:t2", speaker="assistant", text="Noted."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2024-04-20",
                    turns=[
                        NormalizedTurn(turn_id="s2:t1", speaker="user", text="I moved to Dubai."),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="Updated."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="demo-longmemeval-1:q1",
                    question="Where do I live now?",
                    category="knowledge-update",
                    expected_answers=["Dubai"],
                    evidence_session_ids=["s2"],
                    evidence_turn_ids=["s2:t1"],
                )
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="LoCoMo",
            sample_id="demo-locomo-1",
            sessions=[
                NormalizedSession(
                    session_id="session_1",
                    timestamp="2024-01-01",
                    turns=[
                        NormalizedTurn(turn_id="d1", speaker="Alice", text="I like jazz."),
                        NormalizedTurn(turn_id="d2", speaker="Bob", text="Cool."),
                    ],
                ),
                NormalizedSession(
                    session_id="session_2",
                    timestamp="2024-01-10",
                    turns=[
                        NormalizedTurn(turn_id="d3", speaker="Alice", text="I now prefer techno."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="demo-locomo-1:q1",
                    question="What music does Alice prefer now?",
                    category="temporal",
                    expected_answers=["techno"],
                    evidence_session_ids=["session_2"],
                    evidence_turn_ids=["d3"],
                )
            ],
        ),
    ]


def product_memory_samples() -> list[NormalizedBenchmarkSample]:
    return [
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-correction-1",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2025-04-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="My favorite color is blue."),
                        NormalizedTurn(turn_id="s1:t2", speaker="assistant", text="Noted."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2025-04-10",
                    turns=[
                        NormalizedTurn(
                            turn_id="s2:t1",
                            speaker="user",
                            text="Correction: my favorite color is green.",
                        ),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="Updated."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-correction-1:q1",
                    question="What is my favorite color now?",
                    category="current_state",
                    expected_answers=["green"],
                    evidence_session_ids=["s2"],
                    evidence_turn_ids=["s2:t1"],
                    metadata={
                        "product_memory_task": "correction",
                        "memory_operation": "update",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "current_state_memory",
                    },
                )
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-deletion-1",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2025-05-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="I live in Dubai."),
                        NormalizedTurn(turn_id="s1:t2", speaker="assistant", text="Saved."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2025-05-03",
                    turns=[
                        NormalizedTurn(
                            turn_id="s2:t1",
                            speaker="user",
                            text="Please forget that I live in Dubai.",
                        ),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="I will treat that as deleted."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-deletion-1:q1",
                    question="Where do I live now?",
                    category="abstention",
                    expected_answers=["Information provided is not enough"],
                    evidence_session_ids=["s2"],
                    evidence_turn_ids=["s2:t1"],
                    should_abstain=True,
                    metadata={
                        "product_memory_task": "deletion",
                        "memory_operation": "delete",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "current_state_deletion",
                    },
                )
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-stale-state-1",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2025-06-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="I prefer espresso."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2025-06-10",
                    turns=[
                        NormalizedTurn(turn_id="s2:t1", speaker="user", text="I prefer matcha now."),
                    ],
                ),
                NormalizedSession(
                    session_id="s3",
                    timestamp="2025-06-20",
                    turns=[
                        NormalizedTurn(turn_id="s3:t1", speaker="user", text="I switched back to espresso."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-stale-state-1:q1",
                    question="What do I prefer now?",
                    category="current_state",
                    expected_answers=["espresso"],
                    evidence_session_ids=["s3"],
                    evidence_turn_ids=["s3:t1"],
                    metadata={
                        "product_memory_task": "stale_state_drift",
                        "memory_operation": "supersession",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "current_state_memory",
                    },
                )
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-deletion-2",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2025-07-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="My favorite color is blue."),
                        NormalizedTurn(turn_id="s1:t2", speaker="assistant", text="Saved."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2025-07-03",
                    turns=[
                        NormalizedTurn(
                            turn_id="s2:t1",
                            speaker="user",
                            text="Please forget my favorite color.",
                        ),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="I will stop using that memory."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-deletion-2:q1",
                    question="What is my favorite color now?",
                    category="abstention",
                    expected_answers=["Information provided is not enough"],
                    evidence_session_ids=["s2"],
                    evidence_turn_ids=["s2:t1"],
                    should_abstain=True,
                    metadata={
                        "product_memory_task": "deletion",
                        "memory_operation": "delete",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "current_state_deletion",
                    },
                )
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-correction-2",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2025-08-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="I live in Dubai."),
                        NormalizedTurn(turn_id="s1:t2", speaker="assistant", text="Saved."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2025-08-03",
                    turns=[
                        NormalizedTurn(
                            turn_id="s2:t1",
                            speaker="user",
                            text="Please forget where I live.",
                        ),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="Deleted."),
                    ],
                ),
                NormalizedSession(
                    session_id="s3",
                    timestamp="2025-08-07",
                    turns=[
                        NormalizedTurn(turn_id="s3:t1", speaker="user", text="I moved to Sharjah."),
                        NormalizedTurn(turn_id="s3:t2", speaker="assistant", text="Updated."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-correction-2:q1",
                    question="Where do I live now?",
                    category="current_state",
                    expected_answers=["Sharjah"],
                    evidence_session_ids=["s3"],
                    evidence_turn_ids=["s3:t1"],
                    metadata={
                        "product_memory_task": "correction",
                        "memory_operation": "update_after_delete",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "current_state_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-correction-2:q2",
                    question="Where did I live before moving to Sharjah?",
                    category="historical_state",
                    expected_answers=["Dubai"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "evidence_preservation",
                        "memory_operation": "historical_pre_update_recall",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-correction-2:q3",
                    question="Where did I live before I forgot it?",
                    category="historical_state",
                    expected_answers=["Dubai"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "evidence_preservation",
                        "memory_operation": "historical_pre_delete_recall",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-correction-2:q4",
                    question="Where did I live before I deleted where I live?",
                    category="historical_state",
                    expected_answers=["Dubai"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "evidence_preservation",
                        "memory_operation": "historical_pre_delete_slot_recall",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-correction-2:q5",
                    question="Where did I live before I changed where I live to Sharjah?",
                    category="historical_state",
                    expected_answers=["Dubai"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "evidence_preservation",
                        "memory_operation": "historical_pre_slot_update_recall",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-correction-2:q6",
                    question="Before I changed where I live to Sharjah, where did I live?",
                    category="historical_state",
                    expected_answers=["Dubai"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "evidence_preservation",
                        "memory_operation": "historical_fronted_clause_recall",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-correction-2:q7",
                    question="Before I changed where I live to Sharjah, back when the old place was still current, where did I live?",
                    category="historical_state",
                    expected_answers=["Dubai"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "evidence_preservation",
                        "memory_operation": "historical_multiclause_recall",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-correction-2:q8",
                    question="Before that move, where did I live?",
                    category="historical_state",
                    expected_answers=["Dubai"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "evidence_preservation",
                        "memory_operation": "historical_anaphoric_anchor_recall",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-deletion-3",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2025-09-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="I live in Dubai."),
                        NormalizedTurn(turn_id="s1:t2", speaker="user", text="My favorite color is blue."),
                        NormalizedTurn(turn_id="s1:t3", speaker="assistant", text="Saved both."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2025-09-03",
                    turns=[
                        NormalizedTurn(
                            turn_id="s2:t1",
                            speaker="user",
                            text="Please forget where I live.",
                        ),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="Deleted location only."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-deletion-3:q1",
                    question="Where do I live now?",
                    category="abstention",
                    expected_answers=["Information provided is not enough"],
                    evidence_session_ids=["s2"],
                    evidence_turn_ids=["s2:t1"],
                    should_abstain=True,
                    metadata={
                        "product_memory_task": "deletion",
                        "memory_operation": "delete_one_facet",
                        "memory_scope": "multi_facet",
                        "expected_answer_candidate_source": "current_state_deletion",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-deletion-3:q2",
                    question="What is my favorite color now?",
                    category="current_state",
                    expected_answers=["blue"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t2"],
                    metadata={
                        "product_memory_task": "correction",
                        "memory_operation": "preserve_other_facet_after_delete",
                        "memory_scope": "multi_facet",
                        "expected_answer_candidate_source": "current_state_memory",
                    },
                ),
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-correction-3",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2025-10-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="My favorite color is red."),
                        NormalizedTurn(turn_id="s1:t2", speaker="assistant", text="Saved."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2025-10-04",
                    turns=[
                        NormalizedTurn(
                            turn_id="s2:t1",
                            speaker="user",
                            text="Please forget my favorite color.",
                        ),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="Deleted."),
                    ],
                ),
                NormalizedSession(
                    session_id="s3",
                    timestamp="2025-10-06",
                    turns=[
                        NormalizedTurn(turn_id="s3:t1", speaker="user", text="Correction: my favorite color is green."),
                        NormalizedTurn(turn_id="s3:t2", speaker="assistant", text="Updated."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-correction-3:q1",
                    question="What is my favorite color now?",
                    category="current_state",
                    expected_answers=["green"],
                    evidence_session_ids=["s3"],
                    evidence_turn_ids=["s3:t1"],
                    metadata={
                        "product_memory_task": "correction",
                        "memory_operation": "update_deleted_predicate",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "current_state_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-correction-3:q2",
                    question="What was my favorite color before I corrected it to green?",
                    category="historical_state",
                    expected_answers=["red"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "evidence_preservation",
                        "memory_operation": "historical_pre_correction_recall",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-correction-3:q3",
                    question="What was my favorite color before I changed it to green?",
                    category="historical_state",
                    expected_answers=["red"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "evidence_preservation",
                        "memory_operation": "historical_pre_change_recall",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-correction-3:q4",
                    question="What was my favorite color before I updated my favorite color to green?",
                    category="historical_state",
                    expected_answers=["red"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "evidence_preservation",
                        "memory_operation": "historical_pre_slot_update_recall",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-correction-3:q5",
                    question="Before I changed my favorite color to green, what was my favorite color?",
                    category="historical_state",
                    expected_answers=["red"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "evidence_preservation",
                        "memory_operation": "historical_fronted_clause_recall",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-correction-3:q6",
                    question="Before I changed my favorite color to green, when we were still using the old one, what was my favorite color?",
                    category="historical_state",
                    expected_answers=["red"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "evidence_preservation",
                        "memory_operation": "historical_multiclause_recall",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-correction-3:q7",
                    question="What was my favorite color before that update?",
                    category="historical_state",
                    expected_answers=["red"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "evidence_preservation",
                        "memory_operation": "historical_anaphoric_anchor_recall",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-correction-4",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2025-11-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="I prefer espresso."),
                        NormalizedTurn(turn_id="s1:t2", speaker="user", text="My favorite color is blue."),
                        NormalizedTurn(turn_id="s1:t3", speaker="assistant", text="Saved both."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2025-11-04",
                    turns=[
                        NormalizedTurn(
                            turn_id="s2:t1",
                            speaker="user",
                            text="Correction: I prefer matcha now.",
                        ),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="Updated."),
                    ],
                ),
                NormalizedSession(
                    session_id="s3",
                    timestamp="2025-11-06",
                    turns=[
                        NormalizedTurn(
                            turn_id="s3:t1",
                            speaker="user",
                            text="Actually no, I prefer espresso again.",
                        ),
                        NormalizedTurn(turn_id="s3:t2", speaker="assistant", text="Rolled back."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-correction-4:q1",
                    question="What do I prefer now?",
                    category="current_state",
                    expected_answers=["espresso"],
                    evidence_session_ids=["s3"],
                    evidence_turn_ids=["s3:t1"],
                    metadata={
                        "product_memory_task": "correction",
                        "memory_operation": "rollback_to_prior_value",
                        "memory_scope": "multi_facet",
                        "expected_answer_candidate_source": "current_state_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-correction-4:q2",
                    question="What is my favorite color now?",
                    category="current_state",
                    expected_answers=["blue"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t2"],
                    metadata={
                        "product_memory_task": "correction",
                        "memory_operation": "preserve_other_facet_after_rollback",
                        "memory_scope": "multi_facet",
                        "expected_answer_candidate_source": "current_state_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-correction-4:q3",
                    question="Before I changed what I prefer to espresso again, what did I prefer?",
                    category="historical_state",
                    expected_answers=["matcha"],
                    evidence_session_ids=["s2"],
                    evidence_turn_ids=["s2:t1"],
                    metadata={
                        "product_memory_task": "evidence_preservation",
                        "memory_operation": "historical_fronted_clause_recall",
                        "memory_scope": "multi_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-correction-4:q4",
                    question="Before I changed what I prefer to espresso again, back when the old preference still applied, what did I prefer?",
                    category="historical_state",
                    expected_answers=["matcha"],
                    evidence_session_ids=["s2"],
                    evidence_turn_ids=["s2:t1"],
                    metadata={
                        "product_memory_task": "evidence_preservation",
                        "memory_operation": "historical_multiclause_recall",
                        "memory_scope": "multi_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-correction-4:q5",
                    question="What did I prefer before that update?",
                    category="historical_state",
                    expected_answers=["Information provided is not enough"],
                    evidence_session_ids=["s2"],
                    evidence_turn_ids=["s2:t1"],
                    should_abstain=True,
                    metadata={
                        "product_memory_task": "ambiguity_abstention",
                        "memory_operation": "historical_ambiguous_anchor_abstention",
                        "memory_scope": "multi_facet",
                        "expected_answer_candidate_source": "temporal_ambiguity",
                    },
                ),
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-correction-5",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2025-12-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="My favorite color is red."),
                        NormalizedTurn(turn_id="s1:t2", speaker="assistant", text="Saved."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2025-12-03",
                    turns=[
                        NormalizedTurn(
                            turn_id="s2:t1",
                            speaker="user",
                            text="Please forget my favorite color.",
                        ),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="Deleted."),
                    ],
                ),
                NormalizedSession(
                    session_id="s3",
                    timestamp="2025-12-05",
                    turns=[
                        NormalizedTurn(
                            turn_id="s3:t1",
                            speaker="user",
                            text="Actually, my favorite color is red again.",
                        ),
                        NormalizedTurn(turn_id="s3:t2", speaker="assistant", text="Restored."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-correction-5:q1",
                    question="What is my favorite color now?",
                    category="current_state",
                    expected_answers=["red"],
                    evidence_session_ids=["s3"],
                    evidence_turn_ids=["s3:t1"],
                    metadata={
                        "product_memory_task": "correction",
                        "memory_operation": "restore_deleted_value",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "current_state_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-correction-5:q2",
                    question="What was my favorite color before I deleted it?",
                    category="historical_state",
                    expected_answers=["red"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "evidence_preservation",
                        "memory_operation": "historical_pre_delete_recall",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-ambiguity-1",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2026-01-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="I live in Dubai."),
                        NormalizedTurn(turn_id="s1:t2", speaker="assistant", text="Saved."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2026-01-04",
                    turns=[
                        NormalizedTurn(turn_id="s2:t1", speaker="user", text="I moved to Sharjah."),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="Updated."),
                    ],
                ),
                NormalizedSession(
                    session_id="s3",
                    timestamp="2026-01-08",
                    turns=[
                        NormalizedTurn(turn_id="s3:t1", speaker="user", text="I moved to Abu Dhabi."),
                        NormalizedTurn(turn_id="s3:t2", speaker="assistant", text="Updated again."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-ambiguity-1:q1",
                    question="Where did I live before that move?",
                    category="historical_state",
                    expected_answers=["Information provided is not enough"],
                    evidence_session_ids=["s1", "s2", "s3"],
                    evidence_turn_ids=["s1:t1", "s2:t1", "s3:t1"],
                    should_abstain=True,
                    metadata={
                        "product_memory_task": "ambiguity_abstention",
                        "memory_operation": "historical_ambiguous_anchor_abstention",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "temporal_ambiguity",
                    },
                )
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-ambiguity-2",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2026-02-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="My favorite color is red."),
                        NormalizedTurn(turn_id="s1:t2", speaker="assistant", text="Saved."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2026-02-04",
                    turns=[
                        NormalizedTurn(turn_id="s2:t1", speaker="user", text="Correction: my favorite color is green."),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="Updated."),
                    ],
                ),
                NormalizedSession(
                    session_id="s3",
                    timestamp="2026-02-08",
                    turns=[
                        NormalizedTurn(turn_id="s3:t1", speaker="user", text="Actually, my favorite color is yellow now."),
                        NormalizedTurn(turn_id="s3:t2", speaker="assistant", text="Updated again."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-ambiguity-2:q1",
                    question="What was my favorite color before that change?",
                    category="historical_state",
                    expected_answers=["Information provided is not enough"],
                    evidence_session_ids=["s1", "s2", "s3"],
                    evidence_turn_ids=["s1:t1", "s2:t1", "s3:t1"],
                    should_abstain=True,
                    metadata={
                        "product_memory_task": "ambiguity_abstention",
                        "memory_operation": "historical_ambiguous_anchor_abstention",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "temporal_ambiguity",
                    },
                )
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-disambiguation-1",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2026-03-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="My favorite color is red."),
                        NormalizedTurn(turn_id="s1:t2", speaker="assistant", text="Saved."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2026-03-04",
                    turns=[
                        NormalizedTurn(
                            turn_id="s2:t1",
                            speaker="user",
                            text="Correction: my favorite color is green.",
                        ),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="Updated color."),
                    ],
                ),
                NormalizedSession(
                    session_id="s3",
                    timestamp="2026-03-07",
                    turns=[
                        NormalizedTurn(turn_id="s3:t1", speaker="user", text="I moved to Sharjah."),
                        NormalizedTurn(turn_id="s3:t2", speaker="assistant", text="Updated location."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-disambiguation-1:q1",
                    question="What was my favorite color before that change?",
                    category="historical_state",
                    expected_answers=["red"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "cross_facet_disambiguation",
                        "memory_operation": "historical_cross_facet_anchor_binding",
                        "memory_scope": "multi_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                )
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-disambiguation-2",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2026-04-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="I live in Dubai."),
                        NormalizedTurn(turn_id="s1:t2", speaker="assistant", text="Saved."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2026-04-04",
                    turns=[
                        NormalizedTurn(turn_id="s2:t1", speaker="user", text="I moved to Sharjah."),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="Updated location."),
                    ],
                ),
                NormalizedSession(
                    session_id="s3",
                    timestamp="2026-04-07",
                    turns=[
                        NormalizedTurn(turn_id="s3:t1", speaker="user", text="My favorite color is blue."),
                        NormalizedTurn(turn_id="s3:t2", speaker="assistant", text="Updated color."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-disambiguation-2:q1",
                    question="Where did I live before that change?",
                    category="historical_state",
                    expected_answers=["Dubai"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "cross_facet_disambiguation",
                        "memory_operation": "historical_cross_facet_anchor_binding",
                        "memory_scope": "multi_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                )
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-operation-binding-1",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2026-05-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="My favorite color is red."),
                        NormalizedTurn(turn_id="s1:t2", speaker="assistant", text="Saved."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2026-05-03",
                    turns=[
                        NormalizedTurn(turn_id="s2:t1", speaker="user", text="Please forget my favorite color."),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="Deleted."),
                    ],
                ),
                NormalizedSession(
                    session_id="s3",
                    timestamp="2026-05-06",
                    turns=[
                        NormalizedTurn(turn_id="s3:t1", speaker="user", text="Correction: my favorite color is green."),
                        NormalizedTurn(turn_id="s3:t2", speaker="assistant", text="Updated."),
                    ],
                ),
                NormalizedSession(
                    session_id="s4",
                    timestamp="2026-05-09",
                    turns=[
                        NormalizedTurn(turn_id="s4:t1", speaker="user", text="Actually, my favorite color is yellow now."),
                        NormalizedTurn(turn_id="s4:t2", speaker="assistant", text="Updated again."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-operation-binding-1:q1",
                    question="What was my favorite color before that deletion?",
                    category="historical_state",
                    expected_answers=["red"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "operation_disambiguation",
                        "memory_operation": "historical_delete_anchor_binding",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                )
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-operation-binding-2",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2026-06-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="I live in Dubai."),
                        NormalizedTurn(turn_id="s1:t2", speaker="assistant", text="Saved."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2026-06-03",
                    turns=[
                        NormalizedTurn(turn_id="s2:t1", speaker="user", text="Please forget where I live."),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="Deleted."),
                    ],
                ),
                NormalizedSession(
                    session_id="s3",
                    timestamp="2026-06-06",
                    turns=[
                        NormalizedTurn(turn_id="s3:t1", speaker="user", text="I moved to Sharjah."),
                        NormalizedTurn(turn_id="s3:t2", speaker="assistant", text="Updated."),
                    ],
                ),
                NormalizedSession(
                    session_id="s4",
                    timestamp="2026-06-09",
                    turns=[
                        NormalizedTurn(turn_id="s4:t1", speaker="user", text="I moved to Abu Dhabi."),
                        NormalizedTurn(turn_id="s4:t2", speaker="assistant", text="Updated again."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-operation-binding-2:q1",
                    question="Where did I live before that deletion?",
                    category="historical_state",
                    expected_answers=["Dubai"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "operation_disambiguation",
                        "memory_operation": "historical_delete_anchor_binding",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                )
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-dense-turn-1",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2026-07-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="My favorite color is red."),
                        NormalizedTurn(turn_id="s1:t2", speaker="assistant", text="Saved."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2026-07-03",
                    turns=[
                        NormalizedTurn(
                            turn_id="s2:t1",
                            speaker="user",
                            text="Please forget my favorite color, and after that my favorite color is green.",
                        ),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="Deleted then updated."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-dense-turn-1:q1",
                    question="What was my favorite color before that deletion?",
                    category="historical_state",
                    expected_answers=["red"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "dense_turn_disambiguation",
                        "memory_operation": "historical_dense_turn_delete_binding",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-dense-turn-1:q2",
                    question="What was my favorite color before that update?",
                    category="historical_state",
                    expected_answers=["red"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "dense_turn_disambiguation",
                        "memory_operation": "historical_dense_turn_update_binding",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-dense-turn-2",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2026-08-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="I live in Dubai."),
                        NormalizedTurn(turn_id="s1:t2", speaker="assistant", text="Saved."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2026-08-03",
                    turns=[
                        NormalizedTurn(
                            turn_id="s2:t1",
                            speaker="user",
                            text="Please forget where I live, and after that I moved to Sharjah.",
                        ),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="Deleted then updated."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-dense-turn-2:q1",
                    question="Where did I live before that deletion?",
                    category="historical_state",
                    expected_answers=["Dubai"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "dense_turn_disambiguation",
                        "memory_operation": "historical_dense_turn_delete_binding",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-dense-turn-2:q2",
                    question="Where did I live before that update?",
                    category="historical_state",
                    expected_answers=["Dubai"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "dense_turn_disambiguation",
                        "memory_operation": "historical_dense_turn_update_binding",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-pronoun-turn-1",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2026-09-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="My favorite color is red."),
                        NormalizedTurn(turn_id="s1:t2", speaker="assistant", text="Saved."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2026-09-03",
                    turns=[
                        NormalizedTurn(
                            turn_id="s2:t1",
                            speaker="user",
                            text="About my favorite color, please forget it, and after that change it to green.",
                        ),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="Deleted then updated."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-pronoun-turn-1:q1",
                    question="What was my favorite color before that deletion?",
                    category="historical_state",
                    expected_answers=["red"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "pronoun_turn_disambiguation",
                        "memory_operation": "historical_pronoun_turn_delete_binding",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-pronoun-turn-1:q2",
                    question="What was my favorite color before that update?",
                    category="historical_state",
                    expected_answers=["red"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "pronoun_turn_disambiguation",
                        "memory_operation": "historical_pronoun_turn_update_binding",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-pronoun-turn-2",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2026-10-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="I live in Dubai."),
                        NormalizedTurn(turn_id="s1:t2", speaker="assistant", text="Saved."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2026-10-03",
                    turns=[
                        NormalizedTurn(
                            turn_id="s2:t1",
                            speaker="user",
                            text="About where I live, please forget it, and after that change it to Sharjah.",
                        ),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="Deleted then updated."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-pronoun-turn-2:q1",
                    question="Where did I live before that deletion?",
                    category="historical_state",
                    expected_answers=["Dubai"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "pronoun_turn_disambiguation",
                        "memory_operation": "historical_pronoun_turn_delete_binding",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-pronoun-turn-2:q2",
                    question="Where did I live before that update?",
                    category="historical_state",
                    expected_answers=["Dubai"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "pronoun_turn_disambiguation",
                        "memory_operation": "historical_pronoun_turn_update_binding",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-pronoun-ambiguity-1",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2026-11-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="My favorite color is red."),
                        NormalizedTurn(turn_id="s1:t2", speaker="assistant", text="Saved."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2026-11-02",
                    turns=[
                        NormalizedTurn(turn_id="s2:t1", speaker="user", text="I live in Dubai."),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="Saved."),
                    ],
                ),
                NormalizedSession(
                    session_id="s3",
                    timestamp="2026-11-03",
                    turns=[
                        NormalizedTurn(
                            turn_id="s3:t1",
                            speaker="user",
                            text="About my favorite color and where I live, please forget it.",
                        ),
                        NormalizedTurn(turn_id="s3:t2", speaker="assistant", text="Handled."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-pronoun-ambiguity-1:q1",
                    question="What was my favorite color before that deletion?",
                    category="historical_state",
                    expected_answers=["Information provided is not enough"],
                    evidence_session_ids=["s1", "s2", "s3"],
                    evidence_turn_ids=["s1:t1", "s2:t1", "s3:t1"],
                    should_abstain=True,
                    metadata={
                        "product_memory_task": "pronoun_referential_ambiguity",
                        "memory_operation": "historical_pronoun_scope_ambiguity_abstention",
                        "memory_scope": "multi_facet",
                        "expected_answer_candidate_source": "referential_ambiguity",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-pronoun-ambiguity-1:q2",
                    question="Where did I live before that deletion?",
                    category="historical_state",
                    expected_answers=["Information provided is not enough"],
                    evidence_session_ids=["s1", "s2", "s3"],
                    evidence_turn_ids=["s1:t1", "s2:t1", "s3:t1"],
                    should_abstain=True,
                    metadata={
                        "product_memory_task": "pronoun_referential_ambiguity",
                        "memory_operation": "historical_pronoun_scope_ambiguity_abstention",
                        "memory_scope": "multi_facet",
                        "expected_answer_candidate_source": "referential_ambiguity",
                    },
                ),
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-pronoun-ambiguity-2",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2026-12-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="My favorite color is red."),
                        NormalizedTurn(turn_id="s1:t2", speaker="assistant", text="Saved."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2026-12-02",
                    turns=[
                        NormalizedTurn(turn_id="s2:t1", speaker="user", text="I live in Dubai."),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="Saved."),
                    ],
                ),
                NormalizedSession(
                    session_id="s3",
                    timestamp="2026-12-03",
                    turns=[
                        NormalizedTurn(
                            turn_id="s3:t1",
                            speaker="user",
                            text="About my favorite color and where I live, please forget it, and after that change it to green.",
                        ),
                        NormalizedTurn(turn_id="s3:t2", speaker="assistant", text="Handled."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-pronoun-ambiguity-2:q1",
                    question="What was my favorite color before that deletion?",
                    category="historical_state",
                    expected_answers=["Information provided is not enough"],
                    evidence_session_ids=["s1", "s2", "s3"],
                    evidence_turn_ids=["s1:t1", "s2:t1", "s3:t1"],
                    should_abstain=True,
                    metadata={
                        "product_memory_task": "pronoun_referential_ambiguity",
                        "memory_operation": "historical_pronoun_multi_operation_ambiguity_abstention",
                        "memory_scope": "multi_facet",
                        "expected_answer_candidate_source": "referential_ambiguity",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-pronoun-ambiguity-2:q2",
                    question="What was my favorite color before that update?",
                    category="historical_state",
                    expected_answers=["Information provided is not enough"],
                    evidence_session_ids=["s1", "s2", "s3"],
                    evidence_turn_ids=["s1:t1", "s2:t1", "s3:t1"],
                    should_abstain=True,
                    metadata={
                        "product_memory_task": "pronoun_referential_ambiguity",
                        "memory_operation": "historical_pronoun_multi_operation_ambiguity_abstention",
                        "memory_scope": "multi_facet",
                        "expected_answer_candidate_source": "referential_ambiguity",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-pronoun-ambiguity-2:q3",
                    question="Where did I live before that deletion?",
                    category="historical_state",
                    expected_answers=["Information provided is not enough"],
                    evidence_session_ids=["s1", "s2", "s3"],
                    evidence_turn_ids=["s1:t1", "s2:t1", "s3:t1"],
                    should_abstain=True,
                    metadata={
                        "product_memory_task": "pronoun_referential_ambiguity",
                        "memory_operation": "historical_pronoun_multi_operation_ambiguity_abstention",
                        "memory_scope": "multi_facet",
                        "expected_answer_candidate_source": "referential_ambiguity",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-pronoun-ambiguity-2:q4",
                    question="Where did I live before that update?",
                    category="historical_state",
                    expected_answers=["Information provided is not enough"],
                    evidence_session_ids=["s1", "s2", "s3"],
                    evidence_turn_ids=["s1:t1", "s2:t1", "s3:t1"],
                    should_abstain=True,
                    metadata={
                        "product_memory_task": "pronoun_referential_ambiguity",
                        "memory_operation": "historical_pronoun_multi_operation_ambiguity_abstention",
                        "memory_scope": "multi_facet",
                        "expected_answer_candidate_source": "referential_ambiguity",
                    },
                ),
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-temporal-wording-1",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2027-01-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="My favorite color is red."),
                        NormalizedTurn(turn_id="s1:t2", speaker="assistant", text="Saved."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2027-01-03",
                    turns=[
                        NormalizedTurn(turn_id="s2:t1", speaker="user", text="Correction: my favorite color is green."),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="Updated."),
                    ],
                ),
                NormalizedSession(
                    session_id="s3",
                    timestamp="2027-01-05",
                    turns=[
                        NormalizedTurn(turn_id="s3:t1", speaker="user", text="Please forget my favorite color."),
                        NormalizedTurn(turn_id="s3:t2", speaker="assistant", text="Deleted."),
                    ],
                ),
                NormalizedSession(
                    session_id="s4",
                    timestamp="2027-01-07",
                    turns=[
                        NormalizedTurn(turn_id="s4:t1", speaker="user", text="Actually, my favorite color is yellow now."),
                        NormalizedTurn(turn_id="s4:t2", speaker="assistant", text="Updated again."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-temporal-wording-1:q1",
                    question="What was my favorite color before that earlier change?",
                    category="historical_state",
                    expected_answers=["red"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "temporal_wording_disambiguation",
                        "memory_operation": "historical_earlier_change_binding",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-temporal-wording-1:q2",
                    question="What was my favorite color before that later deletion?",
                    category="historical_state",
                    expected_answers=["green"],
                    evidence_session_ids=["s2"],
                    evidence_turn_ids=["s2:t1"],
                    metadata={
                        "product_memory_task": "temporal_wording_disambiguation",
                        "memory_operation": "historical_later_deletion_binding",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-temporal-wording-1:q3",
                    question="What was my favorite color before that later update?",
                    category="historical_state",
                    expected_answers=["green"],
                    evidence_session_ids=["s2"],
                    evidence_turn_ids=["s2:t1"],
                    metadata={
                        "product_memory_task": "temporal_wording_disambiguation",
                        "memory_operation": "historical_later_update_binding",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
            ],
        ),
        NormalizedBenchmarkSample(
            benchmark_name="ProductMemory",
            sample_id="product-memory-temporal-wording-2",
            sessions=[
                NormalizedSession(
                    session_id="s1",
                    timestamp="2027-02-01",
                    turns=[
                        NormalizedTurn(turn_id="s1:t1", speaker="user", text="I live in Dubai."),
                        NormalizedTurn(turn_id="s1:t2", speaker="assistant", text="Saved."),
                    ],
                ),
                NormalizedSession(
                    session_id="s2",
                    timestamp="2027-02-03",
                    turns=[
                        NormalizedTurn(turn_id="s2:t1", speaker="user", text="I moved to Sharjah."),
                        NormalizedTurn(turn_id="s2:t2", speaker="assistant", text="Updated."),
                    ],
                ),
                NormalizedSession(
                    session_id="s3",
                    timestamp="2027-02-05",
                    turns=[
                        NormalizedTurn(turn_id="s3:t1", speaker="user", text="Please forget where I live."),
                        NormalizedTurn(turn_id="s3:t2", speaker="assistant", text="Deleted."),
                    ],
                ),
                NormalizedSession(
                    session_id="s4",
                    timestamp="2027-02-07",
                    turns=[
                        NormalizedTurn(turn_id="s4:t1", speaker="user", text="I moved to Abu Dhabi."),
                        NormalizedTurn(turn_id="s4:t2", speaker="assistant", text="Updated again."),
                    ],
                ),
            ],
            questions=[
                NormalizedQuestion(
                    question_id="product-memory-temporal-wording-2:q1",
                    question="Where did I live before that earlier move?",
                    category="historical_state",
                    expected_answers=["Dubai"],
                    evidence_session_ids=["s1"],
                    evidence_turn_ids=["s1:t1"],
                    metadata={
                        "product_memory_task": "temporal_wording_disambiguation",
                        "memory_operation": "historical_earlier_change_binding",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-temporal-wording-2:q2",
                    question="Where did I live before that later deletion?",
                    category="historical_state",
                    expected_answers=["Sharjah"],
                    evidence_session_ids=["s2"],
                    evidence_turn_ids=["s2:t1"],
                    metadata={
                        "product_memory_task": "temporal_wording_disambiguation",
                        "memory_operation": "historical_later_deletion_binding",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
                NormalizedQuestion(
                    question_id="product-memory-temporal-wording-2:q3",
                    question="Where did I live before that later move?",
                    category="historical_state",
                    expected_answers=["Sharjah"],
                    evidence_session_ids=["s2"],
                    evidence_turn_ids=["s2:t1"],
                    metadata={
                        "product_memory_task": "temporal_wording_disambiguation",
                        "memory_operation": "historical_later_update_binding",
                        "memory_scope": "single_facet",
                        "expected_answer_candidate_source": "evidence_memory",
                    },
                ),
            ],
        ),
    ]
