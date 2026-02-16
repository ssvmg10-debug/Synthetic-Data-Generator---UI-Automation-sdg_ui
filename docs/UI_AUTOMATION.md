# UI Automation – Approach, End-to-End Flow & Examples

This document describes how the **UI automation** pipeline works: from a natural-language test scenario to a runnable Playwright flow with self-healing and app-specific selectors.

**POC/demo scope:** Production-grade behaviour without Docker, Celery, or Grafana. Metrics are in-memory; smoke checks and batch revalidation run on-demand or via simple scripts; human review of heals is via REST API.

### Testing the whole LG application with any test case

Yes. For **LG India** (`https://www.lg.com/in`), the app uses the **Flow Engine** (goal: complete guest checkout). You can run **any test case** that describes this journey; the planner extracts:

- **Search query** (e.g. “search for lg 108cm tv”)
- **Product price limit** (e.g. “buy under 30000”)
- **Pincode** (e.g. “enter pincode 500032”)

The flow runs: **accept cookies → search → select product (under price) → add to cart → enter pincode & check → free delivery → checkout → continue as guest → fill billing address**. Billing name/address/phone/city come from the **Test Data Vault** (`get_synthetic_address()` — use env vars `UI_TEST_NAME`, `UI_TEST_PINCODE`, etc., or defaults).

**What’s not mocked:** The **payment** step is not stubbed. For full E2E without real payment, use LG’s staging/test environment or treat the run as complete once the address form is filled. Set `UI_AUTOMATION_STAGING=1` and `UI_AUTOMATION_MOCK_PAYMENT=1` when using a test environment that supports them.

---

## 1. High-Level Approach

- **Input:** Free-text test scenario (e.g. “Go to LG India, accept cookies, search for 108cm TV, buy one under 30000, enter pincode 500032, checkout as guest”).
- **Output:** A structured plan → a Playwright script (for reference) → an **enhanced script** (goto + steps with selectors, alternatives, and locator hints) → **execution** in a real browser with retries and healing.
- **Resilience:** Each step can use **multiple selectors** (primary + alternatives from app config), **Playwright role/placeholder locators** (locator hints) first, and **healing** (fuzzy match from page elements or locator hint) when the primary selector fails.

### Design principles

| Principle | How it’s done |
|-----------|----------------|
| **Intent-based** | Steps are classified into intents (e.g. `search_icon`, `cookie_accept`, `pincode_zip`). Intents map to app-specific selector lists and Playwright locator hints. |
| **App-specific config** | `app_config` (e.g. for `lg.com`) provides ordered selector lists per intent (cookie, search icon, search box, checkout, etc.) so the same plan works across sites. |
| **Layered locators** | For each step we try: (1) **locator_hint** (get_by_role / get_by_placeholder / get_by_label), (2) primary **selector**, (3) **alternatives**, (4) **healing** (fuzzy match or locator hint again). |
| **Step-through validation** | Pre-execution validation runs steps in order on a real page (goto → step 1 → execute → step 2 on new state → …) so selectors are checked on the correct page. |
| **State-deterministic execution** | After major transitions (search, buy/add-to-cart, pincode check, checkout), we validate expected state (product grid, URL change, delivery options). If validation fails, the step is retried (up to 2 times) to reduce non-determinism from timing/race conditions. |
| **Deterministic waits** | After `goto`: `wait_for_load_state("networkidle")` (with timeout) + short settle time. After `click`: `wait_for_load_state("domcontentloaded")`. Reduces race conditions on dynamic sites (AEM, React, lazy loading). |

### Foundation fixes (production-grade, Week 0)

- **Async Playwright:** All Playwright async APIs (e.g. `locator.count()`) are awaited in SelectorValidator and executor to avoid false negatives and runtime warnings.
- **Deterministic wait policy:** Constants `NETWORK_IDLE_TIMEOUT_MS`, `GOTO_SETTLE_MS`, `AFTER_ACTION_DOM_TIMEOUT_MS`, `AFTER_ACTION_SETTLE_MS`; explicit `locator.wait_for(state='visible')` before click.
- **Screenshot directory:** `os.makedirs(screenshot_dir, exist_ok=True)` before every screenshot (async and sync); screenshots taken on every attempt including failed steps and in FlowEngine after each action.
- **Locator attempt order:** (1) locator_hint, (2) registry primary selector (SelectorRegistryService + UIElement), (3) step selector + alternatives; on failure healing uses semantic → fuzzy → locator_hint. Heals are persisted to registry; auto-promotion after 3 successes.
- **SelectorValidator unit tests:** `backend/tests/test_selector_validator.py` runs headless against `tests/fixtures/selector_validation_page.html` and asserts counts and matches.
- **Selector Registry:** `services.ui_automation.selector_registry.SelectorRegistryService` — get_primary_selector(host, intent), record_heal(host, intent, selector, source, confidence). Uses UIElement (app_key, intent, selectors JSON with success/failure counts). Auto-promote when success_count ≥ 3.
- **Planner:** Rule-based sanitization `_sanitize_plan()` — only allowed action types (navigate, goto, click, fill, type, select, press, wait, verify, comment); LLM cannot invent impossible steps.
- **Test Data Vault:** `services.ui_automation.test_data_vault` — get_environment(), use_mock_payment(), get_synthetic_address(), get_test_account(app_key). Env: UI_AUTOMATION_STAGING, UI_AUTOMATION_MOCK_PAYMENT, UI_TEST_*.
- **Sandbox / mock payment:** `config.app_config.use_staging()`, `use_mock_payment_endpoint()`; per-app `use_staging`, `mock_payment_endpoint` in APP_CONFIGS.
- **Safety limits:** MAX_TOTAL_STEPS=100, GLOBAL_TIMEOUT_MS=10min in EnhancedExecutor; fatal failure captures DOM to `fatal_step_N.html`.
- **Observability (POC, no Grafana):** Structured logging (step_id, run_id, healed) in executor; in-memory metrics updated on every run. **GET /ui/metrics** returns KPIs (runs_total, runs_passed, pass_rate_pct, steps_healed, steps_failed) for a simple dashboard. **POST /ui/smoke-check** runs selector validation on one URL or test case and returns pass/fail (CI-style without Celery). **POST /ui/heals/approve** approves a pending heal (app_key, intent, selector) so it is treated as promoted.
- **Batch revalidation:** `services.ui_automation.batch_revalidate.batch_revalidate_top_flaky(limit, db)` / `batch_revalidate_top_flaky_async` for nightly re-run of top-N tests.
- **Human-in-the-loop:** GET `/ui/heals/pending` returns low-confidence heals (confidence < 0.8 or success_count < 3) for approval.

---

## 2. End-to-End Flow

```
User input (raw text)
        │
        ▼
┌───────────────────┐
│  1. PLAN           │  PlannerAgent: parse scenario → structured plan (url + steps with action, element, description)
│  (PlannerAgent)    │  Optional: inject cookie_accept step after navigate (from app_config).
│                    │  Add intents & locator_hint to each step (intent taxonomy).
└─────────┬─────────┘
          │  structured_plan = { "url": "...", "steps": [ { "action", "element", "description", "intent", "locator_hint", "selector", ... } ] }
          ▼
┌───────────────────┐
│  2. LOAD DATA     │  Optional: load synthetic data by run_id for parameterized tests.
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  3. GENERATE      │  GeneratorAgent: plan + app_config → Playwright script (JS/TS). Used for logs/reference.
│  (GeneratorAgent) │  App config supplies selectors per intent for the plan’s URL.
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  4. VALIDATE      │  ValidatorAgent: structural validation of the plan.
│  (ValidatorAgent) │
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  5a. PRE-VALIDATE │  SelectorValidator: open URL, run steps in order; for each step check selector (and locator_hint)
│  (SelectorValidator)│  on current page; auto-fix with fuzzy match or Playwright role/placeholder; execute step to advance page.
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  5b. BUILD        │  Router builds enhanced_script from structured_plan:
│  enhanced_script  │  • starting_url, steps = [ goto(url), ... ] (navigate steps from plan are skipped; one goto prepended).
│                    │  • For each non-navigate step: action (click/fill/…), selector (from plan or app_config), alternatives, intent, locator_hint.
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  6. EXECUTE       │  For LG (use_flow_engine): FlowEngine (goal-driven loop, goal matching, no page-type transitions).
│  (FlowEngine or   │  Else: EnhancedExecutor (step-based). Per step: semantic actions → locator_hint → selector → alternatives.
│   EnhancedExecutor)│  Post-step validation; retry on invalid state; heal on failure. Deterministic waits.
│                    │  Screenshots per step; run status tracked for UI.
└─────────┬─────────┘
          ▼
     Result (passed / failed), execution_id, step_screenshots, logs
```

---

## 3. Main Components

### 3.1 Planner (`PlannerAgent`)

- **Input:** Raw test case string.
- **Output:** `structured_plan`: `{ "url": "...", "steps": [ { "step", "action", "element", "description", "value?", ... } ] }`.
- **Behavior:**
  - Parses scenario (and optionally uses LLM) into atomic steps: navigate, click, type, select, wait.
  - If `app_config` for the extracted URL has `inject_cookie_step_after_navigate: true`, inserts a **cookie_accept** step after the first navigate.
  - **Intent enrichment:** For each step, sets `intent` (e.g. `search_icon`, `cookie_accept`, `search_box`, `pincode_zip`), `locator_hint`, `selector_hints`, `selector` from intent taxonomy.

**Example step after planning:**

```json
{
  "step": 2,
  "action": "click",
  "element": "Accept cookie consent",
  "description": "Accept cookie consent banner (injected for this application)",
  "intent": "cookie_accept",
  "locator_hint": { "role": "button", "name": "Accept all" },
  "selector": "[role='button']:has-text('Accept all')"
}
```

### 3.2 Intent taxonomy (`intent.py` + `app_config.py`)

- **Intent:** Semantic label for what the step does (e.g. `search_icon`, `search_box`, `cookie_accept`, `pincode_zip`, `checkout`, `guest_checkout`).
- **locator_hint:** Prefer Playwright role/placeholder/label (e.g. `get_by_role("button", name="Accept all")`, `get_by_placeholder("Pincode")`). Executor tries these **before** CSS selectors.
- **app_config:** Per host (e.g. `lg.com`) defines lists like `cookie_accept_selectors`, `search_icon_selectors`, `search_box_selectors`, etc. Router and generator use these to fill **selector** and **alternatives** for each intent.

### 3.3 Generator (`GeneratorAgent`)

- **Input:** Structured plan, optional synthetic data, language (JS/TS), optional `app_config`.
- **Output:** Playwright script (string) for documentation and traceability. Execution does **not** run this script directly; it runs the **enhanced_script** built in the router.

### 3.4 Selector validator (`SelectorValidator`)

- **Input:** URL + list of steps (with selector, action, value, optional locator_hint).
- **Behavior:** Step-through validation: goto URL, then for each step check selector (and locator_hint) on current page; optionally auto-fix; then **execute** the step to advance the page so the next step is validated in the right state.
- **Output:** Validation result (valid/invalid counts, auto-fixed selectors). Fixed steps can be used later; the executor still uses the enhanced_script built from the **plan**, not from the validator output (unless you wire validated steps back in).

### 3.5 Router (build enhanced_script)

- **Input:** `structured_plan`, `url` from plan.
- **Logic:**
  - Append one **goto** step with `url` (skip plan steps whose `action` is navigate/goto).
  - For every other step: take `intent`, `selector`, `value`; get `app_selectors = get_selectors_for_intent(cfg, intent)`; set `action` to click/fill/select/press/wait as appropriate; set `selector` and `alternatives` from plan + app_config; set `locator_hint` from step or `get_locator_hint_for_intent(intent)`.
- **Output:** `enhanced_script = { "starting_url", "steps": [ { "action", "selector", "value", "alternatives", "intent", "locator_hint?" } ] }`.

### 3.6 Executor (`EnhancedExecutor`)

- **Input:** `enhanced_script`.
- **Per step:**
  1. **Semantic actions:** For `select_product_with_condition` (e.g. “Buy Now for product under 30000”), extract page model, filter product cards by `price_max`, click via page-model selectors, **get_by_role** (button/link), or fallback locators. Uses `scroll_into_view_if_needed`; tries multiple Buy Now buttons (first 5) if the first fails.
  2. **locator_hint** (if present): try `get_by_role` / `get_by_placeholder` / `get_by_label` and perform action.
  3. Else try **selector** then **alternatives** (wait for visible, click/fill, etc.).
  4. **Post-step validation:** After key transitions (search submit, buy/add-to-cart, pincode check, checkout), validate expected state. If invalid, retry the step (up to 2 times).
  5. On failure: **heal** — for `select_product_with_condition`, retry semantic action first; else fuzzy-match a new selector; if that fails, try **locator_hint** again.
- **Deterministic waits:** After `goto`: `networkidle` (or timeout) + settle. After `click`: `domcontentloaded` + brief wait.
- **Output:** `ExecutionResult` (success, steps_executed, steps_healed, screenshots, error).

### 3.7 Flow Engine (Goal-Driven) — LG & Dynamic Apps

For LG India and similar e-commerce sites, execution can use the **Flow Engine** instead of the step-based executor. The Flow Engine is a goal-driven autonomous loop:

```
while not goal_completed:
    world = extract_page_model(page)
    action = decide_next_action(goal, world, state)
    if action is None: raise DeadEndError()
    await execute(action)
    validate_transition()
    update_session_state(world)
    if no_progress_for_3_loops: re-evaluate
```

**Key components:**

| Component | Role |
|-----------|------|
| **Goal Extractor** | Converts raw test case / plan → `GoalObject` (search_query, price_max, checkout_mode, complete_purchase, pincode). No steps, no selectors. |
| **Page Intelligence** | Extracts rich world model: product_cards, search_bar, cart, visible_buttons, visible_inputs, modals, address_form. |
| **Decision Engine** | Goal matching: if `goal.search_query` and no search yet and search box visible → perform search; if product_cards and not selected → select product; etc. No hardcoded page_type transitions. |
| **Session State** | Tracks has_searched, product_selected, checkout_started, guest_selected, address_filled. |
| **Validator** | After every action: URL change? DOM change? Cart increase? Retry or re-plan if no progress. |

**Architecture:** `goal_extractor.py` → `GoalObject` → `FlowEngine` → `PageModel` (world) → `DecisionEngine.decide(goal, world, state)` → semantic action → component executes. Validation is mandatory after every action. `DeadEndError` raised when stuck for 3+ iterations.

### 3.8 Healer (`HealerAgent`)

- Used by the executor: given failed selector and current page elements (tag, text, id, name, etc.), returns a **healed selector** (e.g. by fuzzy text match). Sync API (`_fuzzy_match_from_page_elements`); executor must not `await` it.

---

## 4. API Endpoints (main flow)

| Method | Endpoint | Purpose |
|--------|----------|--------|
| **POST** | `/ui/run` | **Full run:** plan → generate → validate → pre-validate selectors → build enhanced_script → execute. Request body: `raw_input`, optional `page_url` / `feature_description`, `visible_browser`, `use_synthetic_data`, `synthetic_run_id`, `chat_id`. |
| **GET** | `/ui/current-run/status` | Returns `{ "running", "stage", "test_case_id" }` for progress (e.g. plan → generate → execute). Frontend polls this; access logs are suppressed to keep execution logs readable. |
| **GET** | `/ui/current-run/live-screenshot` | Returns latest step screenshot for the current run. |
| **POST** | `/ui/plan` | Plan only: raw_input → structured_plan (no execution). |
| **POST** | `/ui/generate` | Generate only: test_plan / test_case_id → Playwright script. |
| **POST** | `/ui/execute` | Execute a stored script (legacy path; full flow uses EnhancedExecutor via `/ui/run`). |

---

## 5. Example: LG India End-to-End

### 5.1 User input (raw)

```text
Navigate to https://www.lg.com/in. Click on search option, search for "lg 108cm tv". Click Buy Now for a product under 30000. Enter pincode 500032 and click Check. Click Checkout, then Continue as guest. Fill billing/shipping address.
```

### 5.2 What the planner produces (conceptually)

- **URL:** `https://www.lg.com/in`
- **Steps (simplified):**
  1. **navigate** to URL  
  2. **click** – Accept cookie consent (injected; intent `cookie_accept`)  
  3. **click** – Search option (intent `search_icon`)  
  4. **type** – "lg 108cm tv" in search (intent `search_box`)  
  5. **click** – Search submit (intent `search_submit`)  
  6. **click** – Buy Now for product under 30000 (intent `add_to_cart` / `product_select`)  
  7. **type** – 500032 in pincode (intent `pincode_zip`)  
  8. **click** – Check (intent `pincode_check`)  
  9. **click** – Checkout (intent `checkout`)  
  10. **click** – Continue as guest (intent `guest_checkout`)  
  11. **type** – address fields (intent `billing_shipping`)

Each step gets an **intent** and a **locator_hint** from the taxonomy; **selector** and **alternatives** come from plan + `app_config` for `lg.com`.

### 5.3 What the router builds (enhanced_script)

- **Step 0:** `action: "goto", value: "https://www.lg.com/in"`.
- **Step 1:** `action: "click", intent: "cookie_accept", selector: "[role='button']:has-text('Accept all')", alternatives: [ ... ], locator_hint: { "role": "button", "name": "Accept all" }`.
- **Step 2:** `action: "click", intent: "search_icon", selector: "a:has-text('Search')", alternatives: [ ... ], locator_hint: { "role": "link", "name": "Search" }`.
- **Step 3:** `action: "fill", intent: "search_box", selector: "input[type='search']", value: "lg 108cm tv", ...`.
- … and so on for each step.

### 5.4 Execution behavior

1. **Goto** LG India URL (with `networkidle` wait + settle time).
2. **Cookie:** Try locator_hint (get_by_role(button, name=Accept all)); else try selector and alternatives; on failure, heal (fuzzy match or locator_hint again).
3. **Search icon:** Try locator_hint (get_by_role(link, name=Search)); else selectors from app_config.
4. **Search box:** Try locator_hint (searchbox) or placeholder; else input selectors.
5. **Search submit:** Post-step validation checks product grid or URL; retries up to 2 times if invalid.
6. **Buy Now (select_product_with_condition):** Extract page model, filter by price; try page-model selectors, get_by_role(button, name="Buy Now"), multiple Buy Now buttons with scroll_into_view; on failure, heal with semantic retry first.
7. Same pattern for pincode, Check (with pincode validation), Checkout (with checkout validation), Continue as guest, billing.

Screenshots are saved per step under `backend/test_outputs/run_{test_case_id}/step_screenshots/`.

### 5.5 How to run this example

**From UI (recommended):**  
Use the chat/UI that calls `POST /ui/run` with the same raw input above (and optional `visible_browser: true` to watch the browser).

**cURL:**

```bash
curl -X POST "http://localhost:8002/ui/run" \
  -H "Content-Type: application/json" \
  -d '{
    "raw_input": "Navigate to https://www.lg.com/in. Click on search option, search for lg 108cm tv. Click Buy Now for a product under 30000. Enter pincode 500032 and click Check. Click Checkout, then Continue as guest. Fill billing/shipping address.",
    "visible_browser": true
  }'
```

(Replace port if your backend uses another one.)

**Response (success case):**

```json
{
  "execution_id": 42,
  "test_case_id": 123,
  "status": "passed",
  "plan": { "url": "https://www.lg.com/in", "steps": [ ... ] },
  "script": { "language": "javascript", "content": "..." },
  "healed": false,
  "steps_healed": 0
}
```

---

## 6. Configuration: Adding a New App (e.g. another site)

1. **Intent taxonomy (`backend/services/ui_automation/intent.py`):**  
   Add or reuse intents and their `locator_hint` and `selector_hints` so the planner can attach the right semantics.

2. **App config (`backend/config/app_config.py`):**
   - Add a host key (e.g. `"example.com"`) under `APP_CONFIGS`.
   - Set `base_url`, `inject_cookie_step_after_navigate` if needed.
   - For each intent you care about, add a list, e.g. `cookie_accept_selectors`, `search_icon_selectors`, `search_box_selectors`, … (see `INTENT_TO_SELECTORS_KEY`).

3. **Planner:**  
   No code change needed; it uses URL to resolve `app_config` and injects cookie step when the config says so. Intents and locator hints come from the taxonomy.

4. **Router:**  
   Already uses `get_app_config_for_url(url)` and `get_selectors_for_intent(cfg, intent)` to build selector and alternatives; no change needed for a new app if the intents exist.

---

## 7. File Reference (backend)

| Path | Role |
|------|------|
| `routers/ui_automation.py` | Entry: `/ui/run`, plan → generate → validate → pre-validate → build enhanced_script → execute. |
| `config/app_config.py` | **Fallback only:** per-host selector lists, cookie inject; core logic is page intelligence + semantic actions. |
| `services/ui_automation/intent.py` | Intent taxonomy; `classify_intent`, `get_locator_hint_for_intent`; includes `select_product_with_condition`. |
| `services/ui_automation/agents/planner/agent.py` | PlannerAgent; cookie injection; intent + **condition** (e.g. price_max) for semantic actions. |
| `services/ui_automation/page_intelligence/` | **Page Intelligence Engine:** `extract_page_model_async`/`_sync`, PageModel (product_cards, search_bar, cart), page_type. |
| `services/ui_automation/state_manager.py` | **State Manager:** SessionState (current_url, page_type, cart_count, checkout_stage, last_action). |
| `services/ui_automation/engine/enhanced_executor.py` | Runs enhanced_script; **conditional** `select_product_with_condition` (get_by_role, scroll, multiple fallbacks); state + post-step validation with retry; deterministic waits; locator_hint → selector → healing (semantic retry first). |
| `services/ui_automation/agents/healer/agent.py` | Fuzzy match from page elements → healed selector. |
| `services/ui_automation/utils/selector_validator.py` | Step-through selector validation and auto-fix. |
| `services/ui_automation/agents/generator/agent.py` | GeneratorAgent; plan → Playwright script. |
| `run_uvicorn.py` | Custom uvicorn runner; `SkipRunStatusAccessFilter` suppresses `/ui/current-run/status` access logs. |
| `services/ui_automation/flow_engine.py` | **Flow Engine:** state-machine loop; detect → decide → execute → validate. |
| `services/ui_automation/decision_engine.py` | Goal + page_type → NextAction. |
| `services/ui_automation/components/` | Component API: HomePage, SearchResults, CartPage, CheckoutPage. |

---

## 8. Enterprise architecture (state-aware + component-aware + conditional + deterministic)

The pipeline extends to support **thousands of scenarios** with:

1. **Scenario compiler (planner)** – Emits semantic actions and **conditions** (e.g. “Buy Now for product **under 30000**” → `select_product_with_condition` with `condition: { "price_max": 30000 }`).
2. **Page Intelligence Engine** – Before/after steps: `extract_page_model(page)` → `PageModel` (page_type, product_cards with price/buy_button_selector, search_bar, cart). Used for conditional execution and validation.
3. **State Manager** – `SessionState` tracks current_url, page_type, cart_count, checkout_stage, last_action. Updated after steps; used by validation and future page-type–driven dispatch.
4. **Conditional execution** – For `select_product_with_condition`, the executor extracts the page model, filters `product_cards` by `price <= condition.price_max`, and clicks the first match’s buy button. Uses **get_by_role**, **scroll_into_view_if_needed**, and tries multiple Buy Now buttons (first 5) if the initial click fails.
5. **Validation engine** – After key steps, `_validate_after_step_async` returns `(valid, should_retry)`. Validates: **search submit** (product grid or URL); **buy/add-to-cart** (URL change or expected page type); **pincode check** (delivery text); **checkout** (URL or checkout visible). If invalid, the step is retried up to 2 times before failing.
6. **Deterministic waits** – After `goto`: `wait_for_load_state("networkidle", timeout=10s)`; after `click`: `wait_for_load_state("domcontentloaded")`. Reduces race conditions on dynamic sites (AEM, React, lazy loading).
7. **Healing enhancements** – For `select_product_with_condition`, healing retries the full semantic action first (page model + get_by_role + multiple fallbacks) before fuzzy matching.
8. **App config as fallback** – Cookie injection and edge selectors only; core flow is driven by page model + semantic actions.
9. **Logging** – Run status polling (`/ui/current-run/status`) and run_status phase logs are suppressed so execution steps remain readable in logs.

**Learning layer (optional):** Failed/successful selectors and page fingerprints can be persisted and reused; hooks are left for future implementation.

---

## 9. Flow Engine (State-Machine Architecture)

For LG and similar e-commerce domains, the system supports a **state-machine flow engine** instead of linear step execution.

### 9.1 Architecture

```
User Scenario
      ↓
Scenario Compiler (Goal + Constraints)
      ↓
Flow Engine (state machine)
      ↓
Page Intelligence (detect page_type via DOM fingerprinting)
      ↓
Decision Engine (what to do next from page_type)
      ↓
Component API (domain logic: cart_page.proceed_to_checkout())
      ↓
Playwright (low-level)
      ↓
State Update
```

### 9.2 Enable Flow Engine

- **Per request:** `POST /ui/run` with `"use_flow_engine": true`
- **Per app:** In `app_config.py`, set `"use_flow_engine": True` for the host (e.g. LG India has this enabled by default)

### 9.3 Components

| Component | Role |
|-----------|------|
| `flow_engine.py` | Core loop: detect → decide → execute → validate → update |
| `decision_engine.py` | Goal + page_type → NextAction (e.g. if CART → proceed_to_checkout) |
| `components/` | Domain APIs: HomePageComponent, SearchResultsComponent, CartPageComponent, CheckoutPageComponent |
| `page_intelligence/` | DOM fingerprinting: page_type from components (DELIVERY_CHECK, ADDRESS_FORM, etc.) |
| `state_manager.py` | Full session: product_selected, delivery_selected, action_history |

### 9.4 Flow vs Step-Based

| Step-based | Flow Engine |
|------------|-------------|
| Linear for-loop | while not goal_reached |
| Assumes next step valid | Decides from current page_type |
| Retry on selector failure | State correction, alternative flow branch |
| Healing = fuzzy match | Healing = re-detect page, recompute decision |

---

## 10. Summary

- **Approach:** Natural language → structured plan with intents and locator hints → app-specific selectors from config → enhanced script → execution with layered locators and healing. For LG: Flow Engine (state-machine) is enabled by default.
- **End-to-end:** Plan → (optional synthetic data) → generate script → validate plan → pre-validate selectors (step-through) → build enhanced_script → execute (EnhancedExecutor) → result and screenshots.
- **Examples:** LG India is the main documented flow; the same pipeline applies to any site by adding host config and reusing or extending the intent taxonomy.
- **Enterprise:** State-aware + component-aware + conditional + deterministic execution (Page Intelligence, SessionState, select_product_with_condition, post-step validation with retry, deterministic waits, healing enhancements); app_config is fallback-only. Run status logs suppressed for readability.
