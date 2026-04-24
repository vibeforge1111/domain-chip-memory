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
- `spark-telegram-bot` invokes Builder through the `gateway simulate-telegram-update` CLI internally
- since the runtime-origin cleanup, real bot bridge calls should now appear as `request_id=telegram:*`, `simulation=false`, and `origin_surface=telegram_runtime`

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

## Continuation Update - 2026-04-24

The two coordinated memory/runtime branches were fast-forwarded into `main` and pushed:

- `domain-chip-memory` `main`: `e33a575 Harden kinship memory retrieval`
- `spark-intelligence-builder` `main`: `edb013b Route Telegram family memory through Builder`

The live Telegram long-polling bot was restarted and verified on `127.0.0.1:8788`. The active runtime process after the observability update was PID `8276`.

The observability cleanup was implemented in Builder and the Telegram bot bridge:

- Builder commit `6aab498 Label bridged Telegram traffic as runtime origin` was pushed to `spark-intelligence-builder/main`.
- `gateway simulate-telegram-update` now accepts `--origin simulation|telegram-runtime`.
- Runtime-origin bridge calls now emit `request_id=telegram:<update_id>`, `simulation=false`, and `origin_surface=telegram_runtime`.
- Default synthetic simulation calls still emit `request_id=sim:<update_id>`, `simulation=true`, and `origin_surface=simulation_cli`.
- `spark-telegram-bot` commit `3ef3b6b Mark Builder bridge calls as Telegram runtime` was created locally and the live bot was rebuilt/restarted from it.
- The bot commit was not pushed because `spark-telegram-bot/main` already had five older local commits ahead of `origin/main`; pushing would publish all six together.

Verification completed after the continuation:

```powershell
# spark-intelligence-builder
python -m pytest tests/test_observability_filters.py -q
# 5 passed, 2 warnings

python -m pytest tests/test_telegram_generic_memory.py -k "family_shared_time or generic_relationship_memory_before_provider_resolution or generic_plan_query" -q
# 4 passed, 70 deselected

# spark-telegram-bot
npm run build
# passed
```

Live runtime-origin probe result:

```text
Which family members did I spend time with recently?
-> You recently spent time with mother, sister.
```

Builder trace confirmed the latest runtime-origin probe used `request_id=telegram:*`, `simulation=false`, and `origin_surface=telegram_runtime`.

Next recommended step:

1. Decide whether to push `spark-telegram-bot/main` with all six local commits or split the observability bridge commit onto a clean branch.
2. If keeping momentum in memory quality, start the next benchmark-plus-live probe slice: preference memory, current plan memory, commitment memory, correction/supersession, and deletion/forgetting.

## Continuation Update - 2026-04-24 Later

Builder `main` was advanced and pushed through the next benchmark-plus-runtime slice:

- `8b5d10c Add Telegram plan memory regression probes`
- `4f34627 Add Telegram preference memory probes`
- `fc31b21 Cover favorite food Telegram memory phrase`
- `250e286 Route Telegram memory deletes before instruction shortcircuit`
- `d89e550 Cover active state Telegram memory deletes`

What changed in Builder:

- added direct tests for current-plan, commitment, correction/history, deletion, favorite-color, and favorite-food memory behavior
- added `preferences` generic memory packs for `profile.favorite_color` and `profile.favorite_food`
- added concise profile-fact answers for favorite color and favorite food
- added preference and current-plan lifecycle cases to the `telegram_generic_profile_lifecycle` benchmark pack
- fixed the Telegram gateway path so governed generic-memory deletes such as `Forget my favorite color.` and `Forget my current plan.` route to Builder memory before the older saved-instruction short-circuit
- added gateway-level coverage for active-state deletes before the saved-instruction short-circuit: current plan and current commitment

Verification completed:

```powershell
# spark-intelligence-builder
python -m pytest tests/test_gateway_ask_telegram.py -q
# 8 passed, 9 warnings, 2 subtests passed

python -m pytest tests/test_telegram_generic_memory.py -k "family_shared_time or plan_and_commitment_queries or plan_correction_history_and_deletion or preference_update_query_and_deletion or favorite_food_preference_phrase" -q
# 6 passed, 72 deselected

python -m pytest tests/test_memory_regression.py -q
# 8 passed

python -m spark_intelligence.cli memory run-telegram-regression --benchmark-pack telegram_generic_profile_lifecycle --case-id favorite_color_write --case-id favorite_color_query --case-id favorite_color_delete --case-id favorite_color_query_after_delete --case-id favorite_food_write --case-id favorite_food_query --case-id favorite_food_delete --case-id generic_plan_write --case-id generic_plan_overwrite --case-id generic_plan_current_query_after_overwrite --case-id generic_plan_history_query_after_overwrite --case-id generic_plan_delete --case-id generic_plan_current_query_after_delete
# focused temp-home run: 13 matched, 0 mismatched

python -m spark_intelligence.cli memory run-telegram-regression --benchmark-pack telegram_generic_profile_lifecycle --case-id generic_commitment_write --case-id generic_commitment_overwrite --case-id generic_commitment_current_query_after_overwrite --case-id generic_commitment_history_query_after_overwrite --case-id generic_commitment_delete --case-id generic_commitment_current_query_after_delete --case-id generic_commitment_history_query_after_delete --case-id generic_commitment_event_history_query_after_delete
# focused temp-home run: 8 matched, 0 mismatched
```

Runtime status observed after the push:

- Builder `main` was clean and aligned with `origin/main`, aside from existing untracked local noise.
- `domain-chip-memory/main` was aligned with `origin/main`, aside from existing untracked artifact noise.
- `spark-telegram-bot` remained on `codex/telegram-runtime-origin-2026-04-24`, aligned with its remote branch, with only untracked `PROJECT.md`.
- Long-polling bot process was still listening on `127.0.0.1:8788` as PID `8276` (`node dist/index.js`).
- Real Telegram favorite-color write was confirmed through long polling:
  - route: `memory_generic_observation_update`
  - predicate: `profile.favorite_color`
  - runtime labels: `request_id=telegram:*`, `simulation=false`, `origin_surface=telegram_runtime`
  - bot reply: `I'll remember that your favorite color is bright green.`
- Local recall against the same live Builder home returned: `Your favorite color is bright green.`

Next recommended step:

1. Ask the user to send the live Telegram probes for favorite food, current plan overwrite/history, commitment overwrite/history, and deletion now that the gateway delete ordering bug is fixed.
2. If live probes pass, update this handoff with the real Telegram replies.
3. Then move to commitment/correction/deletion coverage in the benchmark pack, or push the clean `spark-telegram-bot` runtime-origin branch as a PR if the GitHub app/remote path is available.
