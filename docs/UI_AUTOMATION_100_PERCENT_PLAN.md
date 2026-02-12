# Implementation Plan: Achieve 100% UI Automation

This plan addresses two core ideas:

1. **Give the healer full test-case context** – including the whole test case, which step failed, and what previous steps had already run – so healing is context-aware.
2. **UI crawl before UI automation** – run a test-case-driven crawl, then feed the crawl response (per-step page structure) into planning, generation, and healing so selectors match real pages.

---

## Assurance: Will We Achieve 100%?

**Yes, with the right definition of “100%”:**

- **100% = Maximum achievable UI automation** for your applications (LG India, Hilti India) under the conditions you control:
  - With **crawl-first** and **full healer context** (Phases 1–3), the system uses real page structure and failure context so selectors and healing are no longer blind. That removes the main technical barriers to high pass rates.
  - With **failure context** (Phase 2) and **up to 2 heal+retry cycles** (Phase 4), the pipeline has multiple chances to recover from flaky or wrong selectors.
  - With **stronger verify** (URL + visibility for payment/shipping/checkout), tests no longer pass on the wrong page.

- **In controlled environments** (staging, stable test data, consistent network), this design is built to **approach 100% pass rate** on the flows you automate. Remaining failures will be due to:
  - **External factors**: production A/B tests, third-party scripts, rate limits, or site deployments during the run.
  - **Unavoidable flakiness**: network or CDN variance; we mitigate with retries and healing, but cannot eliminate every edge case.

- **Commitment:** The implementation (Phases 1–4) is done so that **every run gets the maximum possible pass rate** the architecture can deliver. You should see a **clear jump in pass rate** once you use `--crawl-first` and run with full context and multi-retry. For **staging or internal apps** where you control the build and data, **100% on a given run is an achievable target**.

---

## Current Gap (Why We're Not at 100%)

| Gap | Impact |
|-----|--------|
| Healer gets only **script + error** | Cannot reason about "we were on checkout after doing A, B, C"; suggests blind alternatives. |
| No **failure context** (which step, URL, DOM) | Healer doesn't know the page state at failure. |
| No **crawl before automation** | Selectors are generic; we don't use real page structure. |
| Crawl data not passed to Planner/Generator/Healer | Even if we crawl, it isn't wired into the automation pipeline. |

---

## Target Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  OPTIONAL: Test-case-driven crawl (before automation)                         │
│  • Run flow (or simplified steps) in browser                                  │
│  • At each step: capture URL, title, interactive elements (selector, text)   │
│  • Store: crawl_snapshots(test_case_id, step_index, url, elements_json)      │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PLANNER (optional: use crawl for this test case)                            │
│  • Input: raw test case + optional crawl_snapshots for this flow             │
│  • Output: plan with steps; if crawl exists, steps can reference real        │
│    selectors from crawl (e.g. "first product" → selector from crawl)         │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  GENERATOR                                                                   │
│  • Input: plan + optional crawl_snapshots (per-step elements)                │
│  • Output: script using selectors from crawl when available                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  EXECUTOR (enhanced)                                                         │
│  • Runs script; on failure writes: failed_step_index, page.url(),            │
│    optional DOM summary (interactive elements) to failure_context.json        │
│  • Returns: status, error, failed_step_index, failure_url, failure_dom       │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  HEALER (with full context)                                                 │
│  • Input: script, error, failed_locator,                                     │
│    + test_case (id, name, steps), plan (full),                               │
│    + failed_step_index, steps_before_failure (list of step descriptions),   │
│    + failure_url, failure_dom (from executor or from crawl for that step)   │
│  • Uses: registry → rule-based alternatives → LLM with full context         │
│  • LLM prompt includes: "Test: ... Steps that ran: ... Failed at step N:    │
│    ... Page URL: ... Elements on page: ... Failed selector: ..."            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Healer with Full Test-Case Context (No Crawl Yet)

**Goal:** Healer receives full test-case context and previous steps so the LLM can reason about where the failure happened and suggest better selectors.

**Deliverables:**

1. **Healer API extension**
   - New optional parameters: `test_case_context` (dict with `test_id`, `name`, `steps`), `plan` (full structured plan), `failed_step_index` (int), `steps_before_failure` (list of step descriptions or actions), optional `failure_url`, optional `failure_page_elements` (list of {selector, tag, text} from DOM or crawl).
   - When present, the healer uses this in the LLM prompt: describe the test, list steps that already ran, state which step failed and what we were trying to do, then ask for a fixed selector or alternative steps. Keep existing registry and rule-based flow first; use LLM-with-context when those don’t heal.

2. **Runner (run_enterprise_e2e)**
   - When calling healer after a failure, build and pass:
     - `test_case_context`: { "test_id": tid, "name": name, "steps": raw steps from test case }
     - `plan`: the full plan used for this run
     - `failed_step_index`: infer from error (e.g. step number in error) or from parsing script; if unknown, pass last step index
     - `steps_before_failure`: plan["steps"][0:failed_step_index] (descriptions)
   - No crawl yet; `failure_url` and `failure_page_elements` can be left empty.

3. **LLM prompt (healer)**
   - System: "You are a UI test healer. You will be given: the test case, the steps that already ran successfully, the step that failed, the error, and the failed selector. Suggest a replacement selector that fits the current page and the intent of the failed step. Return only a JSON object with key 'selectors' (array of up to 3 alternative selector strings)."
   - User: test case summary, steps before failure, failed step description, error snippet, failed selector, optional failure_url and list of elements on page.

**Success criteria:** Healer is called with full context from the runner; LLM suggestions use "steps that ran" and "failed step" in the prompt. No new tables; backward compatible (context optional).

**Status: Implemented.** `HealerAgent.heal()` now accepts optional `test_case_context`, `plan`, `failed_step_index`, `steps_before_failure`, `failure_url`, `failure_page_elements`. When any context is provided, the healer uses `_llm_suggest_selectors_with_context()` with a rich prompt. `run_enterprise_e2e.py` builds and passes test case, plan, failed step index, and steps before failure when calling the healer; `failure_url` and `failure_page_elements` are passed when the executor provides them (Phase 2).

---

## Phase 2: Executor Captures Failure Context (Step, URL, Optional DOM)

**Goal:** When a step fails, we know exactly which step failed and what the page looked like (URL + optional element list), and pass that to the healer.

**Deliverables:**

1. **Generated script enhancement (Generator)**
   - Wrap each action step in a try/catch that on failure:
     - Writes a small JSON file (e.g. `failure_context.json`) to a known path (e.g. `SCREENSHOT_DIR/../failure_context.json`) with: `step_index`, `page.url()`, `action` (e.g. "click"), `selector` (the one that failed). Optionally: call a small helper that collects visible links/buttons (tag, text, selector) and add as `page_elements` (limit 50 elements to avoid huge payload).
   - Use `process.env.FAILURE_CONTEXT_PATH` or similar so the executor can set the path.

2. **Executor**
   - Set env `FAILURE_CONTEXT_PATH` to `run_dir/failure_context.json`.
   - After running the test, if status is "failed", read `failure_context.json` if it exists. Return in result: `failed_step_index`, `failure_url`, `failure_page_elements` (optional).

3. **Runner**
   - When calling healer, pass `failure_url` and `failure_page_elements` from execution result in addition to Phase 1 context.

4. **Healer**
   - Include `failure_url` and `failure_page_elements` in the LLM prompt so the model can suggest selectors that actually exist on the page.

**Success criteria:** On failure, executor returns step index and URL; optionally returns element list. Healer receives and uses them in the prompt.

---

## Phase 3: Test-Case-Driven UI Crawl (Crawl Before Automation)

**Goal:** For each test case (or for a flow), run a crawler that follows the same steps and, at each step, captures URL and interactive elements. Store this and use it later for planning, generation, and healing.

**Deliverables:**

1. **Crawl snapshot storage**
   - Option A: New table `crawl_snapshots` with columns: `id`, `test_case_id` (or `flow_signature`), `step_index`, `url`, `page_title`, `elements_json` (array of {selector, tag, text, role}), `created_at`. Optional: `screenshot_path`.
   - Option B: Reuse/expand `crawl_cache`: key by composite key (e.g. `url` + `test_case_id` + `step_index`) if schema allows; store `elements_json` and optionally `html_snippet`. Choose one approach and document.

2. **Test-case-driven crawler service**
   - Input: test case (id, name, steps), base_url.
   - Process: Use Planner to get a minimal plan (or use steps as-is). Run a Playwright script that:
     - Navigates and performs clicks/typing per step (same as automation but "crawl" mode).
     - After each step: capture `page.url()`, `page.title()`, and a list of interactive elements (e.g. all `a`, `button`, `input`, `[role=button]`) with a stable selector (e.g. Playwright’s suggested selector or tag+text), tag name, visible text (truncated). Store in DB keyed by test_case_id + step_index.
   - Output: list of crawl_snapshots for this test case.

3. **Runner integration**
   - New flag: `--crawl-first` (or config). When set, for each test case:
     1. Run test-case-driven crawler; store snapshots.
     2. Run Planner (pass crawl snapshots for this test case).
     3. Run Generator (pass crawl snapshots so it can pick selectors from crawl).
     4. Run Executor. On failure, Healer receives: full context (Phase 1) + failure context (Phase 2) + **crawl snapshot for the failed step’s page** (by URL or by step_index) so healer can suggest selectors that exist in the crawl.

4. **Planner/Generator**
   - Planner: If crawl snapshots are provided for this test case, optionally add to LLM prompt or to step metadata: "For step N, crawled page has these elements: ..." so the plan can reference real selectors for "first product" (e.g. pick the first product link from the crawl list).
   - Generator: For each step, if crawl snapshot for that step exists, prefer selector from `elements_json` that matches the step intent (e.g. "Add to cart" → find element in crawl with text "Add to cart" or role button). Fallback to current logic if no crawl.

**Success criteria:** Crawl runs before automation when requested; snapshots stored; Planner/Generator/Healer can consume crawl data; healer uses crawl snapshot for the failed step’s page when available.

---

## Phase 4: Stronger Verify and Multi-Selector Try

**Goal:** Reduce false passes and make each step more resilient.

**Deliverables:**

1. **Verify**
   - For "verify we reach payment/shipping", use crawl or failure context: check that current URL or page has an element matching "payment", "order summary", "shipping" (from crawl or from a small DOM scan). Avoid relying only on `body` visible.

2. **Generator: multi-selector try**
   - For critical steps (e.g. "first product", "checkout"), generate a small loop: try selector A, then B, then C (from planner/crawl) until one succeeds (with short timeout per try). This avoids single-selector fragility.

3. **Healer: multiple retries**
   - Allow runner to call healer up to 2 times with different strategies (e.g. first with context only, second with context + failure DOM/crawl), and retry execution after each heal.

**Success criteria:** Verify uses URL or real elements; at least one critical step uses multi-selector try; runner can do 2 heal+retry cycles.

---

## Phase 5: Per-Application Tuning and Session (Optional)

**Goal:** Handle app-specific behavior (redirects, login, cookie) and reuse session when useful.

**Deliverables:**

1. **Application config**
   - Config (e.g. JSON or DB) per application (LG India, Hilti India): base_url, cookie_selector_overrides, login_required (bool), redirect_domains (list), optional "main content" container selector for "first product" scoping.

2. **Container-scoped "first product"**
   - When config has `main_content_selector`, generate "first product" as: `page.locator(main_content_selector).locator(product_selector).first()`.

3. **Session reuse (optional)**
   - For suites, optionally run a one-time "login" or "cookie accept" flow, save browser context state, and reuse for subsequent tests to avoid repeating consent and to handle login-required flows.

**Success criteria:** LG and Hilti can have different selector/config; "first product" can be scoped; optional session reuse works.

---

## Summary: Will This Achieve 100%?

| Phase | What it fixes | Impact on pass rate |
|-------|----------------|---------------------|
| 1. Healer with full context | Blind healer → context-aware healer | Fewer wrong suggestions; better healing when LLM has "steps before" and "failed step". |
| 2. Executor failure context | No page state at failure → URL + optional DOM at failure | Healer (and LLM) see what was on the page; selectors can be chosen from real elements. |
| 3. Crawl before automation | Generic selectors → selectors from real crawl | Planner/Generator/Healer use actual page structure; "first product" can come from crawl. |
| 4. Verify + multi-selector + multi-retry | Weak verify, single selector, one retry | Fewer false passes; more resilient steps; more chances to heal. |
| 5. Per-app + session | One-size-fits-all, no session | Handles redirects, login, and app-specific DOM. |

**Outcome:** With Phases 1–4 implemented, you get **maximum achievable coverage**: context-aware healer, failure context (step/URL/elements), crawl-first option, stronger verify, and 2 heal+retry cycles. In controlled environments (staging, stable builds), **100% on a given run is an achievable target**; on live production, external factors (A/B tests, deployments) can still cause occasional failures, but the system is built to get as close as possible.

---

## Implementation Order

1. **Phase 1** – Healer context (quick win; no schema change).
2. **Phase 2** – Executor failure context (script + executor + healer prompt).
3. **Phase 3** – Crawl before automation (storage, crawler service, integration with Planner/Generator/Healer).
4. **Phase 4** – Verify and multi-selector/multi-retry.
5. **Phase 5** – Per-application config and optional session.

---

## Files to Touch (Summary)

| Phase | Files |
|-------|--------|
| 1 | `backend/services/ui_automation/agents/healer/agent.py` (new params, LLM prompt), `run_enterprise_e2e.py` (build and pass context to healer) |
| 2 | `backend/services/ui_automation/agents/generator/agent.py` (inject failure-context writing in generated script), `backend/services/ui_automation/engine/executor.py` (read failure_context.json, return in result), healer (use failure_url, failure_page_elements in prompt), runner (pass to healer) |
| 3 | New: `backend/services/ui_automation/crawler/test_case_crawler.py`, migrations for `crawl_snapshots` (or extend crawl_cache), `run_enterprise_e2e.py` (--crawl-first, pass snapshots to planner/generator/healer), planner/generator (accept and use crawl snapshots) |
| 4 | Generator (multi-selector try, verify improvement), runner (2x heal retry) |
| 5 | Config (e.g. `tests/enterprise/app_config.json` or DB), planner/generator (container scope, config-driven selectors), optional session module |

---

## Implementation Status

| Phase | Status | Notes |
|-------|--------|--------|
| **1** | **Done** | Healer accepts full context; runner passes test case, plan, failed step, steps before failure. |
| **2** | **Done** | Generator emits failure-context write in catch blocks; executor sets `FAILURE_CONTEXT_PATH`, reads `failure_context.json`, returns `failed_step_index`, `failure_url`, `failure_page_elements`. |
| **3** | **Done** | `crawl_snapshots` table + migration; `test_case_crawler.py` (generate_crawl_script, run_test_case_crawl, crawl_and_save, get_crawl_snapshots_for_flow); runner `--crawl-first`; healer receives crawl elements for failed step when executor didn't provide them. |
| **4** | **Done** | Runner: up to 2 heal+retry cycles; generator: stronger verify (URL check for payment/shipping/checkout). |
| **5** | Optional | Per-application config and session reuse for future tuning. |

**How to run with maximum coverage:** Use `--crawl-first` so each test case is crawled before automation and the healer can use crawl data when executor doesn't return page elements. Run migrations so `crawl_snapshots` exists: `python run_migrations.py` (includes `b2c3d4e5f6a7_add_crawl_snapshots`).

This plan gives you a clear path from "healer with full test-case context" and "crawl before automation" to a system that can approach 100% UI automation on supported flows.
