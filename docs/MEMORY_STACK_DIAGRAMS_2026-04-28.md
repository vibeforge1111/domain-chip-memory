# Memory Stack Diagrams 2026-04-28

These diagrams describe the selected Spark persistent-memory architecture:

- `domain-chip-memory` remains the authority/control plane.
- Graphiti-compatible temporal graph is the first runtime sidecar.
- Mem0 is a shadow personal-memory baseline.
- Obsidian / LLM-wiki packets replace Cognee for now as the compiled project-knowledge layer.
- Cognee stays optional for later document/connector-scale graph-RAG needs.

## 1. System Architecture

```mermaid
flowchart TB
    user["User on Telegram"] --> telegram["Spark Telegram Bot"]
    telegram --> builder["Builder Runtime"]
    builder --> gate["Memory Capture Gate"]
    gate --> kernel["Spark Memory Kernel"]

    kernel --> dcm["domain-chip-memory\nAuthority Ledger"]
    dcm --> current["Current State Projection"]
    dcm --> entity["Entity State Projection"]
    dcm --> historical["Historical State Reads"]
    dcm --> evidence["Evidence + Event Store"]

    kernel --> graphiti["Graphiti-Compatible\nTemporal Graph Sidecar"]
    kernel --> wiki["Obsidian / LLM-Wiki\nCompiled Knowledge Packets"]
    kernel --> mem0["Mem0 Shadow Baseline"]

    current --> retrieve["Hybrid Retrieval + Rank Fusion"]
    entity --> retrieve
    historical --> retrieve
    evidence --> retrieve
    graphiti --> retrieve
    wiki --> retrieve
    mem0 -. shadow candidates .-> retrieve

    retrieve --> capsule["Capsule Compiler v2"]
    capsule --> answer["Final Answer\n+ Source Explanation"]
    answer --> telegram
```

## 2. Write Path

```mermaid
flowchart LR
    turn["Incoming Turn"] --> classify["Capture Gate\nclassify memory value"]

    classify --> discard["Discard\nno durable value"]
    classify --> raw["Raw Episode\nappend-only evidence"]
    classify --> state["Current / Entity State\nmutable truth"]
    classify --> event["Event Timeline\nactions, diagnostics, commitments"]
    classify --> knowledge["Project Knowledge\nresearch, decisions, handoffs"]

    raw --> ledger["domain-chip-memory\nappend-only ledger"]
    state --> ledger
    event --> ledger
    knowledge --> ledger

    raw --> graphiti["Graphiti Sidecar\nepisode ingest"]
    state --> graphiti
    event --> graphiti

    knowledge --> wiki["Obsidian / LLM-Wiki\npacket compiler"]

    raw -. shadow copy .-> mem0["Mem0 Shadow"]
    state -. shadow copy .-> mem0

    ledger --> projections["Current / Historical\nprojections"]
```

## 3. Read Path

```mermaid
flowchart TB
    question["User Question"] --> intent["Query Intent Router"]

    intent --> exact["Exact Current Fact"]
    intent --> mutable["Mutable Entity Fact"]
    intent --> historical["Historical / Previous Value"]
    intent --> relational["Relationship / Event Ordering"]
    intent --> broad["Open-Ended Next Action\nor Project Context"]

    exact --> current["Current State"]
    mutable --> entity["Entity State"]
    historical --> history["Historical State + Evidence"]
    relational --> graph["Graphiti Temporal Graph"]
    broad --> wiki["Obsidian / LLM-Wiki Packets"]
    broad --> evidence["Relevant Evidence / Events"]

    current --> fusion["Rank Fusion"]
    entity --> fusion
    history --> fusion
    graph --> fusion
    wiki --> fusion
    evidence --> fusion
    mem0["Mem0 Shadow Results"] -. compare only .-> fusion

    fusion --> budget["Source-Aware Context Budget"]
    budget --> capsule["Capsule Compiler v2"]
    capsule --> response["Answer"]
```

## 4. Authority Order

```mermaid
flowchart TD
    a1["1. Explicit current_state"] --> a2["2. Entity-scoped current_state"]
    a2 --> a3["3. Historical state\nonly for historical questions"]
    a3 --> a4["4. Recent conversation"]
    a4 --> a5["5. Retrieved evidence + events"]
    a5 --> a6["6. Graphiti temporal graph hits"]
    a6 --> a7["7. Obsidian / LLM-wiki packets"]
    a7 --> a8["8. Diagnostics / maintenance\nonly when relevant"]
    a8 --> a9["9. Workflow / mission residue\nadvisory only"]
    a9 --> a10["10. Mem0 shadow results\nnot authoritative until promoted"]
```

Rules:

- Clean diagnostics never close a user focus.
- Maintenance success never closes a user plan.
- Graph hits never override current state unless the query is historical or relational.
- Wiki packets can guide project reasoning, but mutable facts still need ledger-backed state.
- Mem0 shadow results can expose misses, but cannot answer as authority until promoted.

## 5. Sidecar Promotion Flow

```mermaid
flowchart LR
    candidate["Sidecar Candidate\nGraphiti / Mem0 / Cognee"] --> contract["Adapter Contract"]
    contract --> shadow["Shadow Mode"]
    shadow --> compare["Compare Against\nCurrent Runtime"]
    compare --> gates["Promotion Gates"]

    gates --> pass{"Passes?"}
    pass -- no --> keep_shadow["Keep Shadow\nor Remove"]
    pass -- yes --> limited["Limited Runtime Lane"]
    limited --> regression["Telegram + Benchmark\nRegression Pack"]
    regression --> promote{"No Regressions?"}
    promote -- no --> rollback["Rollback Feature Flag"]
    promote -- yes --> runtime["Promote Runtime Lane"]
```

Promotion gates:

- current vs stale conflict
- previous-value recall
- open-ended recall
- source-swamp resistance
- identity/entity resolution
- temporal event ordering
- source explanation
- Telegram acceptance probes

## 6. What Cognee Would Add Later

```mermaid
flowchart TB
    connectors["Large Connector / Document Corpus"] --> need{"Wiki packets enough?"}
    need -- yes --> wiki["Stay with Obsidian / LLM-Wiki"]
    need -- no --> cognee["Evaluate Cognee Free/Open-Source"]
    cognee --> shadow["Shadow Graph-RAG Adapter"]
    shadow --> compare["Compare vs Wiki + Graphiti"]
    compare --> decision{"Clear gain?"}
    decision -- no --> skip["Do not add Cognee"]
    decision -- yes --> limited["Limited Connector/Doc Memory Lane"]
```

Cognee should not enter the conversational-memory core unless it proves a clear advantage for connector-scale/document-scale memory.

## 7. Implementation Map

```mermaid
flowchart TD
    step1["1. MemorySidecarAdapter contract"] --> step2["2. Graphiti-compatible stub\nfeature flag off"]
    step2 --> step3["3. Evidence/event episode export"]
    step3 --> step4["4. Graphiti shadow retrieval"]
    step4 --> step5["5. Obsidian / LLM-wiki packet reader"]
    step5 --> step6["6. Mem0 shadow adapter"]
    step6 --> step7["7. Hybrid retrieval fusion"]
    step7 --> step8["8. Capsule compiler v2"]
    step8 --> step9["9. Promotion gates"]
    step9 --> step10["10. Telegram acceptance"]
```

This order keeps the architecture clean: first contract, then sidecar, then retrieval, then capsule, then live Telegram acceptance.
