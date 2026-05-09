from __future__ import annotations

import pytest

from domain_chip_memory.promotion_gates import (
    PromotionGateError,
    assert_promotion_gate,
    build_promotion_gate_contract_summary,
    evaluate_promotion_gate,
    is_protected_mutation_target,
    normalize_promotion_lane,
)


def test_promotion_lanes_normalize_audit_required_surfaces() -> None:
    assert normalize_promotion_lane("current-state") == "current_state"
    assert normalize_promotion_lane("observer-eval") == "observer_eval"
    assert normalize_promotion_lane("quarantine") == "quarantined"
    assert is_protected_mutation_target("mcp config") is True


def test_raw_memory_cannot_directly_modify_prompt_policy_or_skill() -> None:
    decision = evaluate_promotion_gate(
        {
            "promotion_lane": "raw",
            "target_surface": "skill",
            "source_refs": ["chat:1"],
            "eval_refs": ["shadow:1"],
            "approval_ref": "human:sec",
            "rollback_ref": "git:revert-plan",
        }
    )

    assert decision.allowed is False
    assert decision.decision == "block"
    assert decision.protected_target is True
    assert "protected_target_requires_promoted_lane" in decision.reasons


def test_protected_target_requires_provenance_eval_approval_and_rollback() -> None:
    decision = evaluate_promotion_gate(
        {
            "promotion_lane": "promoted",
            "target_surface": "provider_template",
            "source_refs": ["trace:source"],
            "eval_refs": ["eval:shadow"],
        }
    )

    assert decision.allowed is False
    assert decision.decision == "block"
    assert decision.missing_refs == ("approval_ref", "rollback_ref")
    assert "protected_target_missing_governance_refs" in decision.reasons


def test_promoted_record_with_full_governance_can_touch_protected_target() -> None:
    decision = assert_promotion_gate(
        {
            "promotion_lane": "promoted",
            "target_surface": "mcp_config",
            "source_refs": ["audit:memory-gate"],
            "eval_refs": ["pytest:test_promotion_gates"],
            "approval_ref": "approval:security-owner",
            "rollback_ref": "rollback:restore-pinned-config",
        }
    )

    assert decision.allowed is True
    assert decision.decision == "allow"
    assert decision.protected_target is True


def test_current_state_memory_is_not_self_improvement_authority() -> None:
    decision = evaluate_promotion_gate(
        {
            "promotion_lane": "current_state",
            "target_surface": "access_level",
            "source_refs": ["memory:current-state"],
            "eval_refs": ["eval:readback"],
            "approval_ref": "approval:user",
            "rollback_ref": "rollback:access-policy",
        }
    )

    assert decision.allowed is False
    assert "protected_target_requires_promoted_lane" in decision.reasons


def test_candidate_wiki_and_observer_eval_lanes_defer_for_normal_memory_targets() -> None:
    for lane in ("candidate", "wiki", "observer_eval"):
        decision = evaluate_promotion_gate({"promotion_lane": lane, "promotion_target": "current_state"})
        assert decision.allowed is False
        assert decision.decision == "defer"
        assert decision.reasons == ("supporting_lane_requires_separate_promotion",)


def test_quarantined_records_block_even_for_unprotected_targets() -> None:
    with pytest.raises(PromotionGateError, match="quarantined_lane_cannot_promote"):
        assert_promotion_gate({"promotion_lane": "quarantined", "promotion_target": "current_state"})


def test_contract_summary_names_protected_targets_and_refs() -> None:
    summary = build_promotion_gate_contract_summary()

    assert summary["promotion_lanes"] == [
        "raw",
        "candidate",
        "promoted",
        "current_state",
        "wiki",
        "observer_eval",
        "quarantined",
    ]
    assert "prompt" in summary["protected_mutation_targets"]
    assert "mcp_config" in summary["protected_mutation_targets"]
    assert summary["protected_gate_ref_fields"] == [
        "provenance_refs",
        "eval_refs",
        "approval_ref",
        "rollback_ref",
    ]
