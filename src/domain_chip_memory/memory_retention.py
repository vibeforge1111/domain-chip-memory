from __future__ import annotations

from typing import Any, cast

from .contracts import MemoryRole, RetentionClass


_RETENTION_CLASS_DESCRIPTION: dict[RetentionClass, str] = {
    "session_ephemeral": "Short-lived working-memory context that should not persist unless promoted.",
    "episodic_archive": "Cold but durable raw episode or source-truth archive for provenance and replay.",
    "active_state": "High-salience mutable state that should answer current-truth questions until superseded or deleted.",
    "durable_profile": "Longer-lived user, relationship, or stable fact memory that should remain retrievable across sessions.",
    "time_bound_event": "Temporal commitment or chronology memory that is salient while relevant and can later be demoted.",
    "derived_belief": "Derived summary or reflection that must remain marked as inferred and revalidatable.",
    "ops_residue": "Operational residue or low-value noise that should be rejected or quarantined, not promoted.",
}

_SDK_RETENTION_CLASS_ORDER: tuple[RetentionClass, ...] = (
    "session_ephemeral",
    "episodic_archive",
    "active_state",
    "durable_profile",
    "time_bound_event",
    "derived_belief",
    "ops_residue",
)

_DEFAULT_RETENTION_CLASS_BY_ROLE: dict[MemoryRole, RetentionClass | None] = {
    "unknown": None,
    "episodic": "episodic_archive",
    "current_state": "active_state",
    "state_deletion": "active_state",
    "structured_evidence": "durable_profile",
    "belief": "derived_belief",
    "event": "time_bound_event",
    "aggregate": None,
    "ambiguity": None,
}


def is_retention_class(value: str | None) -> bool:
    return str(value or "").strip() in _RETENTION_CLASS_DESCRIPTION


def default_retention_class(
    memory_role: MemoryRole | str | None,
    *,
    metadata: dict[str, Any] | None = None,
) -> RetentionClass | None:
    explicit = str((metadata or {}).get("retention_class") or "").strip()
    if explicit and is_retention_class(explicit):
        return cast(RetentionClass, explicit)
    cleaned = str(memory_role or "").strip()
    if cleaned in _DEFAULT_RETENTION_CLASS_BY_ROLE:
        return _DEFAULT_RETENTION_CLASS_BY_ROLE[cast(MemoryRole, cleaned)]
    return None


def describe_retention_class(retention_class: RetentionClass) -> dict[str, str]:
    return {
        "retention_class": retention_class,
        "description": _RETENTION_CLASS_DESCRIPTION[retention_class],
    }


def sdk_retention_contracts() -> list[dict[str, str]]:
    return [describe_retention_class(retention_class) for retention_class in _SDK_RETENTION_CLASS_ORDER]


def sdk_retention_defaults_by_role() -> dict[str, str]:
    return {
        role: retention_class
        for role, retention_class in _DEFAULT_RETENTION_CLASS_BY_ROLE.items()
        if retention_class is not None
    }
