# Memory Systems Landscape

Date: 2026-03-22
Status: research-grounded

## Benchmark facts from primary sources

### LongMemEval

Source:

- `xiaowu0162/LongMemEval`

What matters:

- 500 questions
- six named categories plus abstention behavior
- `LongMemEval_s` is roughly 115k tokens and about 40 sessions
- benchmark is explicitly about long-term chat memory, knowledge updates, and temporal reasoning

Implication:

- this is the cleanest public benchmark for stale-fact replacement and time-aware retrieval

### LoCoMo

Source:

- `snap-research/locomo`

What matters:

- 10 very long conversations
- QA annotations plus event-summarization annotations
- categories cover single-hop, multi-hop, temporal, open-domain, and adversarial patterns

Implication:

- this benchmark is useful for long conversational recall and reasoning, but its released code and data are under `CC BY-NC 4.0`, so keep reuse policies conservative

### ConvoMem

Source:

- `Salesforce/ConvoMem` paper page on Hugging Face

What matters:

- 75,336 QA pairs
- categories include user facts, assistant recall, preferences, changing facts, implicit connections, and abstention
- the paper argues that full context remains strong up to about 150 conversations

Implication:

- this benchmark is a strong guardrail against overengineering memory where direct context is still the better trade

### GoodAI LTM Benchmark

Source:

- `GoodAI/goodai-ltm-benchmark`

What matters:

- it is a living benchmark and runnable harness for long-term memory and continual-learning capabilities of conversational agents
- it explicitly tests dynamic upkeep of memories and integration of information over long periods of time
- published configurations span multiple context sizes, including very large settings up to `500k`

Implication:

- this is a strong third benchmark for internal benchmark-stack pressure because it stress-tests long-span memory behavior rather than only one fixed public leaderboard slice

## Public system patterns worth learning from

### Supermemory

Sources:

- official research page
- public GitHub README

Useful patterns:

- chunk ingestion followed by explicit memory generation
- relational versioning such as `updates`, `extends`, and `derives`
- dual-layer time representation with both document date and event date
- hybrid search that retrieves atomic memories and then rehydrates source chunks

Important note:

- `Supermemory` remains one of the most important benchmark-native systems to learn from, especially on temporal versioning and rehydration
- the repo README also claims `#1` on `LoCoMo` and `ConvoMem`, but exact public numeric thresholds still need pinning

### Supermemory ASMR

Sources:

- user-provided writeup of the forthcoming ASMR release
- official research root for release tracking

Useful patterns:

- parallel reader ingestion
- specialized search roles
- source rehydration and verification
- explicit benchmark-first orchestration around retrieval quality

Important note:

- the writeup claims `98.60%` and `97.20%` on `LongMemEval_s`
- this is a pending experimental public release, not yet a pinned reproducible target in our registry

### Chronos

Source:

- arXiv paper `2603.16862`

Useful patterns:

- structured event tuples with datetime ranges
- event calendar plus turn calendar
- entity alias resolution
- temporal-aware iterative retrieval guidance

Important note:

- the paper reports `92.60%` and `95.60%` on `LongMemEvalS`
- current source is the paper; code and benchmark implementation still need pinning before we treat it as a reproducible baseline

### Mastra Observational Memory

Sources:

- Mastra research page
- Mastra framework repo

Useful patterns:

- stable context window with no per-turn dynamic retrieval injection
- Observer and Reflector background agents
- dense observation logs replacing older raw history

Important note:

- Mastra research claims `84.23%` on `LongMemEval` with `gpt-4o` and `94.87%` with `gpt-5-mini`
- this is the highest current public `LongMemEval` claim in the reviewed source sweep, but exact reproduction still needs to be handled carefully

### MemoryBench

Source:

- `supermemoryai/memorybench`

Useful patterns:

- pluggable benchmark interface
- pluggable provider interface
- normalized question types across benchmarks
- checkpointed pipeline with ingest, search, answer, evaluate, and report phases

Important note:

- the framework design is valuable even if we do not use their exact code

### Mem0

Source:

- `mem0ai/mem0`

Useful patterns:

- production-facing memory-layer framing
- Apache 2.0 licensing
- explicit efficiency framing versus full-context prompting

Important note:

- the README claims `+26% accuracy` over OpenAI Memory on `LOCOMO`
- that is useful as a baseline reference, but our chip should still normalize comparisons against canonical benchmark tasks

### A-Mem

Source:

- `WujiangXu/A-mem`

Useful patterns:

- agentic organization of memories
- linking and note-style evolution
- LoCoMo-focused experiment framing

Important note:

- this is a good source of architectural inspiration for organization and relation building, not proof of a universal production memory stack

## Strategic conclusions for this chip

1. Treat retrieval as the main bottleneck.
   The public frontier repeatedly points to retrieval quality, temporal filtering, and version resolution as the real unlocks.

2. Keep provenance attached to every memory atom.
   Every retrieved memory should point back to its originating session or turn so the answer layer can rehydrate detail when needed.

3. Separate benchmark-native wins from generic product wins.
   `ConvoMem` should remain a shadow guardrail because full context is still strong in smaller histories, while `GoodAI LTM Benchmark` is better suited as the third official stress benchmark.

4. Run mutation loops by failure bucket.
   The chip should mutate against slices such as `knowledge-update`, `temporal`, `abstention`, and `implicit_connection`, not only against overall accuracy.

5. Track license boundaries early.
   `MIT` and `Apache-2.0` sources are good learning surfaces.
   `LoCoMo` should stay in a more constrained evaluation lane because of its non-commercial license.
