from __future__ import annotations

from typing import Any


OWNER_REPO = "domain-chip-memory"
CANONICAL_DISPOSITIONS = {"removed", "quarantined", "evidence_adapter", "canonical_consumer"}


def _plane(
    *,
    plane_id: str,
    surface: str,
    plane_type: str,
    source_path: str,
    summary: str,
    disposition: str,
    authority_risk: dict[str, bool] | None = None,
    evidence_only: bool = False,
    governor_required: bool = False,
    consumer_of_governor: bool = False,
    ledger_required: bool = False,
    upstream_authority_required: bool = False,
    claim_boundary: str | None = None,
) -> dict[str, Any]:
    if disposition not in CANONICAL_DISPOSITIONS:
        raise ValueError(f"Unsupported legacy authority disposition: {disposition}")

    return {
        "plane_id": f"legacy-plane:{plane_id}",
        "owner_repo": OWNER_REPO,
        "surface": surface,
        "plane_type": plane_type,
        "source_path": source_path,
        "summary": summary,
        "claim_boundary": claim_boundary or "",
        "authority_risk": dict(authority_risk or {}),
        "disposition": disposition,
        "harness_binding": {
            "evidence_only": evidence_only,
            "governor_required": governor_required,
            "consumer_of_governor": consumer_of_governor,
            "ledger_required": ledger_required,
            "upstream_authority_required": upstream_authority_required,
        },
        "blockers": [],
    }


def build_memory_legacy_authority_planes() -> list[dict[str, Any]]:
    return [
        _plane(
            plane_id="memory-sdk-write-subsystem",
            surface="memory",
            plane_type="memory_subsystem",
            source_path="src/domain_chip_memory/sdk.py",
            summary=(
                "SparkMemorySDK can mutate its in-process memory model, but it is not a raw-language ingress; "
                "Builder or another Spark owner must provide the upstream Governor decision before live writes."
            ),
            disposition="canonical_consumer",
            authority_risk={"can_mutate_state": True, "can_write_memory": True},
            governor_required=True,
            consumer_of_governor=True,
            upstream_authority_required=True,
        ),
        _plane(
            plane_id="memory-promotion-publish",
            surface="memory",
            plane_type="artifact_publisher",
            source_path="src/domain_chip_memory/cli.py",
            summary=(
                "Publishing a governed Spark KB refresh validates GovernorDecisionV1, allow authorization, "
                "human approval, binding refs, and a pre-execution ToolCallLedgerV1 before writing release artifacts."
            ),
            disposition="canonical_consumer",
            authority_risk={"can_execute": True, "can_mutate_state": True, "can_publish": True},
            governor_required=True,
            consumer_of_governor=True,
            ledger_required=True,
        ),
        _plane(
            plane_id="memory-promotion-ship",
            surface="memory",
            plane_type="artifact_publisher",
            source_path="src/domain_chip_memory/cli.py",
            summary=(
                "Shipping a governed Spark KB release validates ship authority before publish, summary, gate, "
                "and result-ledger writes; the nested publish step cannot bypass the parent Governor decision."
            ),
            disposition="canonical_consumer",
            authority_risk={"can_execute": True, "can_mutate_state": True, "can_publish": True},
            governor_required=True,
            consumer_of_governor=True,
            ledger_required=True,
        ),
        _plane(
            plane_id="memory-derived-protected-promotion-gate",
            surface="memory",
            plane_type="policy_gate",
            source_path="src/domain_chip_memory/promotion_gates.py",
            summary=(
                "Memory-derived records cannot change prompts, policies, skills, access, provider templates, "
                "MCP config, or installer behavior without provenance, eval, approval, and rollback refs."
            ),
            disposition="evidence_adapter",
            evidence_only=True,
        ),
        _plane(
            plane_id="memory-benchmark-provider-runner",
            surface="memory",
            plane_type="benchmark_runner",
            source_path="src/domain_chip_memory/runner.py,src/domain_chip_memory/providers.py,src/domain_chip_memory/adapters.py",
            summary=(
                "Benchmark/provider runners are explicit CLI evaluation tools and evidence producers; they are not "
                "Telegram, Builder, or autonomous Spark execution authority."
            ),
            disposition="evidence_adapter",
            evidence_only=True,
        ),
        _plane(
            plane_id="memory-shadow-replay-adapters",
            surface="memory",
            plane_type="replay_adapter",
            source_path="src/domain_chip_memory/spark_shadow.py,src/domain_chip_memory/cli.py",
            summary=(
                "Builder and Telegram shadow adapters normalize offline exports for replay and failure taxonomy; "
                "they do not write live memory, promote memory, or route live turns."
            ),
            disposition="evidence_adapter",
            evidence_only=True,
            claim_boundary=(
                "Advisory/evidence-only replay diagnostics; explicit Harness Core/Governor authority is required "
                "before any live promotion, publish, or routing use."
            ),
        ),
        _plane(
            plane_id="memory-kb-compiler-read-surface",
            surface="memory",
            plane_type="artifact_compiler",
            source_path="src/domain_chip_memory/spark_kb.py,src/domain_chip_memory/spark_kb_html.py,src/domain_chip_memory/cli.py",
            summary=(
                "Spark KB compilers and read reports materialize advisory snapshots and metadata; published release "
                "writes remain behind the memory promotion Harness Core/Governor checks."
            ),
            disposition="evidence_adapter",
            evidence_only=True,
            claim_boundary=(
                "Advisory/evidence-only read surface unless a published release path supplies explicit "
                "Harness Core/Governor authority."
            ),
        ),
        _plane(
            plane_id="memory-sidecar-candidates",
            surface="memory",
            plane_type="optional_sidecar",
            source_path="src/domain_chip_memory/memory_sidecars.py",
            summary=(
                "Graphiti/Mem0-style sidecars are optional comparators or adapters; default runtime remains disabled "
                "unless an explicit installer/profile attaches them."
            ),
            disposition="quarantined",
        ),
    ]


def build_memory_legacy_authority_inventory() -> dict[str, Any]:
    planes = build_memory_legacy_authority_planes()
    release_blockers = [plane for plane in planes if plane["disposition"] == "release_blocker" or plane["blockers"]]
    return {
        "schema_version": "legacy-authority-inventory-v1",
        "inventory_id": "domain-chip-memory-legacy-authority-inventory",
        "scope": {
            "owner_repo": OWNER_REPO,
            "surfaces": ["memory"],
        },
        "planes": planes,
        "summary": {
            "plane_count": len(planes),
            "release_blocker_count": len(release_blockers),
            "disposition_counts": {
                disposition: sum(1 for plane in planes if plane["disposition"] == disposition)
                for disposition in sorted({str(plane["disposition"]) for plane in planes})
            },
        },
        "release_gate": {
            "zero_high_agency_legacy_local_gates": not release_blockers,
            "ready_for_readiness_promotion": not release_blockers,
            "blockers": release_blockers,
        },
    }
