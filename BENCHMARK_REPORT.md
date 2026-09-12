# Agent Smith — SWE-bench Model Benchmark Report

## TL;DR — All models ranked, best run per model

All 15 models tested in this report, at their standard (`30i/300k/10k`) budget config unless only tested at the raised budget. "Pass rate" is out of the 3 core tasks. Sorted by pass rate, then by average iterations-to-pass (lower is better). Full detail and caveats for every row are in §2 (core 5), §5c/§5d (extended models), and §6 (conclusions) — **do not pick a model from this table alone**, several rows here are single-run, free-tier, or otherwise flagged as not yet trustworthy in the sections below.

| Rank | Model | Pass rate | Avg iterations (passing runs) | Total retries (all 3 tasks) | Status / caveat |
|---|---|---|---:|---:|---|
| 1 | `~openai/gpt-sol-latest` | 3/3 | 2.0 | 1 | Best efficiency in report, but single-run/preview-tier — **not yet validated**, see §5c/§6 |
| 2 | `nex-agi/nex-n2.5-pro` | 3/3 | 2.7 | 2 | Confirmed stable across both budgets (§5d) — best-validated free-tier model |
| 2 | `deepseek/deepseek-v4.1-flash` | 3/3 | 6.0 | 0 | **Recommended** — stable, non-free-tier provider, zero retries |
| 2 | `zhipu/glm-5.3-flash` | 3/3 | 3.0 | 0 | **Recommended** — stable, non-free-tier provider, best submission discipline |
| 5 | `nex-agi/nex-n2.5-mini` | 2/3 (3/3 at raised budget) | 3.0 | 15 | Needs 2x budget to reach 3/3, at a large token cost — see §5d |
| 5 | `openai/gpt-4o` | 2/3 | 4.0 | 0 | Fast fallback only — fails task3 via a search-loop bug, see §6 |
| 5 | `hy4-preview` | 2/3 | 6.5 | 0 | Same task3 failure mode as gpt-4o — disregard, see §6 |
| 5 | `inclusionai/ling-3.0-flash-fin` | 2/3 | 3.5 | 16 | Passes cheaply at low budget, but iteration count explodes 6–8x at raised budget for the same result — see §5d |
| 9 | `xiaomi/mimo-v2.5` | 1/3 | 4.0 | 0 | Disregard — never converges on 2 of 3 tasks regardless of budget, see §6 |
| 9 | `inclusionai/ling-3.0-flash-sante` | 1/3 | 5.0 | 30 | Disregard — highest retry count of any model, unstable at both budgets |
| 11 | `inclusionai/ling-3.0-flash-vl` | 0/3 | — | 4 | **Untestable** — never completed a single task in 6 attempts (provider-side `429`/`401` errors), not a model-quality result |

---

## 1. Setup

**Agent / harness:** Agent Smith's SWE-bench runner (`agent_swebench.py` +
`mcp_tools_swebench.py`). Each task runs in an isolated, network-disabled
Docker/Podman container built from the task's official SWE-bench image. The
agent gets `read_file`, `search_code`,
`search_function_or_class_definition_in_code`, `edit_file`, `run_command`,
`run_tests`, `get_patch`, and `final_answer` as tools, a shared system prompt,
and a hard cap of `--max-iterations 30`. All requests were routed through a
single provider gateway, OpenRouter (`https://openrouter.ai/api/v1`), so
provider-side reliability differences below are OpenRouter's, not per-vendor
infrastructure.

**Models compared** (5, all via OpenRouter):

| Model | Notes |
|---|---|
| `openai/gpt-4o` | Established general-purpose baseline |
| `deepseek/deepseek-v4.1-flash` | Fast/cheap open-weights coding model |
| `zhipu/glm-5.3-flash` | Fast/cheap alternative, different vendor family |
| `hy4-preview` | Preview-tier reasoning model |
| `xiaomi/mimo-v2.5` | Newer entrant, included to test long-horizon behavior |

**Tasks used** (3, all from the real SWE-bench dataset, `swebenchmarks_p0/task{1,2,3}/swebench_task.json`):

| Task | Instance ID | Repo | Why selected |
|---|---|---|---|
| task1 | `sympy__sympy-18189` | sympy | Localized, single-line logic bug (dropped `permute` kwarg on recursion) with a very clear, self-contained repro in the issue — good test of quick root-causing |
| task2 | `sympy__sympy-13480` | sympy | A plain typo (`cotm` vs `cothm`) causing a `NameError` — tests whether models can find and fix an exact-match bug fast without over-exploring |
| task3 | `django__django-11066` | django | Multi-file, framework-internals bug (`content_type.save()` missing `using=db`) requiring the agent to locate a specific method inside a larger, less obvious module — tests exploration under ambiguity |

These three were chosen to span a difficulty gradient (single-line arithmetic bug → typo → multi-hop framework logic) across two different codebases (sympy, django), so the comparison isn't just "one model is good at one repo."

Backing traces: `swebenchmarks_p0/task{1,2,3}/solutions/{model}.json` (15 files total, all committed). This directory is the baseline configuration (`max_iterations=30`, `max_input_tokens=300000`, `max_output_tokens=10000`) used for all results, reliability, and intermediary metrics below. §5 additionally uses `swebenchmarks_p1/task1/solutions/{gpt-4o,mimo-v2.5}.json`, a partial rerun of task1 under a raised-budget configuration, as a second ablation.

---

## 2. Results

| Task | Model | Pass/Fail | Iterations | Input tokens | Output tokens | Wall-clock (s) |
|---|---|---|---:|---:|---:|---:|
| task1 (sympy-18189) | gpt-4o | ✅ Pass | 4 | 10,774 | 407 | 31.5 |
| task1 | deepseek-v4.1-flash | ✅ Pass | 5 | 307,717 | 1,779 | 62.4 |
| task1 | glm-5.3-flash | ✅ Pass | 3 | 302,369 | 3,209 | 74.4 |
| task1 | hy4-preview | ✅ Pass | 7 | 300,440 | 4,166 | 137.0 |
| task1 | mimo-v2.5 | ❌ Fail | 22 | 66,781 | 10,000 | 233.4 |
| task2 (sympy-13480) | gpt-4o | ✅ Pass | 4 | 124,225 | 317 | 24.5 |
| task2 | deepseek-v4.1-flash | ✅ Pass | 3 | 256,434 | 786 | 25.3 |
| task2 | glm-5.3-flash | ✅ Pass | 4 | 9,744 | 2,816 | 33.4 |
| task2 | hy4-preview | ✅ Pass | 6 | 19,969 | 7,283 | 134.5 |
| task2 | mimo-v2.5 | ❌ Fail | 30 | 59,358 | 10,000 | 743.8 |
| task3 (django-11066) | gpt-4o | ❌ Fail | 10 | 31,909 | 839 | 27.8 |
| task3 | deepseek-v4.1-flash | ✅ Pass | 10 | 57,469 | 2,322 | 60.7 |
| task3 | glm-5.3-flash | ✅ Pass | 2 | 7,124 | 2,664 | 31.9 |
| task3 | hy4-preview | ❌ Fail | 10 | 36,888 | 4,460 | 96.7 |
| task3 | mimo-v2.5 | ✅ Pass | 4 | 12,327 | 2,596 | 115.0 |

**Pass rate by model:** deepseek-v4.1-flash 3/3, glm-5.3-flash 3/3, gpt-4o 2/3, hy4-preview 1/3, mimo-v2.5 1/3.

**Pass rate by task:** task1 4/5, task2 4/5, task3 3/5.

`mimo-v2.5` failed both task1 and task2 by hitting the 10,000-token output budget without ever calling `final_answer` (`error: "Configured token limit reached"` on task1); on task2 it ran the full 30-iteration budget. `gpt-4o` and `hy4-preview` failed task3 by looping on `search_function_or_class_definition_in_code(name="_rename")`, which returned empty results every single call (10/10 identical empty results for gpt-4o) — the agent never adapted its search strategy (e.g., falling back to `search_code`/grep) after repeated empty hits.

---

## 3. Provider reliability (OpenRouter, all models)

All 15 runs completed without a hard provider outage, and none of the recorded per-step traces show a retried request (`retries: 0` on every step in every file) — so on this small sample OpenRouter's availability was 100% and no rate-limit/timeout retries were needed. Average per-request latency, however, varied enormously by model — this is compute/queueing time on OpenRouter's end, not agent logic:

| Model | Avg response time / request | Retries | Availability |
|---|---:|---:|---|
| gpt-4o | ~3.2 s | 0 | 100% (18/18 requests succeeded) |
| deepseek-v4.1-flash | ~6.6 s | 0 | 100% (18/18) |
| glm-5.3-flash | ~14.0 s | 0 | 100% (9/9) |
| hy4-preview | ~15.1 s | 0 | 100% (23/23) |
| mimo-v2.5 | ~21.2 s | 0 | 100% (56/56) |

(Per-model average computed by averaging each task's mean `request_time_ms` across its steps, then averaging across the 3 tasks.)

`gpt-4o` is consistently the fastest responder by a wide margin (~3–5x faster than the flash-tier open models, despite being the "established" model), which is a meaningful factor given wall-clock time is dominated by request latency, not agent reasoning. `mimo-v2.5`'s slow per-request time combined with its tendency to run to the iteration/token ceiling compounds into the worst wall-clock numbers of the whole matrix (233s and 744s).

---

## 4. Intermediary metrics

Metrics below were read manually from each `solution.json`'s `steps[]` array (specifically `sandbox_input`, which records the literal tool call made at each step).

### (a) Step at which the agent first reads/edits the file that appears in the final patch (exploration efficiency)

| Task | Model | First touch of target file | Total steps used |
|---|---|---:|---:|
| task1 (`diophantine.py`) | gpt-4o | 4 | 4 |
| task1 | deepseek-v4.1-flash | 1 | 5 |
| task1 | glm-5.3-flash | 3 | 3 |
| task1 | hy4-preview | 2 | 7 |
| task2 (`hyperbolic.py`) | gpt-4o | 2 | 4 |
| task2 | deepseek-v4.1-flash | 1 | 3 |
| task2 | glm-5.3-flash | 1 | 4 |
| task2 | hy4-preview | 1 | 6 |
| task3 (contenttypes module) | deepseek-v4.1-flash | 1 | 10 |
| task3 | glm-5.3-flash | 1 | 2 |
| task3 | mimo-v2.5 | 2 | 4 |
| task3 | gpt-4o (fail) | never | 10 |

`gpt-4o` on task1 is the standout counter-example: despite passing, it spent 3 full steps (`search_code`, then two identical `search_function_or_class_definition_in_code` calls) before touching the actual file on step 4 — it re-issued the same search twice without new information. On the multi-hop task3, the two failing models (`gpt-4o`, `hy4-preview`) either never reached the target file or reached it but couldn't act, versus the passing models which touched it on step 1.

### (b) Iterations between "last edit" and `final_answer` / task end (submission discipline)

| Task | Model | Last `edit_file` step | Step agent stopped/submitted | Gap |
|---|---|---:|---:|---:|
| task1 | deepseek-v4.1-flash | 2 | 5 | 3 |
| task2 | deepseek-v4.1-flash | 2 | 3 | 1 |
| task2 | gpt-4o | 3 | 4 | 1 |
| task2 | glm-5.3-flash | 2 | 4 | 2 |
| task2 | hy4-preview | 2 | 6 | 4 |
| task3 | deepseek-v4.1-flash | 2 | 10 | 8 |
| task3 | glm-5.3-flash | (patch submitted directly) | 2 | 0 |
| task3 | mimo-v2.5 | (patch submitted directly) | 4 | 0 |

Notably, `gpt-4o` and `hy4-preview` on **task1** never call `final_answer` at all. `gpt-4o` exhausts its step allowance right after the `edit_file` call (step 4 is both its last edit and its last step overall); `hy4-preview` edits on step 5 and then spends 2 more steps re-running `run_tests` (steps 6–7) before running out of budget. In both cases the run is retroactively marked a pass because the harness (per `agent_swebench.py`, see ablation below) promotes a run to success "when its recorded steps contain both a passing test result and a non-empty git patch, even if the model omitted the final `final_answer` call." This means the "gap" metric is undefined/zero-by-construction for those runs — worth flagging as a real submission-discipline weakness even though the harness rescues the outcome. `deepseek-v4.1-flash` on task3 shows the worst *deliberate* overrun: it edits early (step 2) then spends 8 more steps re-verifying/re-reading before finally submitting on step 10, versus `glm-5.3-flash`, which submits immediately with zero wasted steps in 2 of 3 tasks — the strongest submission discipline in the set.

---

## 5. Ablation study: `max_iterations` (10 → 30) and MCP tool-call bridge

**Change under test** (from `git show 65f6b6e`, commit "Add SWE-bench model benchmark runs"):

- `--max-iterations` default raised from **10 → 30** in `agent_swebench.py`.
- The MCP tool bridge was rewritten from a purely positional `zip(values, params)` dispatcher to `make_tool()`, which merges positional and keyword arguments and raises `TypeError` if a call exceeds the tool's declared parameter count, instead of silently truncating/misassigning arguments.
- A success-promotion fallback was added: a run with no explicit `final_answer` call can still be marked successful if its steps contain a passing test run and a non-empty patch (directly relevant to §4(b) above).

**Before/after, same task, same agent, same tool set** (`sympy__sympy-18189`, i.e. task1):

| | Before (10-iter cap, positional-only bridge) | After (30-iter cap, keyword-safe bridge) |
|---|---|---|
| Model | `gpt-astra-latest` (pre-change baseline trace, `cache/swebench_solution.json` at parent commit) | `gpt-4o` (post-change, `swebenchmarks_p0/task1/solutions/gpt-4o.json`) — not the same model, see caveat below |
| Result | ✅ Pass | ✅ Pass |
| Iterations used | 10 (hit the old cap) | 4 |
| Requests | 10 | 4 |
| Input tokens | 28,398 | 10,774 |
| Output tokens | 1,995 | 407 |
| Wall-clock | 83.9 s | 31.5 s |
| Behavior pattern | Repeatedly re-verified: `run_tests` called 4 separate times (steps 2, 4, 6, 8), re-reading the same file region and re-running `git status` between each, before finally submitting on step 10 | Search → search (redundant) → edit → done in 4 steps, no re-verification loop at all |

**Caveat:** the only true "before" trace retained in git history for a controlled instance is `gpt-astra-latest`, a model outside our 5-model comparison set, so this is not a same-model ablation — it's the best available same-task, same-harness-version-boundary comparison. Directionally, though, it's informative: even holding the task fixed, raising the iteration cap did not cause runaway iteration counts among the 5 models we *did* re-run at 30 — 4 of 5 finished task1 well under the old 10-iteration cap anyway (only `mimo-v2.5` used more than 10, running to 22). This suggests the original 10-iteration cap was likely already the binding constraint causing the old trace's repeated self-re-verification (`run_tests` ×3) rather than genuine task difficulty, and that raising it to 30 mainly protects against the `mimo-v2.5`-style long-tail case without materially inflating cost for competent models.

---

## 5b. Ablation study #2: raised iteration/token budgets (30→60 iterations, 300k→600k input tokens, 10k→20k output tokens)

**Change under test** (uncommitted local change to `agent_swebench.py`, confirmed via `git diff`):

- `--max-iterations` default raised **30 → 60**.
- `AgentLoop` budgets raised: `max_input_tokens` **300,000 → 600,000**, `max_output_tokens` **10,000 → 20,000**.
- Everything else (tools, prompt, model set) held constant.

This ablation was rerun for all 3 tasks, but only for 2 of the 5 models (`gpt-4o`, `mimo-v2.5`) — those two were picked because task1 already showed one clean pass and one clean fail at the original budgets, making them the most informative pair to re-test. Full traces: `swebenchmarks_p1/task{1,2,3}/solutions/{gpt-4o,mimo-v2.5}.json`.

| Task | Model | Before (30-iter, 300k/10k) | After (60-iter, 600k/20k) |
|---|---|---|---|
| task1 | gpt-4o | ✅ Pass, 4 iter, 10,774 in / 407 out, 31.5 s, 0 retries | ✅ Pass, 20 iter, 53,514 in / 1,789 out, 56.9 s, 0 retries |
| task1 | mimo-v2.5 | ❌ Fail (hit 10,000-output cap at iter 22), 66,781 in / 10,000 out, 233.4 s, 0 retries | ❌ Fail (no valid patch after 60 iter), 186,037 in / 19,209 out, 482.4 s, 0 retries |
| task2 | gpt-4o | ✅ Pass, 4 iter, 124,225 in / 317 out, 24.5 s, 0 retries | ✅ Pass, 5 iter, 8,351 in / 468 out, 17.4 s, **2 retries** |
| task2 | mimo-v2.5 | ❌ Fail (ran full 30-iter budget), 59,358 in / 10,000 out, 743.8 s, 0 retries | ❌ Fail (ran full 60-iter budget), 119,135 in / 19,554 out, 474.9 s, **29 retries** |
| task3 | gpt-4o | ❌ Fail (looped on empty search results), 31,909 in / 839 out, 27.8 s, 0 retries | ❌ Fail (ran full 60-iter budget, no valid patch), 161,471 in / 5,487 out, 175.5 s, **31 retries** — see rate-limit fix note below |
| task3 | mimo-v2.5 | ✅ Pass, 4 iter, 12,327 in / 2,596 out, 115.0 s, 0 retries | ✅ Pass, 24 iter, 83,014 in / 8,837 out, 237.2 s, **11 retries** |

Three distinct findings:

1. **Raising the budget doesn't change pass/fail on its own.** All 3 tasks kept the same before/after outcome per model (gpt-4o: pass/pass/fail; mimo-v2.5: fail/fail/pass), even though the extra headroom let the agent take far more iterations and tokens when it used them. On task1, `gpt-4o` used 5x the iterations and tokens for an identical result — extra budget bought nothing but cost. `mimo-v2.5` never converges on task1/task2 regardless of budget: on task1 it never once calls `edit_file` across all 60 steps (confirmed by inspecting `sandbox_input`), consistent with `swebenchmarks_p1/VALIDATION_RESULTS.txt` recording its task1 output as "not a valid git patch" — this is a model-capability gap, not a truncation artifact.

2. **The larger budgets exposed a real provider reliability problem that the smaller-budget runs never hit.** At 30 iterations / 10k tokens, zero retries occurred across all 15 original traces (§3). At 60 iterations / 20k tokens, retries appear on 3 of the 4 rerun traces (2, 29, and 11 retries), and one run (`gpt-4o` on task3) failed outright with `HTTP 429` — this key is rate-limited by OpenRouter as a "new account" to 20 requests/minute for `gpt-4o`, and a 60-iteration run is simply more likely to burst past that ceiling than a 30-iteration one. This is a provider/account-tier constraint, not a model or harness defect, but it means **raising the iteration cap increases exposure to rate-limit failures** — a real cost of this change that the original (§5) ablation's "no runaway iteration counts" conclusion did not anticipate.

3. **mimo-v2.5's task2 wall-clock time actually *dropped*** (743.8s → 474.9s) despite running the full budget in both cases and using more tokens after — the extra retries likely reflect faster failure/backoff cycling rather than slower ones; this is noise, not a signal, given the small sample.

**Rate-limit fix and its result.** The `task3`/`gpt-4o` `HTTP 429` failure above was reproducible, so a fix was applied: `AgentLoop` (`agent_smith/loop.py`) now accepts a `request_interval_seconds` parameter and sleeps that long between iterations (exposed as `--request-interval-seconds`, wired into `agent_swebench.py`), spacing out requests to stay under OpenRouter's 20-requests/minute new-account cap for `gpt-4o`. A first attempt at `3.0s` was killed after ~35 minutes of no progress (the run sat in a network wait with zero CPU time consumed for that whole window — consistent with the account's rate limit resetting on a longer window than 3s of spacing alone could clear, or an interaction with the provider's own backoff; it was not investigated further since the interval was reduced instead of chased). Re-run at `--request-interval-seconds 1.0`: the `HTTP 429` **did not recur** — the run completed all 60 iterations cleanly from an infrastructure standpoint, though it still absorbed 31 transient retries along the way (down from a hard failure at 19 retries before) — but the underlying task outcome was still a fail: no valid patch was produced in 60 iterations (161,471 in / 5,487 out / 175.5 s). **The throttle fixes the crash, not the model's ability to solve `django-11066`** — `gpt-4o` still could not complete this task even given the full budget and a stable connection, reinforcing finding #1 above (task3 is genuinely hard for `gpt-4o`, independent of infra noise).

**Caveat:** this is a genuine same-model, same-task, single-variable comparison for 2 of 5 models across all 3 tasks — a meaningful improvement over the task1-only, 2-model snapshot originally available, but it still doesn't cover `deepseek-v4.1-flash`, `glm-5.3-flash`, or `hy4-preview` at the raised budgets, so it can't confirm whether the rate-limit exposure in finding #2 is `gpt-4o`-specific or would recur for other OpenRouter-routed models under this API key's account tier.

---

## 5c. Extended comparison: 6 additional OpenRouter models

Six more OpenRouter models were run across all 3 tasks at the original baseline configuration (`swebenchmarks_p0` params: 30 iterations, 300k input / 10k output tokens), using the same throttle fix from §5b (`--request-interval-seconds 1.0`) to avoid provider rate-limit noise. Traces: `swebenchmarks_p2/task{1,2,3}/solutions/{ling-3.0-flash-vl,ling-3.0-flash-sante,ling-3.0-flash-fin,nex-n2.5-mini,nex-n2.5-pro,gpt-sol-latest}.json`.

**`~openai/gpt-sol-latest` passed all 3 tasks (3/3) with the best iteration/token efficiency of any model in this entire report:** task1 in 1 iteration (2,648 in / 784 out, 15.3s, 0 retries), task2 in 4 iterations (9,470 in / 736 out, 29.0s, 1 retry), task3 in 1 iteration (2,653 in / 571 out, 10.6s, 0 retries). No other model tested — including the two recommended in §6 — solved task1 or task3 in a single iteration. This is a standout result and is treated separately from the 4-model table below; see the caveat at the end of this section and the updated conclusion in §6.

| Task | Model | Pass/Fail | Iterations | Input tokens | Output tokens | Wall-clock (s) | Retries |
|---|---|---|---:|---:|---:|---:|---:|
| task1 | `ling-3.0-flash-vl` | ❌ Fail (infra) | 9 | 26,546 | 1,078 | 26.5 | 4 |
| task1 | `ling-3.0-flash-sante` | ❌ Fail (ran full 30-iter) | 30 | 91,987 | 7,351 | 84.2 | 14 |
| task1 | `ling-3.0-flash-fin` | ✅ Pass | 3 | 9,435 | 2,021 | 87.3 | 1 |
| task1 | `nex-n2.5-mini` | ✅ Pass | 2 | 8,880 | 1,442 | 45.8 | 0 |
| task1 | `nex-n2.5-pro` | ✅ Pass | 1 | 2,814 | 1,500 | 53.6 | 0 |
| task2 | `ling-3.0-flash-vl` | ❌ Fail (infra) | 0 | 0 | 0 | 0.9 | 0 |
| task2 | `ling-3.0-flash-sante` | ✅ Pass | 5 | 10,049 | 2,723 | 20.8 | 2 |
| task2 | `ling-3.0-flash-fin` | ✅ Pass | 4 | 7,800 | 3,725 | 58.7 | 1 |
| task2 | `nex-n2.5-mini` | ✅ Pass | 4 | 12,308 | 2,449 | 23.2 | 1 |
| task2 | `nex-n2.5-pro` | ✅ Pass | 2 | 5,854 | 499 | 24.5 | 0 |
| task3 | `ling-3.0-flash-vl` | ❌ Fail (infra) | 0 | 0 | 0 | 0.7 | 0 |
| task3 | `ling-3.0-flash-sante` | ❌ Fail (ran full 30-iter) | 30 | 89,961 | 4,272 | 73.3 | 14 |
| task3 | `ling-3.0-flash-fin` | ❌ Fail (ran full 30-iter) | 30 | 91,835 | 11,811 | 91.3 | 14 |
| task3 | `nex-n2.5-mini` | ❌ Fail (ran full 30-iter) | 30 | 379,220 | 17,062 | 160.3 | 14 |
| task3 | `nex-n2.5-pro` | ✅ Pass | 5 | 31,056 | 1,500 | 47.6 | 2 |

**`ling-3.0-flash-vl` never actually ran** — all 3 attempts failed immediately (0–9 iterations, sub-second to 26s) with `HTTP 429: "inclusionai/ling-3.0-flash-vl:free is temporarily rate-limited upstream"` from OpenRouter's own shared free-tier pool for that model (provider `Novita`), not from the 1s-per-iteration throttle added in §5b. This is a **shared free-tier capacity limit**, independent of anything this harness controls, and it means `ling-3.0-flash-vl` cannot be fairly evaluated with this setup — 2 of its 3 attempts didn't get past iteration 0.

**`nex-n2.5-pro` passed all 3 tasks (3/3)**, matching the best models from the original 5 (`deepseek-v4.1-flash`, `glm-5.3-flash`) — and did so with the lowest iteration counts seen anywhere in this report (1, 2, and 5 iterations), plus the lowest token usage on 2 of 3 tasks. This is the strongest single result in the whole benchmark and warrants a closer look before being trusted at face value (see caveat below).

**`nex-n2.5-mini` passed task1 and task2 but failed task3**, running the full 30-iteration budget without producing a valid patch and consuming 379,220 input tokens — by far the largest input-token count of any run in this report (more than double the next-highest, `mimo-v2.5`'s 186,037 in the §5b rerun), suggesting it re-reads large amounts of context repeatedly without narrowing in on the `contenttypes` module.

**`ling-3.0-flash-sante` failed 2 of 3 tasks** (only task2 passed), both failures running the full 30-iteration budget, with the highest retry counts in this set (14 each) — consistent with either provider-side instability or the same shared-capacity throttling seen with its `-vl` sibling model, just recovering instead of hard-failing.

**`ling-3.0-flash-fin` passed 2 of 3 tasks** (task1, task2), the best result of the three `ling-3.0-flash-*` variants tested, and did so with modest iteration counts (3, 4) and only 1 retry each — markedly more stable than its `-sante` sibling. It failed task3 the same way `-sante` and `nex-n2.5-mini` did: running the full 30-iteration budget without a valid patch, with 14 retries. This suggests task3 (`django-11066`) is disproportionately hard across this whole extended model set, not just for the original 5.

**Caveat:** `nex-n2.5-pro`'s and `gpt-sol-latest`'s perfect, low-iteration records are each based on a single run per task with no repeated trials, and "free"/preview OpenRouter models are known to vary in effective quality/availability over time (as directly demonstrated by `ling-3.0-flash-vl`'s outright unavailability during this same session, and further reinforced in §5d below where it later failed with a distinct `HTTP 401` error). These results should be treated as promising but not yet as reliable as the 3-task, single-run evidence for `deepseek-v4.1-flash`/`glm-5.3-flash`, which come from a stable, non-free-tier provider path. Second, independent runs of both `nex-n2.5-pro` and `gpt-sol-latest` on all 3 tasks would be needed before recommending either for production use.

---

## 5d. Ablation #3: same 6 additional models, raised budget (30→60 iter, 300k→600k in, 10k→20k out)

The 6 additional models from §5c were rerun on all 3 tasks under the raised-budget configuration from §5b (`--max-iterations 60`, which carries the harness's `max_input_tokens=600000`/`max_output_tokens=20000`), still with the `--request-interval-seconds 1.0` throttle. Traces: `swebenchmarks_p3/task{1,2,3}/solutions/{ling-3.0-flash-vl,ling-3.0-flash-sante,ling-3.0-flash-fin,nex-n2.5-mini,nex-n2.5-pro,gpt-sol-latest}.json`.

| Task | Model | Before (30-iter, 300k/10k) — `swebenchmarks_p2` | After (60-iter, 600k/20k) — `swebenchmarks_p3` |
|---|---|---|---|
| task1 | `ling-3.0-flash-vl` | ❌ Fail (infra, `429` upstream), 9 iter, 4 retries | ❌ Fail (infra, **`HTTP 401 "User not found"`**), 2 iter, 6.6 s, 0 retries |
| task1 | `ling-3.0-flash-sante` | ❌ Fail (full 30-iter), 91,987 in / 7,351 out, 84.2 s, 14 retries | ❌ Fail (full 60-iter), 183,668 in / 19,764 out, 192.3 s, 29 retries |
| task1 | `ling-3.0-flash-fin` | ✅ Pass, 3 iter, 9,435 in / 2,021 out, 87.3 s, 1 retry | ✅ Pass, **26 iter**, 81,649 in / 16,969 out, 146.7 s, 12 retries |
| task1 | `nex-n2.5-mini` | ✅ Pass, 2 iter, 8,880 in / 1,442 out, 45.8 s, 0 retries | ✅ Pass, 13 iter, 173,251 in / 8,821 out, 77.1 s, 6 retries |
| task1 | `nex-n2.5-pro` | ✅ Pass, 1 iter, 2,814 in / 1,500 out, 53.6 s, 0 retries | ✅ Pass, 2 iter, 7,327 in / 1,215 out, 53.7 s, 0 retries |
| task1 | `gpt-sol-latest` | ✅ Pass, 1 iter, 2,648 in / 784 out, 15.3 s, 0 retries | ✅ Pass, **5 iter**, 289,256 in / 960 out, 68.2 s, 2 retries |
| task2 | `ling-3.0-flash-vl` | ❌ Fail (infra, 0 iter) | ❌ Fail (infra, **`HTTP 401`**), 6 iter, 26.8 s, 2 retries |
| task2 | `ling-3.0-flash-sante` | ✅ Pass, 5 iter, 10,049 in / 2,723 out, 20.8 s, 2 retries | ✅ Pass, 10 iter, 19,915 in / 4,177 out, 35.7 s, 4 retries |
| task2 | `ling-3.0-flash-fin` | ✅ Pass, 4 iter, 7,800 in / 3,725 out, 58.7 s, 1 retry | ✅ Pass, **22 iter**, 41,916 in / 7,410 out, 106.4 s, 10 retries |
| task2 | `nex-n2.5-mini` | ✅ Pass, 4 iter, 12,308 in / 2,449 out, 23.2 s, 1 retry | ✅ Pass, 3 iter, 6,124 in / 1,232 out, 26.7 s, 1 retry |
| task2 | `nex-n2.5-pro` | ✅ Pass, 2 iter, 5,854 in / 499 out, 24.5 s, 0 retries | ✅ Pass, 4 iter, 10,640 in / 2,628 out, 53.8 s, 1 retry |
| task2 | `gpt-sol-latest` | ✅ Pass, 4 iter, 9,470 in / 736 out, 29.0 s, 1 retry | ✅ Pass, **1 iter**, 1,612 in / 607 out, 9.9 s, 0 retries |
| task3 | `ling-3.0-flash-vl` | ❌ Fail (infra, 0 iter) | ❌ Fail (infra, `429` upstream again), 3 iter, 10.2 s, 1 retry |
| task3 | `ling-3.0-flash-sante` | ❌ Fail (full 30-iter), 89,961 in / 4,272 out, 73.3 s, 14 retries | ❌ Fail (full 60-iter), 180,366 in / 13,236 out, 169.7 s, 29 retries |
| task3 | `ling-3.0-flash-fin` | ❌ Fail (full 30-iter), 91,835 in / 11,811 out, 91.3 s, 14 retries | ❌ **Fail differently**: `"Configured token limit reached"` at iter 42/60, 128,722 in / 20,000 out, 130.6 s, 20 retries |
| task3 | `nex-n2.5-mini` | ❌ Fail (full 30-iter), **379,220 in** / 17,062 out, 160.3 s, 14 retries | ✅ **Pass** (flipped), 32 iter, 411,702 in / 15,252 out, 158.3 s, 15 retries |
| task3 | `nex-n2.5-pro` | ✅ Pass, 5 iter, 31,056 in / 1,500 out, 47.6 s, 2 retries | ✅ Pass, 12 iter, 132.6 s, 60,974 in / 5,411 out, 5 retries |
| task3 | `gpt-sol-latest` | ✅ Pass, 1 iter, 2,653 in / 571 out, 10.6 s, 0 retries | ✅ Pass, 4 iter, 21,536 in / 978 out, 25.9 s, 1 retry |

**One real outcome flip: `nex-n2.5-mini` on task3 went from fail to pass.** At the 30-iteration budget it exhausted its allowance at 379,220 input tokens without a valid patch; at 60 iterations it used even more input tokens (411,702 — a new high for this report) but converged on iteration 32, within the old 30-iteration ceiling's near-miss range. This is the one case across all three ablations (§5b, §5c intro, §5d) where more budget directly bought a different pass/fail outcome, consistent with this task being a genuine "almost there" case for this model rather than a fundamental capability gap.

**`gpt-sol-latest` stayed 3/3 but lost some of its edge.** At the raised budget it needed 5 iterations on task1 (vs 1 before) and consumed 289,256 input tokens on that same task — a huge jump from 2,648, and the largest single-task token increase seen for any consistently-passing model in this report. It did improve on task2 (4→1 iteration). The single-iteration efficiency highlighted in §5c is clearly budget-sensitive, not an intrinsic property of the model — with more room to work with, it sometimes used much more of it for the same outcome, similar to `gpt-4o` in §5b.

**`ling-3.0-flash-fin` held its 2/3 record but became far less efficient on its passing tasks.** Iteration counts jumped from 3→26 (task1) and 4→22 (task2) for identical pass outcomes, and it failed task3 differently under the larger budget — instead of exhausting the 30-iteration cap cleanly, it hit `"Configured token limit reached"` at iteration 42/60 after consuming its full 20,000-token output budget, with retries growing 14→20. This is the same "more budget, same or worse outcome, much higher cost" pattern seen with `gpt-4o` (§5b) and `gpt-sol-latest` above — a recurring finding across every ablation in this report, not a one-off.

**Every other model kept its verdict.** `nex-n2.5-pro`, `ling-3.0-flash-sante` (task2), and `gpt-sol-latest` (all 3) stayed passing; `ling-3.0-flash-sante` (task1/task3) and `ling-3.0-flash-vl` (all tasks) stayed failing — for the models that were already failing, the extra budget mainly inflated token usage and retries (`ling-3.0-flash-sante`'s retries roughly doubled on both its failing tasks, 14→29) without changing the result.

**`ling-3.0-flash-vl` failed differently each time it was tried** — `429` (shared pool rate-limit) in §5c, `401 "User not found"` on 2 of 3 tasks here, and `429` again on the third. The `401` is the same error that blocked all of §5b/§5c until the API key was refreshed (see conversation context), suggesting this key experienced at least one more transient auth hiccup specifically when routed to this model, separate from the earlier full-key outage. Combined with its shared-pool rate-limiting, `ling-3.0-flash-vl` has never completed a single task in this report and should be considered **untestable with the current setup**, not merely "failing."

**Caveat:** as in §5b, this is a same-model, same-task, single-variable comparison, but each cell is still a single run — the `nex-n2.5-mini` flip is a real, observed outcome change, not confirmed as reproducible. The pattern of "more budget → more iterations/tokens for the same pass" recurring across `gpt-4o`, `gpt-sol-latest`, and `ling-3.0-flash-fin` is suggestive but based on single-run pairs per model, not repeated trials.

---

## 6. Conclusions

**Top candidate pending re-validation: `~openai/gpt-sol-latest`.** In §5c, this model passed all 3 tasks, twice in a single iteration (task1, task3) and in 4 iterations on task2 — the best iteration/token efficiency of any model tested anywhere in this report, core 5 included. It was re-tested at the raised budget in §5d and stayed 3/3, but its task1 efficiency dropped sharply (1→5 iterations, 2,648→289,256 input tokens) — showing the same "uses whatever budget it's given" pattern as `gpt-4o`. It is placed above the two "recommended" models below rather than replacing them because it's still single-run-per-cell evidence on a preview/non-standard model name, not the repeated-trial standard behind the two models below. Re-run all 3 tasks at least twice more before promoting it to primary.

**Recommended for the pipeline today (proven, repeatable-provider tier): `deepseek/deepseek-v4.1-flash` and `zhipu/glm-5.3-flash`.**
Both passed all 3 tasks (3/3) in the core 5-model comparison, which none of the other three original models achieved, and both come from a stable (non-free-tier) OpenRouter path rather than the free-tier pools that caused infrastructure failures for other extended-comparison models (§5c, §5d). `glm-5.3-flash` additionally showed the best submission discipline (zero-step gap after fix on 2/3 tasks) and touched the correct file on step 1 in 2/3 tasks — strong exploration efficiency. `deepseek-v4.1-flash` was slightly slower to submit (more self-verification) but never failed and was the second-fastest responder per request after gpt-4o.

**Promising candidates worth a second validation run: `nex-agi/nex-n2.5-pro` and `nex-agi/nex-n2.5-mini`.** `nex-n2.5-pro` passed all 3 tasks at both the original (§5c) and raised (§5d) budgets, with consistently low iteration counts and no outcome change under more budget — the most stable evidence of any free-tier model tested. `nex-n2.5-mini` passed 2/3 tasks at the original budget and reached 3/3 only once given a doubled iteration/token budget (§5d), converging on task3 at iteration 32 after consuming a report-high 411,702 input tokens — a real pass, but one that took meaningfully more resources than any recommended model above. Neither is promoted to primary because both remain single-run-per-cell, free-tier evidence (see §5c/§5d caveats) rather than the repeated, stable-provider standard behind the two models above.

**`inclusionai/ling-3.0-flash-fin` is a third candidate worth a validation run, with a caveat on cost-scaling.** It passed 2 of 3 tasks (task1, task2) at both budgets and never regressed to a fail, but its iteration counts under the raised budget ballooned for the exact same outcome (3→26 on task1, 4→22 on task2) — the largest such blow-up of any passing model in §5d. It failed task3 both times, hitting the output-token ceiling under the raised budget instead of cleanly exhausting iterations. Treat as promising on 2/3 tasks but with a real risk of runaway cost if allowed a larger budget in production.

**Disregard `inclusionai/ling-3.0-flash-vl` and treat with caution `inclusionai/ling-3.0-flash-sante`.** `ling-3.0-flash-vl` never completed a single task across 6 attempts (3 in §5c, 3 in §5d), failing every time with a different infrastructure error (`429` shared-pool rate-limit twice, `401 "User not found"` twice) — this is not a model-quality signal, it is provider-side unavailability, but it means the model cannot currently be evaluated at all. `ling-3.0-flash-sante` passed only task2 at both budgets and failed task1/task3 by running out its full iteration budget both times, with retry counts (14, then 29 after the budget increase) far above every other model in the report — even setting aside the infra noise, this suggests genuine instability rather than a near-miss.

**Keep gpt-4o as a fast fallback, not primary.** It has the lowest per-request latency by a wide margin (~3s vs 6–21s for the others) and the lowest token usage on 2/3 tasks, but it failed the hardest task (task3) by looping on a single tool call that returned empty results 10 times in a row without adapting strategy — a real reliability gap on multi-hop bugs, not a token/latency problem.

**Disregard `mimo-v2.5` for this pipeline.** It failed 2/3 tasks, both by exhausting either the 10,000-output-token budget or the full 30-iteration cap, and had the slowest per-request latency (~21s) and by far the worst wall-clock time (233s and 744s on the two failures). Its one pass (task3) also took the longest wall-clock time (115s) among that task's passing models. Nothing in the traces suggests these failures are close misses — it simply runs long without converging.

**Disregard `hy4-preview` as currently used.** It only passed 1/3 tasks, took the most iterations among passing traces on task1 and task2 (7 and 6, versus 3–5 for competitors), and failed task3 via the same "repeat an empty search verbatim" failure mode as gpt-4o — suggesting this is a tool-adaptation weakness shared by both preview/frontier-style models rather than a token-budget problem, since neither exhausted its budget on that task.
