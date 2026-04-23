# Session Handoff 2026-04-24

Use this as the first read for the next memory/Telegram continuation, especially on 2026-04-25.

## Current Truth

The Telegram bot memory loop is now confirmed end-to-end with the real long-polling bot path.

Confirmed path:

```text
Telegram long polling -> spark-telegram-bot -> Builder bridge -> domain_chip_memory -> Telegram reply
```

Live user-facing proof:

- user sent the family/shared-time probe to `@SparkAGI_bot` from Telegram
- bot replied: `You recently spent time with mother, sister.`
- Builder state showed the write/read routed through memory:
  - write route: `memory_generic_observation`
  - read route: `memory_profile_fact_query`
  - predicate: `profile.recent_family_members`
  - stored value: `mother, sister`

Important nuance:

- webhook is not used
- current receiver is long polling
- `localhost:8080` is legacy fallback/no-listener noise for this session
- the real memory path is the Builder bridge on the running Telegram bot process
- `spark-telegram-bot` invokes Builder through the `gateway simulate-telegram-update` CLI internally, so Builder request IDs may appear as `sim:*` even for real Telegram bridge calls

## Repos Involved

Primary repo:

- `C:\Users\USER\Desktop\domain-chip-memory`

Runtime/Telegram adapter repo:

- `C:\Users\USER\Desktop\spark-intelligence-builder`

Telegram ingress owner:

- `C:\Users\USER\Desktop\spark-telegram-bot`

Do not start a second Telegram receiver unless intentionally replacing the current one.

## Domain-Chip-Memory Changes

Branch to continue from:

- `feature/domain-chip-family-visit-memory`

Tracked files modified:

- `docs/SESSION_HANDOFF_2026-04-23.md`
- `docs/SESSION_HANDOFF_2026-04-24.md`
- `src/domain_chip_memory/memory_conversational_index.py`
- `src/domain_chip_memory/memory_conversational_retrieval.py`
- `src/domain_chip_memory/memory_conversational_shadow_eval.py`
- `tests/test_conversational_index.py`

What changed:

- candidate-answer guard prevents non-temporal relationship/support spans from overriding explicit temporal answers for `when ...` questions
- kinship aliases normalize `mom` / `mum` / `mother` and `dad` / `father`
- family visit/shared-time extraction handles `came over`, `dropped by`, `visited`, `spent time with`, and `hung out`
- family-member aggregation supports questions like `Which family members did I spend time with recently?`
- handoff docs now record that live Telegram memory is confirmed through long polling and Builder bridge, not `8080`

Key evidence already collected:

- reconstructed `conv44+47` heuristic slice: summary `7/90`, exact-turn `9/90`, entity `9/90`, graph `8/90`, fused `11/90`, fused regressions vs summary `0`, fused improvements vs summary `4`
- sensitive heuristic 6-probe after kinship hardening: summary `2/6`, exact-turn `4/6`, entity `5/6`, graph `4/6`, fused `6/6`
- sensitive MiniMax 6-probe after kinship hardening: summary `2/6`, exact-turn `3/6`, entity `5/6`, graph `4/6`, fused `6/6`
- Telegram shadow report after kinship hardening: accepted `14`, rejected `0`, skipped `2`, evidence `12/12`, current state `1/1`, historical state `1/1`

Artifacts:

- `artifacts/telegram_multi_party_probe_report_after_candidate_guard.json`
- `artifacts/telegram_multi_party_probe_report_after_kinship_hardening.json`
- `C:\Users\USER\.spark-intelligence\artifacts\locomo-unseen-slice\fused-heuristic-sensitive-6probe-after-kinship-hardening.json`
- `C:\Users\USER\.spark-intelligence\artifacts\locomo-unseen-slice\fused-minimax-sensitive-6probe-after-kinship-hardening.json`

## Builder Changes

Tracked files modified in `C:\Users\USER\Desktop\spark-intelligence-builder`:

- `src/spark_intelligence/memory/generic_observations.py`
- `src/spark_intelligence/memory/profile_facts.py`
- `tests/test_telegram_generic_memory.py`

What changed:

- Builder generic Telegram memory now classifies family/shared-time messages into `profile.recent_family_members`
- `mom`, `mum`, and `mother` canonicalize to `mother`; `dad` and `father` canonicalize to `father`
- query detection answers `Which family members did I spend time with recently?` from memory, not provider fallback
- tests assert provider resolution/execution does not run for this write/read path

Live Builder memory status:

```text
configured_module = domain_chip_memory
ready = true
client_kind = _DomainChipMemoryClientAdapter
runtime_class = SparkMemorySDK
runtime_memory_architecture = summary_synthesis_memory
runtime_memory_provider = heuristic_v1
```

Gateway status caveat:

- `gateway status` reports `ready=false` because the broader doctor is not fully clean
- provider runtime/execution are OK
- Telegram adapter auth is OK
- the memory bridge path is confirmed working despite the broader doctor flag

## Telegram Runtime Facts

Observed current process:

```text
127.0.0.1:8788 LISTEN
process: node dist/index.js
repo: spark-telegram-bot
mode: polling
```

Bot API check:

```text
getMe_ok = true
bot_username = SparkAGI_bot
webhook_url_set = false
pending_update_count = 0
```

Real-user confirmation:

```text
User sent the live probe in Telegram.
Bot answered: You recently spent time with mother, sister.
```

## Verification Already Passed

Domain-chip-memory:

```powershell
python -m pytest tests/test_conversational_index.py -k "kinship_aliases or mom_question or family_shared_time or family_visit_members_for_conv47 or extracts_family_visit_events_for_conv47 or retrieve_conversational_entries_finds_full_family_hobby_turns_for_conv48" -q
python -m pytest tests/test_conversational_index.py -k "exact_turn_hybrid_shadow_packets_add_conversational_evidence_for_exact_fact_question or exact_turn_hybrid_shadow_packets_promote_temporal_surface_for_conv47_trip_question or do_not_promote_non_temporal_support_span_for_when_question or fused_conversational_hybrid_shadow_packets or entity_linked_hybrid_shadow_packets" -q
python -m pytest tests/test_typed_temporal_graph_memory.py tests/test_typed_temporal_graph_retrieval.py -q
python -m pytest tests/test_memory_systems.py -k "summary_synthesis_locomo_conv48_social_memory_questions_recover_exact_lists_and_anchors or conv42_temporal_anchor_questions_recover_older_event_grounding or conv49_typed_fact_and_count_questions_recover_exact_answers or unseen_conv47_recovers_exact_supportable_answers" -q
python -m pytest tests/test_providers.py -k "prefers_in_year_candidate_over_bare_year_for_when_question or preserves_matching_temporal_answer_candidate_for_when_question or expand_answer_from_context_preserves_multiline_beam_event_ordering_surface or expand_answer_from_context_preserves_beam_temporal_surface_with_dates" -q
python -m pytest tests/test_memory_systems.py -k "longmemeval_preference_candidates_cover_151_175_single_session_lane or longmemeval_aggregate_candidates_cover_176_200_slice or longmemeval_summary_synthesis_candidates_cover_226_250_frontier_slice" -q
python -m domain_chip_memory.cli validate-spark-shadow-replay docs/examples/spark_shadow/telegram_multi_party_probe_pack.json
python -m domain_chip_memory.cli run-spark-shadow-report docs/examples/spark_shadow/telegram_multi_party_probe_pack.json --write artifacts\telegram_multi_party_probe_report_after_kinship_hardening.json
git diff --check
```

Spark-intelligence-builder:

```powershell
python -m pytest tests/test_telegram_generic_memory.py -k "family_shared_time or generic_relationship_memory_before_provider_resolution or generic_plan_query" -q
python -m pytest tests/test_memory_orchestrator.py -k "profile_fact" -q
git diff --check
```

Live Telegram/Builder checks:

```powershell
python -m spark_intelligence.cli memory status --home .tmp-home-live-telegram-real --json
python -m spark_intelligence.cli gateway status --home .tmp-home-live-telegram-real --json
```

The live real-chat proof was done manually from Telegram and corroborated in Builder state.

## Worktree Cautions

Both repos contain unrelated untracked artifacts/noise. Do not broad-clean or broad-stage.

In `domain-chip-memory`, there are many untracked benchmark artifacts under `artifacts/benchmark_runs/` plus live audit artifact folders. Treat them as existing workspace noise unless the user explicitly asks to package artifacts.

In `spark-intelligence-builder`, there are unrelated untracked files/folders including `.tmp/`, `.vendor/`, logs, docs, and local state files. Do not remove them while landing the memory patch.

Line-ending warnings from `git diff --check` are normal CRLF notices on this Windows checkout; no whitespace errors were reported.

## Tomorrow's Recommended Plan

1. Re-read this file first, then skim `docs/SESSION_HANDOFF_2026-04-23.md` only if extra historical detail is needed.
2. Confirm current runtime quickly:
   ```powershell
   Get-NetTCPConnection -State Listen -LocalPort 8788,8080 -ErrorAction SilentlyContinue
   python -m spark_intelligence.cli memory status --home .tmp-home-live-telegram-real --json
   ```
3. Run one tiny real Telegram sanity probe only if the bot/runtime changed overnight.
4. Review the two patch sets separately:
   - `domain-chip-memory`: benchmark/substrate kinship and temporal-answer hardening
   - `spark-intelligence-builder`: live Telegram routing/profile-fact memory bridge
5. Decide whether to land as two coordinated commits/PRs or keep the Builder patch as a companion runtime patch.
6. Add observability cleanup if time allows:
   - make real Telegram bridge calls less confusing than `sim:*`
   - log bridge mode/routing decision in a concise, redacted runtime event
7. After landing, move to the next architecture slice: temporal validity windows for superseded facts.

## Best Next Live Probes

Use these from Telegram after any restart:

```text
Please remember this live Telegram test: my mom came over and I spent time with my sister.
```

```text
Which family members did I spend time with recently?
```

Expected answer:

```text
You recently spent time with mother, sister.
```

Then expand to:

- preference memory
- current plan memory
- commitment memory
- correction/supersession memory
- deletion/forgetting behavior
