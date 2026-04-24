# Session Handoff 2026-04-23

## Latest Continuation Checkpoint - 2026-04-24

Continue from branch `feature/domain-chip-family-visit-memory`.

The 2026-04-24 continuation closed the known `conv44-47` answer-surface regression and added the first kinship/shared-time hardening pass for Telegram-like memory questions.

What changed in code:

- exact/entity/graph answer candidates no longer promote non-temporal support or relationship spans for `when ...` questions when a normalized time is available
- kinship aliases now normalize across `mom` / `mum` / `mother` and `dad` / `father`
- family visit detection now covers `came over`, `dropped by`, and shared-time phrasing such as `spent time with`, `spend time with`, and `hung out`
- family-member aggregation now works for questions like `Which family members did I spend time with recently?`, not just explicit `visited` wording

Tracked files modified in this checkpoint:

- `src/domain_chip_memory/memory_conversational_index.py`
- `src/domain_chip_memory/memory_conversational_retrieval.py`
- `src/domain_chip_memory/memory_conversational_shadow_eval.py`
- `tests/test_conversational_index.py`

Important benchmark/product evidence:

- reconstructed `conv44+47` heuristic slice: summary `7/90`, exact-turn `9/90`, entity `9/90`, graph `8/90`, fused `11/90`, fused regressions vs summary `0`, fused improvements vs summary `4`
- sensitive heuristic 6-probe after kinship hardening: summary `2/6`, exact-turn `4/6`, entity `5/6`, graph `4/6`, fused `6/6`
- sensitive MiniMax 6-probe after kinship hardening: summary `2/6`, exact-turn `3/6`, entity `5/6`, graph `4/6`, fused `6/6`
- Telegram shadow report after kinship hardening: accepted `14`, rejected `0`, skipped `2`, evidence `12/12`, expected evidence `12/12`, current state `1/1`, historical state `1/1`
- live Telegram direct chat probe was completed through the canonical Builder bridge path on port `8788`; `localhost:8080` was confirmed to be legacy fallback/no listener, not the healthy memory runtime path for this session

Builder/Telegram runtime follow-up:

- canonical Telegram ingress remains `spark-telegram-bot`; do not start a second receiver
- Builder memory substrate was healthy via `python -m spark_intelligence.cli memory status --home .tmp-home-live-telegram-real --json`
- direct memory smoke through `domain_chip_memory` succeeded, which narrowed the live failure to Builder Telegram routing/classification rather than memory storage
- `spark-intelligence-builder` now classifies recent family/shared-time messages into `profile.recent_family_members`
- authorized Telegram shadow write/read now routes through memory:
  - write response: `I'll remember you recently spent time with: mother, sister.`
  - read response: `You recently spent time with mother, sister.`
- a real Telegram Bot API outbound status ping succeeded after the routing fix; no duplicate receiver was started

Artifacts from this checkpoint:

- `artifacts/telegram_multi_party_probe_report_after_candidate_guard.json`
- `artifacts/telegram_multi_party_probe_report_after_kinship_hardening.json`
- `$SPARK_HOME\artifacts\locomo-unseen-slice\fused-heuristic-sensitive-6probe-after-kinship-hardening.json`
- `$SPARK_HOME\artifacts\locomo-unseen-slice\fused-minimax-sensitive-6probe-after-kinship-hardening.json`

Verification commands that passed:

```powershell
python -m pytest tests/test_conversational_index.py -k "kinship_aliases or mom_question or family_shared_time or family_visit_members_for_conv47 or extracts_family_visit_events_for_conv47 or retrieve_conversational_entries_finds_full_family_hobby_turns_for_conv48" -q
python -m pytest tests/test_conversational_index.py -k "exact_turn_hybrid_shadow_packets_add_conversational_evidence_for_exact_fact_question or exact_turn_hybrid_shadow_packets_promote_temporal_surface_for_conv47_trip_question or do_not_promote_non_temporal_support_span_for_when_question or fused_conversational_hybrid_shadow_packets or entity_linked_hybrid_shadow_packets" -q
python -m pytest tests/test_typed_temporal_graph_memory.py tests/test_typed_temporal_graph_retrieval.py -q
python -m pytest tests/test_memory_systems.py -k "summary_synthesis_locomo_conv48_social_memory_questions_recover_exact_lists_and_anchors or conv42_temporal_anchor_questions_recover_older_event_grounding or conv49_typed_fact_and_count_questions_recover_exact_answers or unseen_conv47_recovers_exact_supportable_answers" -q
python -m pytest tests/test_providers.py -k "prefers_in_year_candidate_over_bare_year_for_when_question or preserves_matching_temporal_answer_candidate_for_when_question or expand_answer_from_context_preserves_multiline_beam_event_ordering_surface or expand_answer_from_context_preserves_beam_temporal_surface_with_dates" -q
python -m pytest tests/test_memory_systems.py -k "longmemeval_preference_candidates_cover_151_175_single_session_lane or longmemeval_aggregate_candidates_cover_176_200_slice or longmemeval_summary_synthesis_candidates_cover_226_250_frontier_slice" -q
python -m domain_chip_memory.cli validate-spark-shadow-replay docs/examples/spark_shadow/telegram_multi_party_probe_pack.json
python -m domain_chip_memory.cli run-spark-shadow-report docs/examples/spark_shadow/telegram_multi_party_probe_pack.json --write artifacts\telegram_multi_party_probe_report_after_kinship_hardening.json
```

Builder verification commands that passed:

```powershell
python -m pytest tests/test_telegram_generic_memory.py -k "family_shared_time or generic_relationship_memory_before_provider_resolution or generic_plan_query" -q
python -m pytest tests/test_memory_orchestrator.py -k "profile_fact" -q
```

Recommended next step:

1. Keep this patch narrow and land it after review.
2. Review and land the matching `spark-intelligence-builder` routing patch alongside this domain-chip-memory hardening.
3. Add one or two more real Telegram write/read probes only after confirming they exercise the Builder bridge, not the legacy `8080` fallback.
4. Then move to the next architecture slice: temporal validity windows for superseded facts.

## What Happened Today

Today was a real architecture-and-product session, not just benchmark paperwork.

The biggest concrete outcome is that the product-facing Telegram shadow replay gate is now green, while the benchmark-facing conversational architecture remains additive and still anchored on `summary_synthesis_memory`.

The work split into three real tracks:

- product-facing bridge work
- conversational architecture hardening
- benchmark/regression verification

## Today's Wins

### 1. The Telegram product-facing gate is now clean

Checked pack:

- `docs/examples/spark_shadow/telegram_multi_party_probe_pack.json`

Current report result:

- accepted writes: `12/14`
- rejected writes: `0`
- evidence hit rate: `10/10`
- evidence expected-match rate: `10/10`
- historical state: `1/1`
- current state: `1/1`

This is the first time the checked Telegram multi-party probe pack is fully green as a product-facing regression gate.

### 2. Conversational evidence now survives into product-facing retrieval

Before today, typed conversational bridge observations were helping write acceptance but were not reliably present on the later retrieval surface.

That is now fixed.

The key product-facing checkpoint was:

- `6b37592` `Bridge conversational evidence into spark shadow replay`

What it changed:

- bridge observations are rebuilt from the retained runtime sample
- product-facing evidence retrieval can now see alias / commitment / negation / uncertainty / reported speech / relationship-edge evidence
- Telegram shadow replay is now using the conversational structure instead of only benefitting from it at ingest time

### 3. The remaining Telegram answer-surface misses were closed

The follow-up checkpoint was:

- `0521738` `Tighten Telegram shadow replay surfaces`

What it changed:

- `location` values no longer carry relative-time residue like `Dubai last month`
- conversational turns like:
  - `Yesterday I mailed an appreciation letter to the community center.`
  - `I still feel close to her when I visit the rose garden.`
  - `Leo and I are presenting the prototype on Tuesday.`
  now promote as structured memory instead of falling through as unsupported
- bridge evidence is ranked ahead of noisier raw surfaces when both exist

### 4. The architecture is materially stronger than it was at the start of the day

The memory system now has:

- typed conversational extraction
- typed temporal graph sidecar
- entity-linked conversational retrieval
- exact-turn retrieval lane
- typed answer projection
- shadow fused routing
- product-facing shadow replay bridge
- checked Telegram regression gate

That is a real substrate improvement, not only a benchmark patch.

## What We Improved Architecturally

The current architecture shape is now:

- `summary_synthesis_memory` remains the backbone
- raw episodes are preserved
- typed conversational memory exists as a sidecar structure
- graph/time/entity/exact-turn lanes exist in shadow/eval form
- product-facing shadow replay can now consume typed conversational evidence

The main additive structures now present are:

- `relationship_edge`
- `alias_binding`
- `loss_event`
- `gift_event`
- `support_event`
- `commitment_event`
- `negation_record`
- `reported_speech`
- `unknown_record`

The most important architectural lesson that is now implemented, not just written down, is:

- typed memory must survive into retrieval and answer surfaces

It is not enough to extract good structure if the retrieval surface later falls back to summary-only or noisy raw support spans.

## Benchmark State

### What is green right now

Focused LoCoMo guardrails:

- `4 passed, 274 deselected`

Sampled BEAM/provider surface checks:

- `2 passed, 185 deselected`

Sampled LongMemEval frontier checks:

- `3 passed, 275 deselected`

So the Telegram fixes did not obviously break the narrow benchmark/regression lanes that were checked today.

### What is still incomplete

The widened fused-family LoCoMo chunk program is still throughput-blocked on this machine.

Current live background session:

- `22149`

Intended chunk order:

- `conv-41/42/43`
- `conv-44/47`
- `conv-48/49/50`

Expected artifact names:

- `$SPARK_HOME\artifacts\locomo-unseen-slice\fused-heuristic-conv41-43-0521738.json`
- `$SPARK_HOME\artifacts\locomo-unseen-slice\fused-heuristic-conv44-47-0521738.json`
- `$SPARK_HOME\artifacts\locomo-unseen-slice\fused-heuristic-conv48-50-0521738.json`

At the stop point of this handoff:

- the chunk runner is alive
- it is still silent
- no chunk artifact has appeared yet

That looks like execution throughput saturation, not a newly found architecture regression.

## Honest Assessment

### What is truly better now

- the product-facing Telegram memory surface
- the bridge between conversational structure and replay retrieval
- the quality of answer surfaces on the checked conversational families
- confidence that the current architecture helps both benchmark-like and product-like memory

### What is still not proven enough

- wider fused-family LoCoMo answer quality on unseen slices
- real-provider chunked LoCoMo comparisons after the latest Telegram/product-facing changes
- full BEAM / LongMemEval regression closure after the latest additive layers
- runtime promotion safety

So the system is stronger, but the remaining promotion question is still benchmark throughput and wider evidence, not “invent another lane.”

## Remaining Gaps

The main gaps are now:

### 1. Wider benchmark evidence

The chunked heuristic fused-family LoCoMo scoreboard is now complete:

- `conv41-43`
  - `summary`: `14/148`
  - `exact-turn`: `21/148`
  - `entity`: `14/148`
  - `graph`: `13/148`
  - `fused`: `21/148`
- `conv44-47`
  - `summary`: `7/90`
  - `exact-turn`: `6/90`
  - `entity`: `7/90`
  - `graph`: `7/90`
  - `fused`: `6/90`
- `conv48-50`
  - `summary`: `29/162`
  - `exact-turn`: `34/162`
  - `entity`: `14/162`
  - `graph`: `28/162`
  - `fused`: `33/162`

Aggregate across the widened fused-family slice:

- `summary`: `50/400`
- `exact-turn`: `61/400`
- `entity`: `35/400`
- `graph`: `48/400`
- `fused`: `60/400`

Current interpretation:

- `exact-turn` is the best heuristic lane on this widened slice
- `fused` is close behind but not yet better overall
- `conv41-43` and `conv48-50` support the new direction
- `conv44-47` is the drag chunk and should be inspected before any runtime promotion

Specific `conv44-47` diagnosis:

- there is exactly one fused-vs-summary regression in this chunk
- `conv-47-qa-14` `When did James visit Italy?`
  - `summary`: `in 2021` and scored correct
  - `fused`: `2021` and scored false
  - selector: `exact_turn_first`
- this looks like a temporal answer-surface normalization issue, not a broader retrieval failure
- a narrow fix has now landed:
  - exact-turn shadow packets now promote evidence-derived answer candidates only for `when ...` questions
  - provider coverage now includes a locked regression test for preferring `in 2021` over bare `2021`
  - targeted tests passed:
    - `tests/test_conversational_index.py -k "exact_turn_hybrid_shadow_packets_add_conversational_evidence_for_exact_fact_question or exact_turn_hybrid_shadow_packets_promote_temporal_surface_for_conv47_trip_question"`
    - `tests/test_providers.py -k "prefers_in_year_candidate_over_bare_year_for_when_question or preserves_matching_temporal_answer_candidate_for_when_question"`
- the next targeted rerun should be `conv-47-qa-14`, then the `conv44-47` chunk

Artifacts now on disk:

- `$SPARK_HOME\artifacts\locomo-unseen-slice\fused-heuristic-conv41-43-0521738.json`
- `$SPARK_HOME\artifacts\locomo-unseen-slice\fused-heuristic-conv44-47-0521738.json`
- `$SPARK_HOME\artifacts\locomo-unseen-slice\fused-heuristic-conv48-50-0521738.json`

We still need:

- real-provider reruns on the chunks that matter
- broader BEAM / LongMemEval regression checks

### 2. Entity linking hardening

Still pending from `tasks.md`:

- stronger alias binding beyond the current cases
- kinship normalization across `mom` / `mother` / `her mother` / `my mom`
- longer-range person resolution across sessions

### 3. Temporal validity

Still pending:

- valid-from / valid-until style fact windows
- preserving superseded facts more explicitly
- stronger historical query handling over conversational time

### 4. Broader product-facing coverage

The checked Telegram pack is green, but the next step is to widen the pack, not assume the whole product surface is solved.

## Where We Should Head Next

The next direction should stay evidence-led:

1. finish the chunked heuristic fused-family LoCoMo scoreboard
2. rerun only the worthwhile chunks with a real provider
3. widen BEAM / LongMemEval regression checks after the chunk scoreboard is stable
4. only then decide whether any runtime routing should change

The next architecture work after that should be:

- entity linking hardening
- then temporal validity windows

Not:

- replacing `summary_synthesis_memory`
- adding benchmark-only heuristics
- inventing new retrieval lanes before the current fused lane is fully measured

## Recommended Restart Order For Tomorrow

1. Read the three completed chunk artifacts first.
2. Inspect `conv44-47` failure families before changing routing again.
3. Run the best chunk(s) with a real provider.
4. After that, rerun broader BEAM / LongMemEval regression lanes.
5. Only then decide whether fused routing deserves promotion or whether `exact-turn` should remain the main non-summary lane.

## Exact Commands To Resume With

Heuristic chunk pattern:

```powershell
python -m domain_chip_memory.cli run-locomo-multi-shadow-eval benchmark_data/official/LoCoMo/data/locomo10.json --provider heuristic_v1 --sample-id conv-41 --sample-id conv-42 --sample-id conv-43 --category 1 --category 2 --category 3 --exclude-missing-gold --fused-family-only --conversational-limit 4 --graph-limit 4 --write $SPARK_HOME\artifacts\locomo-unseen-slice\fused-heuristic-conv41-43-0521738.json
```

Real-provider rerun pattern:

```powershell
python -m domain_chip_memory.cli run-locomo-multi-shadow-eval benchmark_data/official/LoCoMo/data/locomo10.json --provider minimax:MiniMax-M2.7 --sample-id conv-41 --sample-id conv-42 --sample-id conv-43 --category 1 --category 2 --category 3 --exclude-missing-gold --fused-family-only --conversational-limit 4 --graph-limit 4 --write $SPARK_HOME\artifacts\locomo-unseen-slice\fused-minimax-conv41-43-0521738.json
```

Focused regression lanes already known-good today:

```powershell
python -m pytest tests/test_memory_systems.py -k "summary_synthesis_locomo_conv48_social_memory_questions_recover_exact_lists_and_anchors or conv42_temporal_anchor_questions_recover_older_event_grounding or conv49_typed_fact_and_count_questions_recover_exact_answers or unseen_conv47_recovers_exact_supportable_answers" -q

python -m pytest tests/test_providers.py -k "expand_answer_from_context_preserves_multiline_beam_event_ordering_surface or expand_answer_from_context_preserves_beam_temporal_surface_with_dates" -q

python -m pytest tests/test_memory_systems.py -k "longmemeval_preference_candidates_cover_151_175_single_session_lane or longmemeval_aggregate_candidates_cover_176_200_slice or longmemeval_summary_synthesis_candidates_cover_226_250_frontier_slice" -q
```

## Worktree Warning

The worktree is still dirty in unrelated ways.

Do not revert these unless explicitly intended:

- `src/domain_chip_memory/__init__.py`
- `src/domain_chip_memory/memory_dual_store_builder.py`
- many untracked benchmark artifacts under `artifacts/benchmark_runs/`

These were not part of today’s checkpoint line.

## Commits From Today That Matter

- `6b37592` `Bridge conversational evidence into spark shadow replay`
- `0521738` `Tighten Telegram shadow replay surfaces`

These are the two checkpoints that matter most for today’s product-facing progress.
