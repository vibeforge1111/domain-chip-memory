from domain_chip_memory import (
    DisabledMemorySidecarAdapter,
    MemorySidecarEpisode,
    MemorySidecarHit,
    MemorySidecarRetrievalRequest,
    build_memory_sidecar_contract_summary,
    build_sdk_contract_summary,
)


def test_memory_sidecar_contract_declares_authority_boundaries() -> None:
    payload = build_memory_sidecar_contract_summary()

    assert payload["contract_name"] == "MemorySidecarAdapter"
    assert payload["authority_policy"]["domain_chip_memory"] == "source_of_truth"
    assert payload["runtime_sidecars"]["graphiti_temporal_graph"]["first_runtime_candidate"] is True
    assert payload["runtime_sidecars"]["mem0_shadow"]["mode"] == "shadow_baseline"
    assert payload["runtime_sidecars"]["cognee_optional"]["mode"] == "deferred"
    assert "source_swamp_resistance" in payload["promotion_gates"]


def test_sdk_contract_links_to_memory_sidecars_without_making_them_authority() -> None:
    payload = build_sdk_contract_summary()

    sidecar_contract = payload["sidecar_contract"]
    assert sidecar_contract["contract_name"] == "MemorySidecarAdapter"
    assert sidecar_contract["sidecar_authority"] == "supporting_or_shadow_until_promoted"
    assert "graphiti_temporal_graph" in sidecar_contract["runtime_sidecars"]
    assert "mem0_shadow" in sidecar_contract["runtime_sidecars"]
    assert sidecar_contract["deferred_sidecars"] == ["cognee_optional"]


def test_disabled_sidecar_adapter_is_contract_safe_noop() -> None:
    adapter = DisabledMemorySidecarAdapter(sidecar_name="graphiti_temporal_graph")
    episode = MemorySidecarEpisode(
        source_record_id="obs-1",
        source_class="structured_evidence",
        text="The tiny desk plant is named Sol.",
        subject="human:telegram:12345",
        predicate="entity.name",
        entity_keys=["named-object:tiny-desk-plant"],
    )

    upsert = adapter.upsert_episode(episode)
    retrieval = adapter.retrieve(
        MemorySidecarRetrievalRequest(
            query="What was the plant called before?",
            subject="human:telegram:12345",
            entity_keys=["named-object:tiny-desk-plant"],
            top_k=3,
        )
    )
    health = adapter.health()

    assert upsert.status == "disabled"
    assert upsert.sidecar_ids == []
    assert upsert.trace["persisted"] is False
    assert retrieval.hits == []
    assert retrieval.trace["status"] == "disabled"
    assert health.enabled is False
    assert health.details["authority"] == "not_authoritative"


def test_sidecar_shadow_compare_reports_missing_and_sidecar_only_ids() -> None:
    adapter = DisabledMemorySidecarAdapter(sidecar_name="mem0_shadow", mode="shadow")
    sidecar_hit = MemorySidecarHit(
        sidecar_name="mem0_shadow",
        source_class="mem0_shadow",
        source_record_id="sidecar-1",
        text="Shadow memory candidate",
        score=0.5,
        provenance={"source": "mem0"},
    )

    comparison = adapter.shadow_compare(
        query="plant name",
        local_hits=[{"observation_id": "local-1"}, {"source_record_id": "shared-1"}],
        sidecar_hits=[
            sidecar_hit,
            MemorySidecarHit(
                sidecar_name="mem0_shadow",
                source_class="mem0_shadow",
                source_record_id="shared-1",
                text="Shared memory candidate",
                score=0.7,
                provenance={"source": "mem0"},
            ),
        ],
    )

    assert comparison.local_hit_count == 2
    assert comparison.sidecar_hit_count == 2
    assert comparison.overlap_record_ids == ["shared-1"]
    assert comparison.missing_from_sidecar_record_ids == ["local-1"]
    assert comparison.sidecar_only_record_ids == ["sidecar-1"]
