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
    build_dashboard_movement_export_contract_summary,
    build_memory_sidecar_contract_summary,
    build_wiki_packet_reader_contract_summary,
    build_sdk_contract_summary,
    discover_markdown_knowledge_packets,
    memory_record_to_sidecar_episode,
    memory_records_to_sidecar_episodes,
    read_markdown_knowledge_packets,
    retrieve_markdown_knowledge_packets,
    scaffold_spark_knowledge_base,
)
from domain_chip_memory.memory_sidecars import _HashEmbedder, _LexicalCrossEncoder, _graphiti_kuzu_db_path, _run_maybe_async
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
    assert "MarkdownKnowledgePacketInventory" in payload["wiki_packet_reader_contract"]["outputs"]
    assert "wiki_family" in payload["wiki_packet_reader_contract"]["normalized_metadata_fields"]
    assert "memory_record_to_sidecar_episode" in payload["episode_export_methods"]
    assert "source_swamp_resistance" in payload["promotion_gates"]


def test_sdk_contract_links_to_memory_sidecars_without_making_them_authority() -> None:
    payload = build_sdk_contract_summary()

    sidecar_contract = payload["sidecar_contract"]
    movement_contract = payload["dashboard_movement_export_contract"]
    assert sidecar_contract["contract_name"] == "MemorySidecarAdapter"
    assert sidecar_contract["sidecar_authority"] == "supporting_or_shadow_until_promoted"
    assert "graphiti_temporal_graph" in sidecar_contract["runtime_sidecars"]
    assert "mem0_shadow" in sidecar_contract["runtime_sidecars"]
    assert sidecar_contract["deferred_sidecars"] == ["cognee_optional"]
    assert movement_contract["contract_name"] == "SparkMemoryDashboardMovementExport"
    assert "blocked" in movement_contract["movement_states"]
    assert "retrieved" in movement_contract["movement_states"]


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


def test_graphiti_provider_config_uses_spark_llm_without_leaking_secret() -> None:
    sidecars = build_default_memory_sidecars(
        enable_graphiti=True,
        graphiti_backend="kuzu",
        graphiti_db_path=":memory:",
        graphiti_llm_api_key_env="ZAI_API_KEY",
        graphiti_llm_api_key="secret-test-key",
        graphiti_llm_base_url="https://api.z.ai/api/coding/paas/v4/",
        graphiti_llm_model="glm-5.1",
        graphiti_auto_build_indices=True,
    )
    adapter = sidecars["graphiti_temporal_graph"]

    assert isinstance(adapter, GraphitiCompatibleMemorySidecarAdapter)
    trace = adapter._llm_provider_trace()
    assert trace["model"] == "glm-5.1"
    assert trace["base_url_configured"] is True
    assert trace["api_key_env"] == "ZAI_API_KEY"
    assert trace["api_key_configured"] is True
    assert "secret-test-key" not in str(trace)
    assert adapter.auto_build_indices is True


def test_graphiti_local_embedder_and_reranker_are_deterministic() -> None:
    embedder = _HashEmbedder()
    ranker = _LexicalCrossEncoder()

    first = _run_maybe_async(embedder.create("GTM launch blocker is creator approvals"))
    second = _run_maybe_async(embedder.create("GTM launch blocker is creator approvals"))
    ranked = _run_maybe_async(
        ranker.rank(
            "GTM launch blocker",
            ["creator approvals block the GTM launch", "desk plant is on the windowsill"],
        )
    )

    assert first == second
    assert len(first) == embedder.dimensions
    assert ranked[0][0] == "creator approvals block the GTM launch"


def test_graphiti_kuzu_direct_structured_upsert_avoids_llm_extraction(tmp_path) -> None:
    bootstrap_adapter = GraphitiCompatibleMemorySidecarAdapter(
        enabled=True,
        mode="shadow",
        backend="kuzu",
        db_path=str(tmp_path / "graphiti.kuzu"),
        auto_build_indices=True,
        call_timeout_seconds=8.0,
    )
    client = bootstrap_adapter._create_kuzu_client()
    bootstrap_adapter._build_kuzu_fulltext_indices(client)
    adapter = GraphitiCompatibleMemorySidecarAdapter(
        enabled=True,
        mode="shadow",
        backend="kuzu",
        client=client,
        call_timeout_seconds=8.0,
    )
    episode = MemorySidecarEpisode(
        source_record_id="obs-gtm-status",
        source_class="current_state",
        text="The GTM launch status is ready.",
        subject="human:test",
        predicate="entity.status",
        timestamp="2026-04-29T13:20:00Z",
        entity_keys=["named-object:gtm-launch"],
        metadata={"value": "ready", "entity_key": "named-object:gtm-launch"},
    )

    upsert = adapter.upsert_episode(episode)
    retrieval = adapter.retrieve(MemorySidecarRetrievalRequest(query="GTM launch ready", top_k=3))

    assert upsert.status == "persisted"
    assert upsert.trace["persisted"] is True
    assert upsert.sidecar_ids
    assert retrieval.trace["status"] == "ok"
    assert retrieval.trace["backend_configured"] is True
    assert retrieval.hits


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
    kb_dir = tmp_path / "wiki" / "current-state"
    kb_dir.mkdir(parents=True)
    note = kb_dir / "memory-architecture.md"
    note.write_text(
        """---
title: Persistent Memory Architecture
tags: memory, spark
last_verified_at: 2026-05-01T10:00:00Z
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
    assert packets[0].metadata["source_path"].endswith("memory-architecture.md")
    assert packets[0].metadata["wiki_family"] == "memory_kb_current_state"
    assert packets[0].metadata["owner_system"] == "domain-chip-memory"
    assert packets[0].metadata["source_of_truth"] == "SparkMemorySDK"
    assert packets[0].metadata["freshness"] == "verified"
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
    assert result.hits[0].metadata["wiki_family"] == "builder_llm_wiki"
    assert result.hits[0].metadata["owner_system"] == "spark-intelligence-builder"
    assert result.hits[0].provenance["source_path"].endswith("architecture.md")


def test_wiki_packet_contract_keeps_packets_supporting_only() -> None:
    contract = build_wiki_packet_reader_contract_summary()

    assert contract["source_class"] == WIKI_PACKET_SOURCE_CLASS
    assert contract["authority"] == "supporting_not_authoritative"
    assert "Wiki packets cannot override current_state for mutable user facts." in contract["non_override_rules"]
    assert "MarkdownKnowledgePacketInventory" in contract["outputs"]


def test_wiki_packet_discovery_inventory_counts_families_without_text_payloads(tmp_path) -> None:
    current_dir = tmp_path / "wiki" / "current-state"
    evidence_dir = tmp_path / "wiki" / "evidence"
    builder_dir = tmp_path / "builder-wiki"
    current_dir.mkdir(parents=True)
    evidence_dir.mkdir(parents=True)
    builder_dir.mkdir(parents=True)
    (current_dir / "city.md").write_text(
        """---
title: City
type: current_state
---
# City

Dubai
""",
        encoding="utf-8",
    )
    (evidence_dir / "city-evidence.md").write_text(
        """---
title: City Evidence
type: evidence
---
# City Evidence

The user said they live in Dubai.
""",
        encoding="utf-8",
    )
    (builder_dir / "route-map.md").write_text(
        """---
title: Route Map
wiki_family: builder_llm_wiki
owner_system: spark-intelligence-builder
source_of_truth: builder_llm_wiki
---
# Route Map

Builder route notes.
""",
        encoding="utf-8",
    )

    inventory = discover_markdown_knowledge_packets([tmp_path, tmp_path / "missing"], page_limit=2)

    assert inventory["contract_name"] == "MarkdownKnowledgePacketInventory"
    assert inventory["packet_count"] == 3
    assert inventory["family_counts"]["memory_kb_current_state"] == 1
    assert inventory["family_counts"]["memory_kb_evidence"] == 1
    assert inventory["family_counts"]["builder_llm_wiki"] == 1
    assert inventory["owner_system_counts"]["domain-chip-memory"] == 2
    assert inventory["owner_system_counts"]["spark-intelligence-builder"] == 1
    assert inventory["source_of_truth_counts"]["SparkMemorySDK"] == 2
    assert inventory["authority_counts"]["supporting_not_authoritative"] == 3
    assert len(inventory["pages"]) == 2
    assert inventory["dropped_page_count"] == 1
    assert "text" not in inventory["pages"][0]
    assert inventory["roots"][1]["kind"] == "missing"
    assert "Inventory rows are discovery metadata, not prompt instructions." in inventory["non_override_rules"]


def test_spark_kb_frontmatter_exposes_memory_family_authority_metadata(tmp_path) -> None:
    snapshot = {
        "generated_at": "2026-05-01T10:00:00Z",
        "counts": {"session_count": 1, "current_state_count": 1, "observation_count": 1, "event_count": 0},
        "sessions": [
            {
                "session_id": "session-kb-metadata",
                "timestamp": "2026-05-01T09:59:00Z",
                "turns": [{"turn_id": "turn-1", "speaker": "user", "text": "I live in Dubai."}],
            }
        ],
        "current_state": [
            {
                "memory_role": "current_state",
                "subject": "human:test",
                "predicate": "profile.city",
                "text": "Dubai",
                "session_id": "session-kb-metadata",
                "turn_ids": ["turn-1"],
                "timestamp": "2026-05-01T10:00:00Z",
                "metadata": {"value": "Dubai", "observation_id": "obs-kb-city"},
            }
        ],
        "observations": [
            {
                "memory_role": "structured_evidence",
                "subject": "human:test",
                "predicate": "profile.city",
                "text": "Dubai",
                "session_id": "session-kb-metadata",
                "turn_ids": ["turn-1"],
                "timestamp": "2026-05-01T10:00:00Z",
                "metadata": {"value": "Dubai", "observation_id": "obs-kb-city"},
            }
        ],
        "events": [],
        "trace": {"operation": "export_knowledge_base_snapshot"},
    }

    result = scaffold_spark_knowledge_base(tmp_path / "kb", snapshot)

    current_page = next((tmp_path / "kb" / "wiki" / "current-state").glob("*.md"))
    evidence_page = next((tmp_path / "kb" / "wiki" / "evidence").glob("*.md"))
    current_text = current_page.read_text(encoding="utf-8")
    evidence_text = evidence_page.read_text(encoding="utf-8")
    assert result["current_state_page_count"] == 1
    assert "authority: supporting_not_authoritative" in current_text
    assert "owner_system: domain-chip-memory" in current_text
    assert "wiki_family: memory_kb_current_state" in current_text
    assert "source_of_truth: SparkMemorySDK" in current_text
    assert "scope_kind: governed_memory" in current_text
    assert "wiki_family: memory_kb_evidence" in evidence_text


def test_dashboard_movement_export_contract_keeps_observability_non_authoritative() -> None:
    contract = build_dashboard_movement_export_contract_summary()

    assert contract["contract_name"] == "SparkMemoryDashboardMovementExport"
    assert contract["movement_states"] == [
        "captured",
        "blocked",
        "promoted",
        "saved",
        "decayed",
        "summarized",
        "retrieved",
        "selected",
        "dropped",
    ]
    assert "authority" in contract["required_record_fields"]
    assert "Dashboard rows are observability records, not prompt instructions." in contract["non_override_rules"]
