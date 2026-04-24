# Memory Systems Handoff - 2026-04-13

This is the restart document for tomorrow's work on the Spark memory system.
It is intentionally cross-repo because today's work spanned:

- `<workspace>\\domain-chip-memory`
- `<workspace>\\spark-agent-harness`
- `<workspace>\\spark-tui-lab`

The goal is that tomorrow can start from this file alone without needing to
reconstruct the memory story from chat history.

---

## 1. Executive Summary

The governed memory system is now real end to end for read paths and explicit
runtime writes:

- `domain-chip-memory` has a governed release pipeline, gate artifacts, summary
  artifacts, direct read helpers, and release-manifest surfaces.
- `spark-agent-harness` exposes that system honestly as a memory bridge:
  status, governed reads, conversation reads, explicit save writes, runtime
  confirmation, and task-event telemetry.
- `spark-tui-lab` shows `domain-chip-memory` as connected, supports inline
  `/memory` read and save commands, renders memory telemetry in the same
  terminal flow, intercepts narrow natural-language save intents, and no longer
  pollutes the transcript with redundant wrapper lines.

The most important remaining product gap is still:

- explicit saves are `runtime_only`
- governed release reads do not see those saves yet
- normal governed task prefetch therefore does not benefit from explicit saves

That is the highest-value continuation item for tomorrow.

---

## 2. Repo State At Stop

### domain-chip-memory

Path:

- `<workspace>\\domain-chip-memory`

Current HEAD:

- `a2ddb80`

Relevant docs already in repo:

- [NEXT_PHASE_SPARK_MEMORY_KB_BENCHMARK_PROGRAM_2026-04-10.md](<domain-chip-memory>/docs/NEXT_PHASE_SPARK_MEMORY_KB_BENCHMARK_PROGRAM_2026-04-10.md)
- [SPARK_GOVERNED_RELEASE_EXTRA_WORK_2026-04-12.md](<domain-chip-memory>/docs/SPARK_GOVERNED_RELEASE_EXTRA_WORK_2026-04-12.md)

Important note:

- this repo is not clean right now
- current local status includes modified tracked files:
  - `src/domain_chip_memory/__init__.py`
  - `src/domain_chip_memory/memory_dual_store_builder.py`
  - `src/domain_chip_memory/spark_kb.py`
  - `tests/test_sdk.py`
- there are also many untracked benchmark-run JSON files under
  `artifacts/benchmark_runs`
- none of those were created by the final handoff-writing step

### spark-agent-harness

Path:

- `<workspace>\\spark-agent-harness`

Current HEAD:

- `985cc49`

Branch state:

- `master`
- ahead of `origin/master` by `26`

Latest memory-specific commits in this repo:

- `026d583` `Document runtime confirmation in save response`
- `7e16d54` `Confirm runtime memory state after explicit saves`
- `2f28dab` `Document explicit memory bridge save route`
- `e0c2428` `Add explicit memory bridge save endpoint`
- `379e951` `Tag governed memory lookup start events`
- `d8d7f41` `Emit governed memory miss events`
- `07b799b` `Tag goal memory telemetry with chip source`
- `2ceae1b` `Expose chip source in memory task events`
- `466a04f` `Expand governed memory phrase coverage`
- `6760362` `Prefetch governed memory for live tasks`
- `8382be8` `Document memory telemetry contract`
- `7c68bab` `Verify memory telemetry in task event API`
- `752ba4e` `Quiet automatic goal memory writes`
- `437d4f3` `Stream goal memory telemetry through harness`
- `4297181` `Emit goal memory progress telemetry`
- `77108eb` `Read governed domain chip memory from harness`
- `eab6c22` `Document domain chip memory bridge`
- `dd9b551` `Expose domain chip memory bridge status`

### spark-tui-lab

Path:

- `<workspace>\\spark-tui-lab`

Current HEAD:

- `55fdc01`

Branch state:

- `master`
- ahead of `origin/master` by `8`

Important memory/UI commits from today's lane:

- `d4f8f7c` `Restore live terminal status indicator`
- `3711240` `Trim redundant terminal task chrome`
- `e6f7f96` `Intercept natural-language terminal memory saves`
- `48751b6` `Call out missing runtime save confirmation`
- `5e29d7c` `Show runtime confirmation for memory saves`
- `7278b3e` `Add explicit memory save provenance metadata`
- `4b0d5bf` `Add terminal explicit memory save command`
- `a23e344` `Differentiate terminal memory lookup states`
- `f98b7c6` `Show memory chip source in terminal`
- `444358a` `Show retrieved memory values in terminal`
- `2f4b63b` `Send terminal memory identity to harness`
- `5b0756b` `Expose memory commands in TUI help`
- `ab41410` `Stream memory bridge telemetry in terminal`
- `ba0a86a` `Expose governed memory bridge reads in TUI client`
- `bfa1d27` `Document domain chip memory TUI integration`
- `e508982` `Show domain chip memory connection in chips panel`

Important note:

- the visible TUI behavior the user approved today corresponds to the memory
  commits above, even though newer unrelated TUI commits exist on top

---

## 3. What Was Completed Well

### 3.1 domain-chip-memory: governed release system

This part is genuinely complete enough for downstream consumers:

- governed replay slice creation exists
- approved promotion slice exists
- policy verdict and promotion plan exist
- governed release can be:
  - materialized
  - published
  - resolved
  - read directly
  - summarized
  - gated
  - asserted ready
- the publish root includes stable top-level artifacts such as:
  - `governed-release.json`
  - `governed-release-summary.json`
  - `governed-release-gate.json`

This means the memory KB is not just benchmark plumbing anymore. It has a real
release contract.

### 3.2 spark-agent-harness: honest bridge over governed memory

The harness now exposes the memory layer as an actual system surface rather than
an implicit local convention.

Implemented bridge capabilities:

- `GET /v1/memory/bridge`
- `GET /v1/memory/bridge/support`
- `GET /v1/memory/bridge/conversations/{conversation_id}/support`
- `POST /v1/memory/bridge/observations`

Behavior that is genuinely good:

- governed bridge status reports whether `domain-chip-memory` is connected
- subject-level governed reads work
- conversation-level governed reads work
- explicit saves work through the bridge
- explicit saves include runtime confirmation fields after write
- memory-related progress events carry structured fields instead of collapsing
  into generic text
- normal goal/task flows can emit inline memory telemetry

### 3.3 spark-tui-lab: same-terminal memory UX

This is the user-facing part that landed well.

The TUI now supports:

- `/memory subject <subject> <predicate>`
- `/memory conversation <conversation_id> <predicate>`
- `/memory save <predicate> <value...>`

It also renders memory behavior inline in the same terminal transcript:

- `checking memory`
- `memory retrieved`
- `no governed memory found`
- `memory updated`
- `memory saved`
- `runtime confirmed`
- `runtime confirmation unavailable`

Other good UX outcomes:

- `domain-chip-memory` shows as connected in the Chips panel
- chip source is visible inline in memory telemetry
- retrieved values are shown inline
- natural-language explicit save intent is intercepted for narrow cases like:
  - `remember that my timezone is Asia/Dubai`
  - `save that i am from the UAE`
  - `remember that North Korea hacked me`
- vague prompts like `i want to see if you can save memories` no longer fall
  through to Codex file-save behavior

Transcript cleanup that the user explicitly wanted is also done:

- keep the live animation/timer above the chat
- remove permanent transcript noise:
  - `> spark is working`
  - `x spark-codex finished and returned a reply`
  - `------ spark reply ------`

---

## 4. What Was Tested

### 4.1 Automated tests run successfully

#### spark-agent-harness

Command run:

```powershell
python -m pytest tests/test_observability_and_api.py tests/goals/test_chip_memory_context.py tests/goals/test_harness_http_submitter.py tests/test_integration_wiring.py -q
```

Result:

- `138 passed`

This covered:

- bridge status and read routes
- explicit save route
- runtime confirmation behavior
- goal memory telemetry
- task-event propagation
- integration wiring

#### spark-tui-lab

Command run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_terminal_memory_save.py tests/test_terminal_memory_telemetry.py tests/test_harness_api.py -q
```

Result:

- `104 passed`

Additional focused regression run after transcript cleanup:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_first_60_seconds.py tests/test_harness_api.py -q
```

Result:

- `102 passed`

This covered:

- terminal memory save formatting
- terminal memory telemetry formatting
- harness client memory methods
- transcript cleanup expectations
- live indicator expectations

### 4.2 Live bridge checks

#### Important operational note

The harness already bound to `8011` was stale relative to current code for at
least one route:

- reads worked
- `POST /v1/memory/bridge/observations` returned `404`

To verify the current implementation honestly, a fresh harness was started on:

- `http://127.0.0.1:8013`

#### Live results on fresh `8013`

Governed hit:

- subject:
  `human:telegram:spark-memory-regression-user-2c339238-hack_actor_query_missing`
- predicate: `profile.hack_actor`
- result:
  - `found: true`
  - `value: North Korea`
  - `supporting_evidence_count: 1`

Governed miss:

- conversation:
  `session:telegram:dm:spark-memory-soak-user-ed0c3cbc-boundary_abstention-0005-timezone_query_missing_cleanroom`
- predicate: `profile.timezone`
- result:
  - `found: false`
  - `supporting_evidence_count: 0`

Explicit save:

- subject: `human:terminal-live-save-check-2`
- predicate: `profile.timezone`
- value: `Asia/Dubai`
- result:
  - `accepted: true`
  - `runtime_only: true`
  - `governed_release_updated: false`
  - `runtime_lookup_found: true`
  - `runtime_lookup_value: Asia/Dubai`
  - `runtime_memory_role: current_state`
  - `runtime_provenance_count: 1`

### 4.3 Live product gap confirmed

After the explicit save above, governed readback on the bridge still returned:

- `found: false`
- `value: null`

That proves the remaining boundary clearly:

- explicit saves update runtime state
- explicit saves do not update the governed release
- normal governed retrieval does not see those runtime-only writes

This is not ambiguous anymore. It is the main next task.

---

## 5. What Is Actually Done vs. What Is Not

### Done enough to trust

- governed memory release contract in `domain-chip-memory`
- governed bridge status/read/save contract in `spark-agent-harness`
- inline terminal memory UX in `spark-tui-lab`
- chips panel integration showing `domain-chip-memory` connection honestly
- natural-language explicit save interception for narrow patterns
- explicit save runtime confirmation in the terminal
- transcript cleanup requested by the user

### Not done

- runtime explicit saves do not promote into governed retrieval
- normal governed task prefetch cannot benefit from those saves
- stale harness detection/startup hygiene is not solved; `8011` can easily be
  an older process than the code on disk
- natural-language save interception is still narrow and heuristic
- `domain-chip-memory` repo cleanup is partial; many benchmark-run JSONs remain
  locally under `artifacts/benchmark_runs`

### Things explicitly not touched today

- `$SPARK_HOME\state.db`
- `$SPARK_HOME` live config/state beyond safe cache/log cleanup discussion
- any `spark-intelligence*` Desktop repo deletion

---

## 6. Cleanup Work Completed Today

### Safe benchmark/cache cleanup in domain-chip-memory

Removed:

- `benchmark_data/official`
- `tmp`
- `artifacts/tmp`
- `.pytest_cache`

Approximate reclaimed space:

- `5.59 GB`

### Desktop repo cleanup

Deleted Desktop directories:

- `<workspace>\\mind`
- `<workspace>\\the-mind`
- `<workspace>\\vibeship-mind`
- `<workspace>\\vibeship-mind-terrarium`

Approximate reclaimed space:

- `265 MB`

Important note:

- only those four mind-family directories were removed
- no `spark-intelligence*` repo was deleted
- no live Spark state folder was deleted

---

## 7. Tomorrow's Recommended Plan

This is the recommended execution order for tomorrow.

### Priority 0 - fix the explicit-save retrieval gap

Goal:

- make normal memory retrieval capable of seeing explicit runtime saves, or
- make the separation explicit enough that product behavior is honest and
  predictable

Recommended approach:

1. decide whether explicit saves should:
   - stay runtime-only forever, or
   - feed a governed refresh path
2. if they should feed retrieval soon, add a bridge read path that can consult:
   - governed release first
   - runtime explicit-save layer second
3. if they should not feed retrieval, update task behavior and UI wording so the
   operator understands that explicit saves are not yet part of governed recall

This is the most important product decision remaining.

### Priority 1 - eliminate stale-server ambiguity

Observed problem:

- `8011` was stale enough that the save route was missing even though the code
  on disk had it

Tomorrow should add one of:

- server build/version marker in `/health`
- launcher logic that kills/replaces stale processes
- harness/TUI mismatch warning if the expected route set is absent

### Priority 2 - broaden natural-language save interception

Current coverage is narrow and good enough for demos but not robust enough for
general use.

Good next expansions:

- `remember my timezone is ...`
- `save that I live in ...`
- `remember I am from ...`
- `save who hacked me as ...`
- maybe explicit prompts like `save this as memory: ...`

Keep it narrow enough that ordinary user messages do not get hijacked by
accident.

### Priority 3 - make runtime-save history auditable

Potential follow-on:

- lightweight recent explicit-save history in the harness bridge or terminal
- useful for operator trust and debugging

### Priority 4 - decide how much further cleanup to do

Still large on disk:

- `<codex-home>\\worktrees` about `7.5 GB`
- `<codex-home>\\sessions` about `2.67 GB`
- `<codex-home>\\log` about `0.81 GB`
- `$SPARK_HOME\artifacts` about `0.67 GB`

Do not clean those blindly. Treat them as a separate cleanup session.

---

## 8. Concrete Restart Commands

### Fresh harness on a clean port

```powershell
Set-Location '<workspace>\\spark-agent-harness'
python scripts/serve.py --port 8013
```

### TUI against that fresh harness

```powershell
$env:SPARK_HARNESS_URL='http://127.0.0.1:8013'
$env:PYTHONIOENCODING='utf-8'
Set-Location '<workspace>\\spark-tui-lab'
.\.venv\Scripts\python.exe -m spark_tui.cli dashboard
```

### Good live prompts for immediate re-check

```text
remember that my timezone is Asia/Dubai
what is my timezone?
who hacked me?
i want to see if you can save memories
```

### Good direct bridge probes

```powershell
Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8013/v1/memory/bridge"
Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8013/v1/memory/bridge/support?subject=human%3Atelegram%3Aspark-memory-regression-user-2c339238-hack_actor_query_missing&predicate=profile.hack_actor"
```

---

## 9. Tomorrow's Definition Of Done

Tomorrow counts as a strong follow-through if all of this becomes true:

1. explicit save behavior is no longer ambiguous
2. normal retrieval after explicit save works in the intended way
3. fresh/stale harness mismatch is easy to detect
4. at least one live TUI session proves the intended memory story end to end
5. the restart path no longer depends on remembering that `8011` might be stale

---

## 10. Final Recommendation

Do not restart tomorrow by adding more benchmark plumbing.

Restart from the real user-facing gap:

- explicit saves work
- runtime confirmation works
- governed reads work
- but the two systems are still separated

That is the seam to close next.
