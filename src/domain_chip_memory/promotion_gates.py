from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .contracts import JsonDict


PROMOTION_LANES: tuple[str, ...] = (
    "raw",
    "candidate",
    "promoted",
    "current_state",
    "wiki",
    "observer_eval",
    "quarantined",
)
AUTHORITATIVE_MEMORY_LANES = {"promoted", "current_state"}
SUPPORTING_MEMORY_LANES = {"raw", "candidate", "wiki", "observer_eval"}
BLOCKED_MEMORY_LANES = {"quarantined"}
PROTECTED_MUTATION_TARGETS: tuple[str, ...] = (
    "prompt",
    "policy",
    "skill",
    "access_level",
    "provider_template",
    "mcp_config",
    "installer_behavior",
)
PROTECTED_GATE_REF_FIELDS: tuple[str, ...] = (
    "provenance_refs",
    "eval_refs",
    "approval_ref",
    "rollback_ref",
)

_LANE_ALIASES = {
    "raw_episode": "raw",
    "working_scratchpad": "raw",
    "scratchpad": "raw",
    "structured_evidence": "candidate",
    "current-state": "current_state",
    "current_state_confirmed": "current_state",
    "current_state_candidate": "candidate",
    "llm_wiki": "wiki",
    "project_wiki": "wiki",
    "observer-eval": "observer_eval",
    "shadow_comparator": "observer_eval",
    "quarantine": "quarantined",
    "rejected": "quarantined",
    "blocked": "quarantined",
}
_TARGET_ALIASES = {
    "system_prompt": "prompt",
    "developer_prompt": "prompt",
    "prompt_template": "prompt",
    "access_policy": "access_level",
    "permission": "access_level",
    "provider_templates": "provider_template",
    "mcp": "mcp_config",
    "mcp_server_config": "mcp_config",
    "installer": "installer_behavior",
    "install_script": "installer_behavior",
    "current-state": "current_state",
}
_REF_ALIASES = {
    "provenance_refs": ("provenance_refs", "source_refs", "lineage_refs", "source_ref", "source"),
    "eval_refs": ("eval_refs", "evaluation_refs", "benchmark_refs", "shadow_eval_refs", "eval_ref"),
    "approval_ref": ("approval_ref", "approval_id", "human_approval_ref", "policy_approval_ref"),
    "rollback_ref": ("rollback_ref", "rollback_plan_ref", "rollback_id"),
}


@dataclass(frozen=True)
class PromotionGateDecision:
    allowed: bool
    decision: str
    lane: str
    target: str
    protected_target: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)
    missing_refs: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> JsonDict:
        return {
            "allowed": self.allowed,
            "decision": self.decision,
            "lane": self.lane,
            "target": self.target,
            "protected_target": self.protected_target,
            "reasons": list(self.reasons),
            "missing_refs": list(self.missing_refs),
        }


class PromotionGateError(ValueError):
    pass


def normalize_promotion_lane(value: Any) -> str:
    lane = _normalize_token(value)
    return _LANE_ALIASES.get(lane, lane)


def normalize_mutation_target(value: Any) -> str:
    target = _normalize_token(value)
    return _TARGET_ALIASES.get(target, target)


def is_protected_mutation_target(value: Any) -> bool:
    return normalize_mutation_target(value) in PROTECTED_MUTATION_TARGETS


def evaluate_promotion_gate(record: Mapping[str, Any]) -> PromotionGateDecision:
    lane = normalize_promotion_lane(
        _first_present(record, ("promotion_lane", "lane", "memory_lane", "promotion_stage"))
    )
    target = normalize_mutation_target(
        _first_present(record, ("mutation_target", "target_surface", "target_kind", "promotion_target", "target"))
    )
    reasons: list[str] = []
    missing_refs: list[str] = []

    if lane not in PROMOTION_LANES:
        reasons.append("unknown_promotion_lane")
    if not target:
        reasons.append("missing_promotion_target")

    protected_target = target in PROTECTED_MUTATION_TARGETS
    if lane in BLOCKED_MEMORY_LANES:
        reasons.append("quarantined_lane_cannot_promote")

    if protected_target:
        if lane != "promoted":
            reasons.append("protected_target_requires_promoted_lane")
        missing_refs = _missing_required_refs(record)
        if missing_refs:
            reasons.append("protected_target_missing_governance_refs")

    if reasons:
        return PromotionGateDecision(
            allowed=False,
            decision="block",
            lane=lane,
            target=target,
            protected_target=protected_target,
            reasons=tuple(reasons),
            missing_refs=tuple(missing_refs),
        )

    if lane in SUPPORTING_MEMORY_LANES:
        return PromotionGateDecision(
            allowed=False,
            decision="defer",
            lane=lane,
            target=target,
            protected_target=protected_target,
            reasons=("supporting_lane_requires_separate_promotion",),
        )

    return PromotionGateDecision(
        allowed=True,
        decision="allow",
        lane=lane,
        target=target,
        protected_target=protected_target,
    )


def assert_promotion_gate(record: Mapping[str, Any]) -> PromotionGateDecision:
    decision = evaluate_promotion_gate(record)
    if not decision.allowed:
        reason_text = ", ".join(decision.reasons) if decision.reasons else decision.decision
        raise PromotionGateError(f"Promotion gate blocked {decision.target or 'unknown target'}: {reason_text}")
    return decision


def build_promotion_gate_contract_summary() -> JsonDict:
    return {
        "contract_name": "SparkMemoryPromotionGate",
        "purpose": (
            "Separate memory evidence lanes from authority-changing self-improvement. "
            "Retrieved memory, tool output, web content, wiki packets, and observer evals are evidence until a gate promotes them."
        ),
        "promotion_lanes": list(PROMOTION_LANES),
        "authoritative_memory_lanes": sorted(AUTHORITATIVE_MEMORY_LANES),
        "supporting_memory_lanes": sorted(SUPPORTING_MEMORY_LANES),
        "blocked_memory_lanes": sorted(BLOCKED_MEMORY_LANES),
        "protected_mutation_targets": list(PROTECTED_MUTATION_TARGETS),
        "protected_gate_ref_fields": list(PROTECTED_GATE_REF_FIELDS),
        "non_override_rules": [
            "Raw, candidate, wiki, observer-eval, and quarantined lanes cannot directly modify protected Spark surfaces.",
            "Protected targets require promoted lane plus provenance, evaluation, approval, and rollback references.",
            "Current-state memory can answer mutable user facts, but it does not authorize prompt, policy, skill, access, provider, MCP, or installer changes.",
            "Quarantined records are inspectable policy evidence only, never truth or runtime authority.",
        ],
    }


def _normalize_token(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _first_present(record: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return value
    return ""


def _has_ref(record: Mapping[str, Any], field_name: str) -> bool:
    for key in _REF_ALIASES[field_name]:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, (list, tuple, set)) and any(str(item).strip() for item in value):
            return True
    return False


def _missing_required_refs(record: Mapping[str, Any]) -> list[str]:
    return [field_name for field_name in PROTECTED_GATE_REF_FIELDS if not _has_ref(record, field_name)]
