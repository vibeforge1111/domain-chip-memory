from types import SimpleNamespace

from domain_chip_memory import (
    DisabledMemorySidecarAdapter,
    GraphitiCompatibleMemorySidecarAdapter,
    MemorySidecarEpisode,
    MemorySidecarHit,
    MemorySidecarRetrievalRequest,
    Mem0ShadowMemorySidecarAdapter,
    SparkMemorySDK,
    WIKI_PACKET_SOURCE_CLASS,
    build_default_memory_sidecars,
    build_memory_sidecar_contract_summary,
    build_wiki_packet_reader_contract_summary,
    build_sdk_contract_summary,
    memory_record_to_sidecar_episode,
    memory_records_to_sidecar_episodes,
    read_markdown_knowledge_packets,
    retrieve_markdown_knowledge_packets,
)
from domain_chip_memory.memory_sidecars import _graphiti_kuzu_db_path
from domain_chip_memory.sdk import EventRetrievalRequest, EvidenceRetrievalRequest, MemoryWriteRequest


def test_memory_sidecar_contract_declares_authority_boundaries() -> None:
    payload = build_memory_sidecar_contract_summary()

    assert payload["contract_name"] == "MemorySidecarAdapter"
    assert payload["authority_policy"]["domain_chip_memory"] == "source_of_truth"
    assert payload["runtime_sidecars"]["graphiti_temporal_graph"]["first_runtime_candidate"] is True
    assert payload["runtime_sidecars"]["mem0_shadow"]["mode"] == "shadow_baseline"
    assert payload["runtime_sidecars"]["cognee_optional"]["mode"] == "deferred"
    assert "GraphitiCompatibleMemorySidecarAdapter" in payload["adapter_implementations"]
    assert "Mem0ShadowMemorySidecarAdapter" in payload["adapter_implementations"]
    assert "ObsidianLlmWikiPacketReader" in payload["adapter_implementations"]
    assert payload["wiki_packet_reader_contract"]["authority"] == "supporting_not_authoritative"
    assert "memory_record_to_sidecar_episode" in payload["episode_export_methods"]
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


def test_graphiti_compatible_adapter_prepares_episode_payload_without_persisting() -> None:
    adapter = GraphitiCompatibleMemorySidecarAdapter(enabled=True, mode="shadow")
    episode = MemorySidecarEpisode(
        source_record_id="obs-plant-sol",
        source_class="current_state",
        text="The tiny desk plant is named Sol.",
        subject="human:telegram:12345",
        predicate="entity.name",
        session_id="session-1",
        turn_ids=["turn-1"],
        timestamp="2026-04-28T10:00:00Z",
        entity_keys=["named-object:tiny-desk-plant"],
        lifecycle={"valid_from": "2026-04-28T10:00:00Z"},
    )

    result = adapter.upsert_episode(episode)

    assert result.status == "prepared"
    assert result.trace["persisted"] is False
    payload = result.trace["graphiti_episode"]
    assert payload["group_id"] == "spark-memory"
    assert payload["episode_body"] == "The tiny desk plant is named Sol."
    assert payload["metadata"]["source_record_id"] == "obs-plant-sol"
    assert payload["metadata"]["entity_keys"] == ["named-object:tiny-desk-plant"]
    assert payload["metadata"]["authority"] == "supporting"


def test_graphiti_compatible_adapter_default_is_disabled() -> None:
    adapter = GraphitiCompatibleMemorySidecarAdapter()

    health = adapter.health()
    retrieval = adapter.retrieve(MemorySidecarRetrievalRequest(query="plant name", top_k=2))

    assert health.enabled is False
    assert health.status == "disabled"
    assert retrieval.hits == []
    assert retrieval.trace["status"] == "disabled"
    assert retrieval.trace["query_payload"]["num_results"] == 2


def test_graphiti_compatible_adapter_uses_injected_live_backend_without_becoming_authority() -> None:
    class FakeGraphitiClient:
        def __init__(self) -> None:
            self.added = []

        def add_episode(self, **payload):
            self.added.append(payload)
            return SimpleNamespace(uuid="episode-1")

        def search(self, query: str, num_results: int = 10):
            return [
                SimpleNamespace(
                    uuid="edge-1",
                    fact="The GTM launch depends on creator approvals.",
                    score=0.82,
                    valid_at="2026-04-29T10:00:00Z",
                    invalid_at=None,
                )
            ][:num_results]

    client = FakeGraphitiClient()
    adapter = GraphitiCompatibleMemorySidecarAdapter(
        enabled=True,
        mode="shadow",
        backend="kuzu",
        db_path=":memory:",
        client=client,
    )
    episode = MemorySidecarEpisode(
        source_record_id="obs-gtm-blocker",
        source_class="current_state",
        text="The GTM launch blocker is creator approvals.",
        subject="human:telegram:12345",
        predicate="entity.blocker",
        entity_keys=["named-object:gtm-launch"],
        timestamp="2026-04-29T10:00:00Z",
    )

    upsert = adapter.upsert_episode(episode)
    retrieval = adapter.retrieve(
        MemorySidecarRetrievalRequest(
            query="What is blocking the GTM launch?",
            subject="human:telegram:12345",
            scope="entity.blocker",
            entity_keys=["named-object:gtm-launch"],
            top_k=3,
        )
    )
    health = adapter.health()

    assert upsert.status == "persisted"
    assert upsert.trace["backend_configured"] is True
    assert client.added[0]["group_id"] == "spark-memory"
    assert retrieval.trace["status"] == "ok"
    assert retrieval.trace["backend_configured"] is True
    assert retrieval.hits[0].source_class == "graphiti_temporal_graph"
    assert retrieval.hits[0].provenance["source"] == "graphiti"
    assert retrieval.hits[0].validity["valid_at"] == "2026-04-29T10:00:00Z"
    assert retrieval.hits[0].metadata["authority"] == "supporting_not_authoritative"
    assert health.status == "ok"
    assert health.details["authority"] == "not_authoritative"


def test_graphiti_kuzu_db_path_uses_database_file_inside_directory(tmp_path) -> None:
    db_dir = tmp_path / "graphiti" / "kuzu"
    db_dir.mkdir(parents=True)

    resolved = _graphiti_kuzu_db_path(str(db_dir))

    assert resolved == str(db_dir / "graphiti.kuzu")


def test_default_sidecars_keep_graphiti_feature_flag_off_by_default() -> None:
    sidecars = build_default_memory_sidecars()

    graphiti = sidecars["graphiti_temporal_graph"]
    mem0 = sidecars["mem0_shadow"]

    assert graphiti.health().status == "disabled"
    assert mem0.health().status == "disabled"


def test_mem0_shadow_adapter_prepares_memory_payload_without_persisting() -> None:
    adapter = Mem0ShadowMemorySidecarAdapter(enabled=True, mode="shadow", user_id="human:telegram:12345")
    episode = MemorySidecarEpisode(
        source_record_id="obs-plant-sol",
        source_class="current_state",
        text="The tiny desk plant is named Sol.",
        subject="human:telegram:12345",
        predicate="entity.name",
        session_id="session-1",
        turn_ids=["turn-1"],
        entity_keys=["named-object:tiny-desk-plant"],
    )

    upsert = adapter.upsert_episode(episode)
    retrieval = adapter.retrieve(
        MemorySidecarRetrievalRequest(
            query="What is the plant named?",
            subject="human:telegram:12345",
            entity_keys=["named-object:tiny-desk-plant"],
            top_k=3,
        )
    )

    assert upsert.status == "prepared"
    assert upsert.trace["persisted"] is False
    assert upsert.trace["mem0_memory"]["user_id"] == "human:telegram:12345"
    assert upsert.trace["mem0_memory"]["metadata"]["authority"] == "shadow_not_authoritative"
    assert retrieval.trace["status"] == "prepared"
    assert retrieval.trace["query_payload"]["limit"] == 3
    assert retrieval.hits == []


def test_memory_record_to_sidecar_episode_preserves_evidence_provenance() -> None:
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="update",
            subject="human:telegram:12345",
            predicate="entity.name",
            value="Sol",
            timestamp="2026-04-28T10:00:00Z",
            metadata={
                "entity_key": "named-object:tiny-desk-plant",
                "source_surface": "telegram",
            },
        )
    )
    record = sdk.retrieve_evidence(
        EvidenceRetrievalRequest(subject="human:telegram:12345", predicate="entity.name")
    ).items[0]

    episode = memory_record_to_sidecar_episode(record)

    assert episode.source_record_id == record.observation_id
    assert episode.source_class == "retrieved_evidence"
    assert episode.subject == "human:telegram:12345"
    assert episode.predicate == "entity.name"
    assert episode.entity_keys == ["named-object:tiny-desk-plant"]
    assert episode.lifecycle["valid_from"] == "2026-04-28T10:00:00Z"
    assert episode.metadata["memory_role"] == "structured_evidence"
    assert episode.metadata["sidecar_episode_export"] is True


def test_memory_record_to_sidecar_episode_maps_event_records() -> None:
    sdk = SparkMemorySDK()
    sdk.write_event(
        MemoryWriteRequest(
            text="",
            operation="event",
            subject="human:telegram:12345",
            predicate="diagnostics.scan",
            value="clean",
            timestamp="2026-04-28T10:01:00Z",
            event_time="2026-04-28T10:01:00Z",
        )
    )
    record = sdk.retrieve_events(EventRetrievalRequest(subject="human:telegram:12345", limit=1)).items[0]

    episode = memory_record_to_sidecar_episode(record)

    assert episode.source_record_id == record.event_id
    assert episode.source_class == "retrieved_events"
    assert episode.metadata["memory_role"] == "event"
    assert episode.lifecycle["event_time"] == "2026-04-28T10:01:00Z"


def test_memory_records_to_sidecar_episodes_batch_exports_records() -> None:
    sdk = SparkMemorySDK()
    sdk.write_observation(
        MemoryWriteRequest(
            text="",
            operation="update",
            subject="human:telegram:12345",
            predicate="profile.current_focus",
            value="persistent memory quality evaluation",
            timestamp="2026-04-28T10:02:00Z",
            metadata={"memory_role": "current_state"},
        )
    )
    records = sdk.retrieve_evidence(EvidenceRetrievalRequest(subject="human:telegram:12345", limit=5)).items

    episodes = memory_records_to_sidecar_episodes(records)

    assert len(episodes) == 1
    assert episodes[0].text
    assert episodes[0].source_record_id == records[0].observation_id


def test_wiki_packet_reader_loads_obsidian_markdown_with_provenance(tmp_path) -> None:
    note = tmp_path / "memory-architecture.md"
    note.write_text(
        """---
title: Persistent Memory Architecture
tags: memory, spark
---
# Persistent Memory Architecture

Current state outranks workflow residue.
Graphiti is a temporal graph sidecar.
""",
        encoding="utf-8",
    )

    packets = read_markdown_knowledge_packets([tmp_path])

    assert len(packets) == 1
    assert packets[0].title == "Persistent Memory Architecture"
    assert packets[0].source_class == WIKI_PACKET_SOURCE_CLASS
    assert packets[0].metadata["file_name"] == "memory-architecture.md"
    assert "memory" in packets[0].tags


def test_wiki_packet_retrieval_scores_relevant_packets_without_authority(tmp_path) -> None:
    (tmp_path / "architecture.md").write_text(
        "# Spark Memory Stack\n\nCurrent state wins over old workflow_state.",
        encoding="utf-8",
    )
    (tmp_path / "unrelated.md").write_text("# Gardening\n\nWater the desk plant weekly.", encoding="utf-8")

    result = retrieve_markdown_knowledge_packets(
        paths=[tmp_path],
        query="Why should current_state outrank workflow_state?",
        top_k=2,
    )

    assert result.trace["source_class"] == WIKI_PACKET_SOURCE_CLASS
    assert result.trace["packet_count"] == 2
    assert len(result.hits) == 1
    assert result.hits[0].title == "Spark Memory Stack"
    assert result.hits[0].metadata["authority"] == "supporting_not_authoritative"
    assert result.hits[0].provenance["source_path"].endswith("architecture.md")


def test_wiki_packet_contract_keeps_packets_supporting_only() -> None:
    contract = build_wiki_packet_reader_contract_summary()

    assert contract["source_class"] == WIKI_PACKET_SOURCE_CLASS
    assert contract["authority"] == "supporting_not_authoritative"
    assert "Wiki packets cannot override current_state for mutable user facts." in contract["non_override_rules"]
