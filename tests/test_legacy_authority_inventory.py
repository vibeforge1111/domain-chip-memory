from __future__ import annotations

import json
import sys

from domain_chip_memory import cli
from domain_chip_memory.legacy_authority_inventory import (
    build_memory_legacy_authority_inventory,
    build_memory_legacy_authority_planes,
)


def _has_high_agency_risk(plane: dict) -> bool:
    return any(bool(value) for value in dict(plane.get("authority_risk") or {}).values())


def test_memory_legacy_authority_inventory_is_release_ready() -> None:
    inventory = build_memory_legacy_authority_inventory()
    allowed_dispositions = {"removed", "quarantined", "evidence_adapter", "canonical_consumer"}

    assert inventory["schema_version"] == "legacy-authority-inventory-v1"
    assert inventory["scope"]["owner_repo"] == "domain-chip-memory"
    assert inventory["scope"]["surfaces"] == ["memory"]
    assert inventory["summary"]["plane_count"] == len(inventory["planes"])
    assert inventory["summary"]["plane_count"] >= 8
    assert inventory["summary"]["release_blocker_count"] == 0
    assert inventory["release_gate"]["zero_high_agency_legacy_local_gates"] is True
    assert inventory["release_gate"]["ready_for_readiness_promotion"] is True
    assert {plane["disposition"] for plane in inventory["planes"]} <= allowed_dispositions


def test_memory_publish_and_ship_are_governor_consumers() -> None:
    planes = {plane["plane_id"]: plane for plane in build_memory_legacy_authority_planes()}

    for plane_id in (
        "legacy-plane:memory-promotion-publish",
        "legacy-plane:memory-promotion-ship",
    ):
        plane = planes[plane_id]
        assert plane["disposition"] == "canonical_consumer"
        assert _has_high_agency_risk(plane)
        assert plane["harness_binding"]["governor_required"] is True
        assert plane["harness_binding"]["consumer_of_governor"] is True
        assert plane["harness_binding"]["ledger_required"] is True
        assert plane["blockers"] == []


def test_memory_sdk_write_subsystem_requires_upstream_authority() -> None:
    planes = {plane["plane_id"]: plane for plane in build_memory_legacy_authority_planes()}
    sdk_plane = planes["legacy-plane:memory-sdk-write-subsystem"]

    assert sdk_plane["disposition"] == "canonical_consumer"
    assert sdk_plane["authority_risk"]["can_write_memory"] is True
    assert sdk_plane["harness_binding"]["governor_required"] is True
    assert sdk_plane["harness_binding"]["upstream_authority_required"] is True
    assert sdk_plane["harness_binding"]["consumer_of_governor"] is True


def test_memory_old_replay_kb_and_benchmark_planes_are_evidence_only_or_quarantined() -> None:
    planes = build_memory_legacy_authority_planes()
    passive = [
        plane
        for plane in planes
        if plane["disposition"] in {"evidence_adapter", "quarantined"}
    ]

    assert len(passive) >= 5
    for plane in passive:
        assert not _has_high_agency_risk(plane)
        assert plane["blockers"] == []
        if plane["disposition"] == "evidence_adapter":
            assert plane["harness_binding"]["evidence_only"] is True


def test_shadow_and_kb_inventory_planes_have_advisory_claim_boundaries() -> None:
    planes = {plane["plane_id"]: plane for plane in build_memory_legacy_authority_planes()}

    for plane_id in (
        "legacy-plane:memory-shadow-replay-adapters",
        "legacy-plane:memory-kb-compiler-read-surface",
    ):
        plane = planes[plane_id]
        rendered = " ".join(
            [
                str(plane.get("summary") or ""),
                str(plane.get("claim_boundary") or ""),
            ]
        ).lower()

        assert plane["harness_binding"]["evidence_only"] is True
        assert "advisory/evidence-only" in rendered
        assert "governed memory" not in rendered
        assert "governed snapshots" not in rendered
        assert "authoritative" not in rendered


def test_legacy_authority_inventory_cli_command_runs(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["domain_chip_memory.cli", "legacy-authority-inventory"])

    cli.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "legacy-authority-inventory-v1"
    assert payload["release_gate"]["ready_for_readiness_promotion"] is True
