from domain_chip_memory import (
    CurrentStateRequest,
    EvidenceRetrievalRequest,
    SparkMemorySDK,
    SparkShadowIngestAdapter,
    SparkShadowIngestRequest,
    SparkShadowProbe,
    SparkShadowTurn,
    build_shadow_replay_contract_summary,
    build_shadow_report,
    build_shadow_ingest_contract_summary,
    normalize_builder_shadow_export_payload,
    normalize_telegram_bot_export_payload,
    validate_shadow_replay_payload,
)


def test_shadow_ingest_contract_summary_exposes_runtime_surface():
    payload = build_shadow_ingest_contract_summary()

    assert payload["runtime_class"] == "SparkShadowIngestAdapter"
    assert "SparkShadowIngestRequest" in payload["request_contracts"]
    assert "SparkShadowProbe" in payload["request_contracts"]
    assert "SparkShadowReport" in payload["response_contracts"]


def test_shadow_replay_contract_summary_exposes_file_shapes():
    payload = build_shadow_replay_contract_summary()

    assert payload["single_file_shape"]["required_fields"] == ["conversations"]
    assert "turns" in payload["single_file_shape"]["conversation_fields"]
    assert "probe_type" in payload["single_file_shape"]["probe_fields"]
    assert payload["batch_shape"]["default_glob"] == "*.json"
    assert payload["supported_probe_types"] == ["current_state", "historical_state", "evidence"]
    assert "validate-spark-shadow-replay <file>" in payload["validation_entrypoints"][1]
    assert "validate-spark-shadow-replay-batch <dir>" in payload["validation_entrypoints"][2]


def test_validate_shadow_replay_payload_reports_good_file_shape():
    payload = validate_shadow_replay_payload(
        {
            "conversations": [
                {
                    "conversation_id": "conv-1",
                    "session_id": "conv-1",
                    "turns": [
                        {
                            "message_id": "m1",
                            "role": "user",
                            "content": "I live in Dubai.",
                            "timestamp": "2025-01-01T00:00:00Z",
                        }
                    ],
                    "probes": [
                        {
                            "probe_id": "p1",
                            "probe_type": "current_state",
                            "subject": "user",
                            "predicate": "location",
                            "expected_value": "Dubai",
                        }
                    ],
                }
            ]
        }
    )
    assert payload["valid"] is True
    assert payload["conversation_count"] == 1
    assert payload["turn_count"] == 1
    assert payload["probe_count"] == 1


def test_validate_shadow_replay_payload_reports_bad_shape():
    payload = validate_shadow_replay_payload(
        {
            "conversations": [
                {
                    "conversation_id": "",
                    "turns": [
                        {
                            "message_id": "",
                            "role": "",
                            "content": "",
                        }
                    ],
                    "probes": [
                        {
                            "probe_id": "",
                            "probe_type": "historical_state",
                            "subject": "user",
                            "predicate": "",
                            "as_of": "",
                            "min_results": 0,
                        }
                    ],
                }
            ]
        }
    )
    assert payload["valid"] is False
    assert payload["errors"]
    assert any("conversation_id" in error for error in payload["errors"])
    assert any("min_results" in error for error in payload["errors"])


def test_normalize_builder_shadow_export_payload_accepts_common_builder_aliases():
    payload = normalize_builder_shadow_export_payload(
        {
            "writableRoles": ["user"],
            "threads": [
                {
                    "threadId": "builder-thread-1",
                    "sessionId": "builder-session-1",
                    "meta": {"source": "builder"},
                    "messages": [
                        {
                            "id": "m1",
                            "speaker": "user",
                            "text": "I live in Dubai.",
                            "createdAt": "2025-03-01T09:00:00Z",
                            "meta": {"memory_kind": "current_state"},
                        }
                    ],
                    "probes": [
                        {
                            "id": "p1",
                            "type": "current_state",
                            "subject": "user",
                            "predicate": "location",
                            "expectedValue": "Dubai",
                        }
                    ],
                }
            ],
        }
    )

    assert payload == {
        "writable_roles": ["user"],
        "conversations": [
            {
                "conversation_id": "builder-thread-1",
                "session_id": "builder-session-1",
                "metadata": {"source": "builder"},
                "turns": [
                    {
                        "message_id": "m1",
                        "role": "user",
                        "content": "I live in Dubai.",
                        "timestamp": "2025-03-01T09:00:00Z",
                        "metadata": {"memory_kind": "current_state"},
                    }
                ],
                "probes": [
                    {
                        "probe_id": "p1",
                        "probe_type": "current_state",
                        "subject": "user",
                        "predicate": "location",
                        "expected_value": "Dubai",
                    }
                ],
            }
        ],
    }


def test_normalize_telegram_bot_export_payload_accepts_bot_api_updates():
    payload = normalize_telegram_bot_export_payload(
        {
            "result": [
                {
                    "update_id": 101,
                    "message": {
                        "message_id": 11,
                        "date": 1740829200,
                        "chat": {"id": -1001, "title": "Spark Lab", "type": "supergroup"},
                        "from": {"id": 501, "is_bot": False, "username": "alice", "first_name": "Alice"},
                        "text": "I live in Dubai.",
                    },
                },
                {
                    "update_id": 102,
                    "message": {
                        "message_id": 12,
                        "date": 1740829260,
                        "chat": {"id": -1001, "title": "Spark Lab", "type": "supergroup"},
                        "from": {"id": 900, "is_bot": True, "username": "spark_bot", "first_name": "Spark"},
                        "text": "Noted.",
                    },
                },
            ]
        }
    )

    assert payload == {
        "writable_roles": ["user"],
        "conversations": [
            {
                "conversation_id": "telegram-chat--1001",
                "session_id": "telegram-chat--1001",
                "metadata": {
                    "source": "telegram",
                    "telegram_chat_id": "-1001",
                    "telegram_chat_label": "Spark Lab",
                    "telegram_chat_type": "supergroup",
                },
                "turns": [
                    {
                        "message_id": "11",
                        "role": "user",
                        "content": "I live in Dubai.",
                        "timestamp": "2025-03-01T11:40:00Z",
                        "metadata": {
                            "source": "telegram",
                            "telegram_update_id": "101",
                            "telegram_chat_id": "-1001",
                            "telegram_message_id": "11",
                            "telegram_sender_id": "501",
                            "telegram_sender_username": "alice",
                            "telegram_sender_name": "Alice",
                        },
                    },
                    {
                        "message_id": "12",
                        "role": "assistant",
                        "content": "Noted.",
                        "timestamp": "2025-03-01T11:41:00Z",
                        "metadata": {
                            "source": "telegram",
                            "telegram_update_id": "102",
                            "telegram_chat_id": "-1001",
                            "telegram_message_id": "12",
                            "telegram_sender_id": "900",
                            "telegram_sender_username": "spark_bot",
                            "telegram_sender_name": "Spark",
                        },
                    },
                ],
            }
        ],
    }


def test_shadow_ingest_writes_user_turns_and_skips_assistant_turns():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-1",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="I live in London.",
                    timestamp="2025-01-01T09:00:00Z",
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="assistant",
                    content="Noted.",
                    timestamp="2025-01-01T09:01:00Z",
                ),
                SparkShadowTurn(
                    message_id="m3",
                    role="user",
                    content="I moved to Dubai.",
                    timestamp="2025-03-01T09:00:00Z",
                ),
            ],
        )
    )

    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))

    assert result.accepted_writes == 2
    assert result.rejected_writes == 0
    assert result.skipped_turns == 1
    assert result.reference_turns == 0
    assert current_state.found is True
    assert current_state.value == "Dubai"
    assert result.turn_traces[1].action == "skipped_role"


def test_shadow_ingest_counts_rejected_unsupported_writes():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-2",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="Hello there.",
                    timestamp="2025-01-01T09:00:00Z",
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="user",
                    content="I moved to Dubai.",
                    timestamp="2025-03-01T09:00:00Z",
                ),
            ],
        )
    )

    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))

    assert result.accepted_writes == 1
    assert result.rejected_writes == 0
    assert result.skipped_turns == 1
    assert result.reference_turns == 0
    assert result.turn_traces[0].action == "skipped_residue"
    assert result.turn_traces[0].unsupported_reason == "low_signal_residue"
    assert current_state.found is True
    assert current_state.value == "Dubai"


def test_shadow_ingest_skips_metadata_backed_ephemeral_residue():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-metadata-residue",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="Browser status ok.",
                    timestamp="2026-04-20T00:00:00Z",
                    metadata={
                        "keepability": "ephemeral_context",
                        "promotion_disposition": "not_promotable",
                        "bridge_mode": "external_autodiscovered",
                        "routing_decision": "provider_fallback_chat+manual_recommended",
                    },
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="user",
                    content="I live in Dubai.",
                    timestamp="2026-04-20T00:00:01Z",
                ),
            ],
        )
    )

    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))

    assert result.accepted_writes == 1
    assert result.rejected_writes == 0
    assert result.skipped_turns == 1
    assert result.turn_traces[0].action == "skipped_residue"
    assert result.turn_traces[0].unsupported_reason == "low_signal_residue"
    assert current_state.found is True
    assert current_state.value == "Dubai"


def test_shadow_ingest_reclassifies_non_memory_questions_as_residue():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-non-memory-question",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="What's on your mind?",
                    timestamp="2026-04-20T00:00:00Z",
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="user",
                    content="I live in Dubai.",
                    timestamp="2026-04-20T00:00:01Z",
                ),
            ],
        )
    )

    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))

    assert result.accepted_writes == 1
    assert result.rejected_writes == 0
    assert result.skipped_turns == 1
    assert result.turn_traces[0].action == "skipped_residue"
    assert result.turn_traces[0].unsupported_reason == "non_memory_chat"
    assert current_state.found is True
    assert current_state.value == "Dubai"


def test_shadow_ingest_reclassifies_unicode_question_chat_as_residue():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-unicode-question",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="what’s on your mind?",
                    timestamp="2026-04-20T00:00:00Z",
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="user",
                    content="I live in Dubai.",
                    timestamp="2026-04-20T00:00:01Z",
                ),
            ],
        )
    )

    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))

    assert result.accepted_writes == 1
    assert result.rejected_writes == 0
    assert result.skipped_turns == 1
    assert result.turn_traces[0].action == "skipped_residue"
    assert result.turn_traces[0].unsupported_reason == "non_memory_chat"
    assert current_state.found is True
    assert current_state.value == "Dubai"


def test_shadow_ingest_reclassifies_onboarding_turns_as_residue():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-onboarding-residue",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="energetic",
                    timestamp="2026-04-20T00:00:00Z",
                    metadata={
                        "source_event_type": "intent_committed",
                        "onboarding_step": "awaiting_persona",
                        "onboarding_completed": False,
                    },
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="user",
                    content="I live in Dubai.",
                    timestamp="2026-04-20T00:00:01Z",
                ),
            ],
        )
    )

    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))

    assert result.accepted_writes == 1
    assert result.rejected_writes == 0
    assert result.skipped_turns == 1
    assert result.turn_traces[0].action == "skipped_residue"
    assert result.turn_traces[0].unsupported_reason == "non_memory_chat"
    assert current_state.found is True
    assert current_state.value == "Dubai"


def test_shadow_ingest_reclassifies_filler_prefixed_questions_as_residue():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-filler-prefixed-question",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="hey can you do web search now",
                    timestamp="2026-04-20T00:00:00Z",
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="user",
                    content="I live in Dubai.",
                    timestamp="2026-04-20T00:00:01Z",
                ),
            ],
        )
    )

    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))

    assert result.accepted_writes == 1
    assert result.rejected_writes == 0
    assert result.skipped_turns == 1
    assert result.turn_traces[0].action == "skipped_residue"
    assert result.turn_traces[0].unsupported_reason == "non_memory_chat"
    assert current_state.found is True
    assert current_state.value == "Dubai"


def test_shadow_ingest_reclassifies_search_directives_as_residue():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-search-directive",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="Search the web and tell me the current BTC price in USD with the source you used.",
                    timestamp="2026-04-20T00:00:00Z",
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="user",
                    content="I live in Dubai.",
                    timestamp="2026-04-20T00:00:01Z",
                ),
            ],
        )
    )

    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))

    assert result.accepted_writes == 1
    assert result.rejected_writes == 0
    assert result.skipped_turns == 1
    assert result.turn_traces[0].action == "skipped_residue"
    assert result.turn_traces[0].unsupported_reason == "non_memory_chat"
    assert current_state.found is True
    assert current_state.value == "Dubai"


def test_shadow_ingest_reclassifies_execution_confirmations_as_residue():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-execution-confirmation",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="sure lets do it",
                    timestamp="2026-04-20T00:00:00Z",
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="user",
                    content="I live in Dubai.",
                    timestamp="2026-04-20T00:00:01Z",
                ),
            ],
        )
    )

    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))

    assert result.accepted_writes == 1
    assert result.rejected_writes == 0
    assert result.skipped_turns == 1
    assert result.turn_traces[0].action == "skipped_residue"
    assert result.turn_traces[0].unsupported_reason == "non_memory_chat"
    assert current_state.found is True
    assert current_state.value == "Dubai"


def test_shadow_ingest_reclassifies_meta_collaboration_prompts_as_residue():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-meta-collaboration",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="let's actually think about the startup part together",
                    timestamp="2026-04-20T00:00:00Z",
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="user",
                    content="I live in Dubai.",
                    timestamp="2026-04-20T00:00:01Z",
                ),
            ],
        )
    )

    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))

    assert result.accepted_writes == 1
    assert result.rejected_writes == 0
    assert result.skipped_turns == 1
    assert result.turn_traces[0].action == "skipped_residue"
    assert result.turn_traces[0].unsupported_reason == "non_memory_chat"
    assert current_state.found is True
    assert current_state.value == "Dubai"


def test_shadow_ingest_reclassifies_reflective_meta_chat_as_residue():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-reflective-meta",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="you ask a lot of questions from there",
                    timestamp="2026-04-20T00:00:00Z",
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="user",
                    content="I live in Dubai.",
                    timestamp="2026-04-20T00:00:01Z",
                ),
            ],
        )
    )

    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))

    assert result.accepted_writes == 1
    assert result.rejected_writes == 0
    assert result.skipped_turns == 1
    assert result.turn_traces[0].action == "skipped_residue"
    assert result.turn_traces[0].unsupported_reason == "non_memory_chat"
    assert current_state.found is True
    assert current_state.value == "Dubai"


def test_shadow_ingest_reclassifies_topic_fragments_as_residue():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-topic-fragment",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="AI for customer support",
                    timestamp="2026-04-20T00:00:00Z",
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="user",
                    content="I live in Dubai.",
                    timestamp="2026-04-20T00:00:01Z",
                ),
            ],
        )
    )

    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))

    assert result.accepted_writes == 1
    assert result.rejected_writes == 0
    assert result.skipped_turns == 1
    assert result.turn_traces[0].action == "skipped_residue"
    assert result.turn_traces[0].unsupported_reason == "non_memory_chat"
    assert current_state.found is True
    assert current_state.value == "Dubai"


def test_shadow_ingest_reclassifies_name_yourself_meta_chat_as_residue():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-name-yourself-meta",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="just chilling and testing you i guess, by the way you should name yourself Spark",
                    timestamp="2026-04-20T00:00:00Z",
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="user",
                    content="I live in Dubai.",
                    timestamp="2026-04-20T00:00:01Z",
                ),
            ],
        )
    )

    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))

    assert result.accepted_writes == 1
    assert result.rejected_writes == 0
    assert result.skipped_turns == 1
    assert result.turn_traces[0].action == "skipped_residue"
    assert result.turn_traces[0].unsupported_reason == "non_memory_chat"
    assert current_state.found is True
    assert current_state.value == "Dubai"


def test_shadow_ingest_accepts_builder_project_history_as_current_mission():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-project-history-mission",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="I've been building a memory domain chip for you too right now thats in shadow tests but should be live soon",
                    timestamp="2026-04-20T00:00:00Z",
                ),
            ],
        )
    )

    mission = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="current_mission"))

    assert result.accepted_writes == 1
    assert result.rejected_writes == 0
    assert result.skipped_turns == 0
    assert mission.found is True
    assert mission.value == "build a memory domain chip for Spark"


def test_shadow_ingest_accepts_building_spark_statement_as_current_mission():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-build-spark-mission",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="I'm building you",
                    timestamp="2026-04-20T00:00:00Z",
                ),
            ],
        )
    )

    mission = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="current_mission"))

    assert result.accepted_writes == 1
    assert result.rejected_writes == 0
    assert result.skipped_turns == 0
    assert mission.found is True
    assert mission.value == "build Spark"


def test_shadow_ingest_skips_unchanged_explicit_current_state_writes():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-unchanged-state",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="I live in Dubai.",
                    timestamp="2026-04-20T00:00:00Z",
                    metadata={
                        "source_event_type": "memory_write_requested",
                        "subject": "human:telegram:test",
                        "predicate": "profile.city",
                        "value": "Dubai",
                        "operation": "update",
                        "memory_role": "current_state",
                    },
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="user",
                    content="I still live in Dubai.",
                    timestamp="2026-04-20T00:00:01Z",
                    metadata={
                        "source_event_type": "memory_write_requested",
                        "subject": "human:telegram:test",
                        "predicate": "profile.city",
                        "value": "Dubai",
                        "operation": "update",
                        "memory_role": "current_state",
                    },
                ),
            ],
        )
    )

    current_state = sdk.get_current_state(
        CurrentStateRequest(subject="human:telegram:test", predicate="profile.city")
    )

    assert result.accepted_writes == 1
    assert result.rejected_writes == 0
    assert result.skipped_turns == 1
    assert result.turn_traces[1].action == "skipped_unchanged_current_state"
    assert result.turn_traces[1].unsupported_reason == "unchanged_current_state"
    assert current_state.found is True
    assert current_state.value == "Dubai"


def test_shadow_ingest_same_timestamp_later_turn_wins_current_state():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    filler_turns = [
        SparkShadowTurn(
            message_id=f"m{index}",
            role="assistant",
            content="Noted.",
            timestamp="2026-04-20T00:00:00Z",
        )
        for index in range(1, 9)
    ]
    turns = [
        *filler_turns,
        SparkShadowTurn(
            message_id="m9",
            role="user",
            content="I live in Dubai.",
            timestamp="2026-04-20T00:00:00Z",
        ),
        SparkShadowTurn(
            message_id="m10",
            role="assistant",
            content="Noted.",
            timestamp="2026-04-20T00:00:00Z",
        ),
        SparkShadowTurn(
            message_id="m11",
            role="user",
            content="I live in Abu Dhabi now.",
            timestamp="2026-04-20T00:00:00Z",
        ),
    ]

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-same-timestamp-order",
            turns=turns,
        )
    )

    current_state = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="location"))
    evidence = sdk.retrieve_evidence(
        EvidenceRetrievalRequest(subject="user", predicate="location", limit=2)
    )

    assert result.accepted_writes == 2
    assert current_state.found is True
    assert current_state.value == "Abu Dhabi"
    assert evidence.items[0].text == "I live in Abu Dhabi"


def test_shadow_ingest_accepts_founder_startup_and_hack_facts():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-founder-conv",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="I am an entrepreneur.",
                    timestamp="2025-01-01T09:00:00Z",
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="user",
                    content="My startup is Seedify.",
                    timestamp="2025-01-01T09:01:00Z",
                ),
                SparkShadowTurn(
                    message_id="m3",
                    role="user",
                    content="We were hacked by North Korea.",
                    timestamp="2025-01-01T09:02:00Z",
                ),
                SparkShadowTurn(
                    message_id="m4",
                    role="user",
                    content="I am trying to survive the hack and revive the companies.",
                    timestamp="2025-01-01T09:03:00Z",
                ),
                SparkShadowTurn(
                    message_id="m5",
                    role="user",
                    content="I am the founder of Spark Swarm.",
                    timestamp="2025-01-01T09:04:00Z",
                ),
            ],
        )
    )

    startup = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="startup_name"))
    attacker = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="hack_actor"))
    founder = sdk.get_current_state(CurrentStateRequest(subject="user", predicate="founder_of"))

    assert result.accepted_writes == 5
    assert result.rejected_writes == 0
    assert result.reference_turns == 0
    assert startup.found is True
    assert startup.value == "Seedify"
    assert attacker.found is True
    assert attacker.value == "North Korea"
    assert founder.found is True
    assert founder.value == "Spark Swarm"


def test_shadow_ingest_can_route_turn_to_event_write():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-3",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="I moved to Dubai.",
                    timestamp="2025-03-01T09:00:00Z",
                    metadata={"memory_kind": "event"},
                ),
            ],
        )
    )

    assert result.accepted_writes == 1
    assert result.reference_turns == 0
    assert result.turn_traces[0].accepted is True
    assert result.turn_traces[0].trace["write_trace"]["operation"] == "write_memory"


def test_shadow_ingest_consolidates_telegram_event_write_into_latest_current_state():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-telegram-event",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="My flight to Tokyo is on May 18.",
                    timestamp="2025-03-01T09:00:00Z",
                    metadata={
                        "memory_kind": "event",
                        "subject": "human:telegram:test",
                        "predicate": "telegram.event.flight",
                        "value": "flight to Tokyo on May 18",
                        "operation": "event",
                    },
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="user",
                    content="My flight to Tokyo is on May 24.",
                    timestamp="2025-03-02T09:00:00Z",
                    metadata={
                        "memory_kind": "event",
                        "subject": "human:telegram:test",
                        "predicate": "telegram.event.flight",
                        "value": "flight to Tokyo on May 24",
                        "operation": "event",
                    },
                ),
            ],
        )
    )

    current_state = sdk.get_current_state(
        CurrentStateRequest(subject="human:telegram:test", predicate="telegram.summary.latest_flight")
    )

    assert result.accepted_writes == 2
    assert current_state.found is True
    assert current_state.value == "flight to Tokyo on May 24"


def test_shadow_ingest_uses_explicit_structured_metadata_when_present():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-structured",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="User preference update. I live in Dubai.",
                    timestamp="2025-03-01T09:00:00Z",
                    metadata={
                        "memory_kind": "current_state",
                        "subject": "human:human:test",
                        "predicate": "profile.city",
                        "value": "Dubai",
                        "operation": "update",
                        "memory_role": "current_state",
                    },
                ),
            ],
        )
    )

    current_state = sdk.get_current_state(CurrentStateRequest(subject="human:human:test", predicate="profile.city"))

    assert result.accepted_writes == 1
    assert result.reference_turns == 0
    assert current_state.found is True
    assert current_state.value == "Dubai"


def test_shadow_ingest_treats_bridge_queries_and_bridge_replies_as_reference_turns():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="bridge-conv-1",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="My startup is Seedify.",
                    timestamp="2026-04-10T11:45:08Z",
                    metadata={
                        "source_event_type": "memory_write_requested",
                        "subject": "human:telegram:test",
                        "predicate": "profile.startup_name",
                        "value": "Seedify",
                        "operation": "update",
                        "memory_role": "current_state",
                    },
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="assistant",
                    content="I'll remember you created Seedify.",
                    timestamp="2026-04-10T11:45:08Z",
                    metadata={"source_event_type": "tool_result_received"},
                ),
                SparkShadowTurn(
                    message_id="m3",
                    role="user",
                    content="What is my startup?",
                    timestamp="2026-04-10T11:45:09Z",
                    metadata={"source_event_type": "plugin_or_chip_influence_recorded"},
                ),
            ],
        )
    )

    startup = sdk.get_current_state(CurrentStateRequest(subject="human:telegram:test", predicate="profile.startup_name"))

    assert result.accepted_writes == 1
    assert result.rejected_writes == 0
    assert result.skipped_turns == 0
    assert result.reference_turns == 2
    assert startup.found is True
    assert startup.value == "Seedify"
    assert result.turn_traces[1].action == "reference_turn"
    assert result.turn_traces[2].action == "reference_turn"


def test_shadow_ingest_applies_promotion_policy_to_source_backed_clone_writes():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(
        sdk=sdk,
        promotion_policy_rows=(
            {
                "policy_decision": "allow",
                "target_conversation_id": "allowed-conv",
                "predicate": "profile.hack_actor",
                "source_conversation_id": "source-conv",
                "source_message_id": "msg-hack",
            },
            {
                "policy_decision": "block",
                "target_conversation_id": "blocked-conv",
                "predicate": "profile.timezone",
                "source_conversation_id": "source-conv",
                "source_message_id": "msg-timezone",
            },
        ),
    )

    allowed_result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="allowed-conv",
            turns=[
                SparkShadowTurn(
                    message_id="clone-hack",
                    role="user",
                    content="We were hacked by North Korea.",
                    timestamp="2026-04-12T00:00:00Z",
                    metadata={
                        "source_event_type": "memory_write_requested",
                        "source_backed_clone": True,
                        "source_backed_predicate": "profile.hack_actor",
                        "source_backed_from_conversation_id": "source-conv",
                        "source_backed_from_message_id": "msg-hack",
                        "source_backed_target_conversation_id": "allowed-conv",
                        "subject": "human:telegram:allowed",
                        "predicate": "profile.hack_actor",
                        "value": "North Korea",
                        "operation": "update",
                        "memory_role": "current_state",
                    },
                )
            ],
        )
    )
    blocked_result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="blocked-conv",
            turns=[
                SparkShadowTurn(
                    message_id="clone-timezone",
                    role="user",
                    content="My timezone is Asia/Dubai.",
                    timestamp="2026-04-12T00:00:01Z",
                    metadata={
                        "source_event_type": "memory_write_requested",
                        "source_backed_clone": True,
                        "source_backed_predicate": "profile.timezone",
                        "source_backed_from_conversation_id": "source-conv",
                        "source_backed_from_message_id": "msg-timezone",
                        "source_backed_target_conversation_id": "blocked-conv",
                        "subject": "human:telegram:blocked",
                        "predicate": "profile.timezone",
                        "value": "Asia/Dubai",
                        "operation": "update",
                        "memory_role": "current_state",
                    },
                )
            ],
        )
    )

    allowed_lookup = sdk.get_current_state(
        CurrentStateRequest(subject="human:telegram:allowed", predicate="profile.hack_actor")
    )
    blocked_lookup = sdk.get_current_state(
        CurrentStateRequest(subject="human:telegram:blocked", predicate="profile.timezone")
    )

    assert allowed_result.accepted_writes == 1
    assert allowed_result.skipped_turns == 0
    assert allowed_lookup.found is True
    assert allowed_lookup.value == "North Korea"

    assert blocked_result.accepted_writes == 0
    assert blocked_result.skipped_turns == 1
    assert blocked_lookup.found is False
    assert blocked_result.turn_traces[0].action == "skipped_promotion_policy"
    assert blocked_result.turn_traces[0].unsupported_reason == "block"
    assert blocked_result.turn_traces[0].trace["policy_decision"] == "block"


def test_shadow_ingest_default_denies_source_backed_clone_without_policy_row():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(
        sdk=sdk,
        promotion_policy_rows=(
            {
                "policy_decision": "allow",
                "target_conversation_id": "other-conv",
                "predicate": "profile.timezone",
                "source_conversation_id": "source-conv",
                "source_message_id": "msg-timezone",
            },
        ),
    )

    result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="missing-policy-conv",
            turns=[
                SparkShadowTurn(
                    message_id="clone-missing",
                    role="user",
                    content="My timezone is Asia/Dubai.",
                    timestamp="2026-04-12T00:00:00Z",
                    metadata={
                        "source_event_type": "memory_write_requested",
                        "source_backed_clone": True,
                        "source_backed_predicate": "profile.timezone",
                        "source_backed_from_conversation_id": "source-conv",
                        "source_backed_from_message_id": "msg-timezone",
                        "source_backed_target_conversation_id": "missing-policy-conv",
                        "subject": "human:telegram:missing-policy",
                        "predicate": "profile.timezone",
                        "value": "Asia/Dubai",
                        "operation": "update",
                        "memory_role": "current_state",
                    },
                )
            ],
        )
    )

    lookup = sdk.get_current_state(
        CurrentStateRequest(subject="human:telegram:missing-policy", predicate="profile.timezone")
    )

    assert result.accepted_writes == 0
    assert result.skipped_turns == 1
    assert lookup.found is False
    assert result.turn_traces[0].action == "skipped_promotion_policy"
    assert result.turn_traces[0].unsupported_reason == "missing_policy_row"


def test_shadow_ingest_evaluation_summarizes_write_and_readback_quality():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    ingest_result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-4",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="Hello there.",
                    timestamp="2025-01-01T09:00:00Z",
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="assistant",
                    content="Noted.",
                    timestamp="2025-01-01T09:01:00Z",
                ),
                SparkShadowTurn(
                    message_id="m3",
                    role="user",
                    content="I moved to Dubai.",
                    timestamp="2025-03-01T09:00:00Z",
                ),
            ],
        )
    )
    evaluation = adapter.evaluate_ingest(
        ingest_result,
        probes=[
            SparkShadowProbe(
                probe_id="p1",
                probe_type="current_state",
                subject="user",
                predicate="location",
                expected_value="Dubai",
            ),
            SparkShadowProbe(
                probe_id="p2",
                probe_type="evidence",
                subject="user",
                predicate="location",
                expected_value="Dubai",
                min_results=1,
            ),
        ],
    )

    assert evaluation.summary["accepted_writes"] == 1
    assert evaluation.summary["rejected_writes"] == 0
    assert evaluation.summary["skipped_turns"] == 2
    assert evaluation.summary["reference_turns"] == 0
    assert evaluation.summary["accepted_rate"] == 0.3333
    assert evaluation.summary["rejected_rate"] == 0.0
    assert evaluation.summary["skipped_rate"] == 0.6667
    assert evaluation.summary["unsupported_reasons"] == [
        {"reason": "low_signal_residue", "count": 1}
    ]
    assert evaluation.summary["current_state_hit_rate"]["hits"] == 1
    assert evaluation.summary["current_state_hit_rate"]["rate"] == 1.0
    assert evaluation.summary["evidence_hit_rate"]["hits"] == 1
    assert evaluation.summary["evidence_hit_rate"]["rate"] == 1.0
    assert evaluation.probe_results[0].matched_expected is True
    assert evaluation.probe_results[1].matched_expected is True


def test_shadow_ingest_evaluation_supports_historical_state_probes():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    ingest_result = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-5",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="I live in London.",
                    timestamp="2025-01-01T09:00:00Z",
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="user",
                    content="I moved to Dubai.",
                    timestamp="2025-03-01T09:00:00Z",
                ),
                SparkShadowTurn(
                    message_id="m3",
                    role="user",
                    content="I moved to Abu Dhabi.",
                    timestamp="2025-06-01T09:00:00Z",
                ),
            ],
        )
    )
    evaluation = adapter.evaluate_ingest(
        ingest_result,
        probes=[
            SparkShadowProbe(
                probe_id="p1",
                probe_type="historical_state",
                subject="user",
                predicate="location",
                as_of="2025-05-01T00:00:00Z",
                expected_value="Dubai",
            )
        ],
    )

    assert evaluation.summary["historical_state_hit_rate"]["hits"] == 1
    assert evaluation.summary["historical_state_hit_rate"]["rate"] == 1.0
    assert evaluation.probe_results[0].matched_expected is True


def test_shadow_report_aggregates_multiple_evaluations():
    sdk = SparkMemorySDK()
    adapter = SparkShadowIngestAdapter(sdk=sdk)

    first_ingest = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-6",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="user",
                    content="Hello there.",
                    timestamp="2025-01-01T09:00:00Z",
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="user",
                    content="I moved to Dubai.",
                    timestamp="2025-03-01T09:00:00Z",
                ),
            ],
        )
    )
    second_ingest = adapter.ingest_conversation(
        SparkShadowIngestRequest(
            conversation_id="builder-conv-7",
            turns=[
                SparkShadowTurn(
                    message_id="m1",
                    role="assistant",
                    content="Noted.",
                    timestamp="2025-04-01T09:00:00Z",
                ),
                SparkShadowTurn(
                    message_id="m2",
                    role="user",
                    content="I moved to Abu Dhabi.",
                    timestamp="2025-06-01T09:00:00Z",
                ),
            ],
        )
    )

    first_evaluation = adapter.evaluate_ingest(
        first_ingest,
        probes=[
            SparkShadowProbe(
                probe_id="p1",
                probe_type="current_state",
                subject="user",
                predicate="location",
                expected_value="dubai",
            )
        ],
    )
    second_evaluation = adapter.evaluate_ingest(
        second_ingest,
        probes=[
            SparkShadowProbe(
                probe_id="p2",
                probe_type="historical_state",
                subject="user",
                predicate="location",
                as_of="2025-05-01T00:00:00Z",
                expected_value="dubai",
            ),
            SparkShadowProbe(
                probe_id="p3",
                probe_type="evidence",
                subject="user",
                predicate="location",
                expected_value="abu dhabi",
                min_results=1,
            ),
        ],
    )

    report = build_shadow_report([first_evaluation, second_evaluation])

    assert report.run_count == 2
    assert report.summary["accepted_writes"] == 2
    assert report.summary["rejected_writes"] == 0
    assert report.summary["skipped_turns"] == 2
    assert report.summary["reference_turns"] == 0
    assert report.summary["total_turns"] == 4
    assert report.summary["accepted_rate"] == 0.5
    assert report.summary["rejected_rate"] == 0.0
    assert report.summary["skipped_rate"] == 0.5
    assert report.summary["unsupported_reasons"] == [
        {"reason": "low_signal_residue", "count": 1}
    ]
    assert report.summary["probe_rows"] == [
        {
            "probe_type": "current_state",
            "hits": 1,
            "total": 1,
            "hit_rate": 1.0,
            "expected_matches": 0,
            "expected_total": 1,
            "expected_match_rate": 0.0,
        },
        {
            "probe_type": "evidence",
            "hits": 1,
            "total": 1,
            "hit_rate": 1.0,
            "expected_matches": 1,
            "expected_total": 1,
            "expected_match_rate": 1.0,
        },
        {
            "probe_type": "historical_state",
            "hits": 1,
            "total": 1,
            "hit_rate": 1.0,
            "expected_matches": 1,
            "expected_total": 1,
            "expected_match_rate": 1.0,
        },
    ]
    assert report.summary["memory_roles"] == [
        {"memory_role": "current_state", "count": 1},
        {"memory_role": "structured_evidence", "count": 2},
    ]
    assert report.conversation_rows == [
        {
            "conversation_id": "builder-conv-6",
            "session_id": "builder-conv-6",
            "accepted_writes": 1,
            "rejected_writes": 0,
            "skipped_turns": 1,
            "reference_turns": 0,
            "probe_count": 1,
        },
        {
            "conversation_id": "builder-conv-7",
            "session_id": "builder-conv-7",
            "accepted_writes": 1,
            "rejected_writes": 0,
            "skipped_turns": 1,
            "reference_turns": 0,
            "probe_count": 2,
        },
    ]
