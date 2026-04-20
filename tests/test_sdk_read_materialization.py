from domain_chip_memory import (
    AnswerExplanationRequest,
    CurrentStateRequest,
    EvidenceRetrievalRequest,
    MemoryWriteRequest,
    SparkMemorySDK,
)


def test_sdk_retrieve_evidence_supports_identity_summary_queries():
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="human:telegram:12345",
            predicate="profile.preferred_name",
            value="Sarah",
            timestamp="2025-03-01T09:00:00Z",
        )
    )
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="human:telegram:12345",
            predicate="profile.occupation",
            value="entrepreneur",
            timestamp="2025-03-01T09:01:00Z",
        )
    )

    evidence = sdk.retrieve_evidence(
        EvidenceRetrievalRequest(
            query="What do you know about me?",
            subject="telegram:12345",
            limit=5,
        )
    )

    assert len(evidence.items) == 2
    assert {item.predicate for item in evidence.items} == {"profile.preferred_name", "profile.occupation"}
    assert evidence.trace["query_intent"] == "profile_identity_summary"


def test_sdk_normalizes_bare_telegram_subjects_for_current_state_and_explanations():
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="create",
            subject="human:telegram:12345",
            predicate="profile.city",
            value="Dubai",
            timestamp="2025-03-01T09:00:00Z",
        )
    )

    state = sdk.get_current_state(
        CurrentStateRequest(
            subject="telegram:12345",
            predicate="profile.city",
        )
    )
    explanation = sdk.explain_answer(
        AnswerExplanationRequest(
            question="How do you know where I live?",
            subject="telegram:12345",
            predicate="profile.city",
        )
    )

    assert state.found is True
    assert state.value == "Dubai"
    assert explanation.found is True
    assert explanation.answer == "Dubai"
    assert explanation.evidence
