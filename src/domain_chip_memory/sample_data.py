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
                )
            ],
        ),
    ]
