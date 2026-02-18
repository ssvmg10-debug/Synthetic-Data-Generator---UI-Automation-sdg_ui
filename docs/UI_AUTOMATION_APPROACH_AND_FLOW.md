# UI Automation — Approach, End-to-End Flow & Boilerplate

This document describes the **Enhanced Deterministic System V2** approach: inputs, all logic in between, outputs, real-time examples, and boilerplate code snippets for each major file.

**Latest approach (pin-to-pin):**  
**No blind success** — post-state is validated after every step; on mismatch (after one retry) the **step fails** and the test stops. **No wrong clicks** — Smart Resolver uses word overlap for category/product links, a blocklist for generic nav (Shop, Promotions, etc.), and semantic floors (0.35 links, 0.4 e-commerce buttons). **4-phase resolution** — Phase 0 (execution memory cache) → Phase 1 (element resolver) → Phase 2 (smart resolver with strict matching) → recovery → Phase 3 (visual grounding: vision or text) → Phase 4 (healing agent). **Stability & popups** — stabilize before run, contextual router before steps, popup classifier or interrupt handler after steps. **Selector cache** only when post-action validation passes.

## Production-Grade Architecture (Stable + Intelligent)

**Deterministic First, Adaptive Second.** Healing agent is a **rare escalation layer** (<5% execution path), not the default fallback.

```
Input
  ↓
Semantic DSL
  ↓
Intent Classifier (CATEGORY, PRODUCT, PRIMARY_CTA, CHECKOUT_CTA, AUTH_CTA, OPTION)
  ↓
Candidate Graph Builder (id, text, role, tag, visible, bounding_box, parent_container, …)
  ↓
Deterministic Weighted Scorer
  final_score = semantic_similarity*0.45 + word_overlap*0.20 + role*0.10 + container*0.10 + visual_position*0.05 + primary_button*0.10
  Intent-specific thresholds: CATEGORY 0.35, PRODUCT 0.40, PRIMARY_CTA 0.45, CHECKOUT 0.50
  ↓
Action Executor (single best candidate — no second click, no randomness)
  ↓
Intent-Based Validator (CATEGORY→product grid; PRODUCT→H1+price; BUY_NOW→cart/checkout; CHECKOUT→billing; GUEST→email; OPTION→radio)
  ↓
Adaptive fallbacks (controlled): Reranking → Container restriction → Coordinate click → DOM traversal
  ↓
(rare) Healing Agent
```

- **Resolution Decision Engine** (`resolution_decision_engine.py`): Build candidate graph → classify intent → weighted score → confidence rule → single click; fallbacks: contextual rerank, container restriction, coordinate click, DOM traversal.
- **Semantic State Engine** (`semantic_state_engine.py`): State from DOM signals (e.g. CATEGORY = 5+ product cards + filter/breadcrumb/pagination; PRODUCT = H1 + price + Buy Now; CHECKOUT = billing + payment + place order).
- **Wait strategy** (`wait_strategy.py`): `networkidle` → `readyState === 'complete'` → 600ms (no random timing).
- **Execution memory v2**: Cache key `(url, intent_type, normalized_target)`; store selector, dom_path, bounding_box, container_info; cache only after validation success.

## Enterprise architecture (implemented)

- **Input** → **Semantic Parser** → **Normalized DSL**
- **Deterministic Executor** (state-driven: pre-state check → execute → post-state check)
- **Perception + Resolution stack**: Phase 0 (execution memory cache) → Phase 1 (DOM resolver) → Phase 2 (smart fuzzy + cache) → recovery (flow handlers + retry) → Phase 3 (visual grounding) → Phase 4 (LLM healing)
- **Post-action validation** (strict: Buy Now → cart/checkout; TYPE → value; SELECT_OPTION → radio)
- **Flow handlers + interrupts** (popup classifier: login/delivery/consent/payment; contextual router before step)
- **Stability engine** (before run: clear storage, disable animations, network idle, scroll, dismiss; after step: force_layout_stabilization)
- **Execution memory** (state transitions; selector cache populated only when post-action validation passes)
- **Weighted selector scoring (Module 8)**: `score = semantic*0.5 + role*0.2 + visibility*0.1 + position*0.1 + container*0.1`; pick highest; container = main vs footer.
- **Strict post-state validation (Module 2)**: after step, if `expected_state` set, validate; on mismatch retry once (flow handlers + wait); if still mismatch, **fail the step** (no blind success — applies to all expected states, not only critical).
- **Strict link/button matching (no wrong clicks)**: Smart resolver requires **word overlap** for category/product links (e.g. "split air conditioners" must share a word with link text — rejects "Promotions"); **generic nav blocklist** (Shop, Promotions, Support, etc.) when target is category/product/CTA; **semantic floor** (links ≥ 0.35, e-commerce buttons ≥ 0.4); **buy now / buynow** aliases so "Buy Now" button matches.
- **No CLICK fallback** for unparseable steps (StepType.UNKNOWN → fail explicitly).

### Claude-like capabilities — what is actually implemented

| Capability | Status | How it’s done |
|------------|--------|----------------|
| **Visual understanding** | ✅ Implemented | **Vision path:** When `USE_VISION_GROUNDING=true`, Phase 3 visual grounding captures a **screenshot**, sends it with element list to the vision model (e.g. gpt-4o). Model sees the UI and returns index or (x,y). **Text path:** Element list (index, text, role) sent to LLM when vision is off or fails. |
| **Visual UI adaptability** | ✅ Implemented | Same vision path: model sees layout and semantics, picks best element; optional coordinates make clicks layout-driven. Bbox center fallback in `click_by_visual_result` is selector-independent. |
| **Dynamic UI handling** | ✅ Implemented | Flow handlers + interrupt handler + popup classifier (DOM text) + contextual action router; stability engine (animations off, scroll, dismiss). Recovery + retry on resolution/post-state. |
| **Popup reasoning** | ✅ Implemented (DOM) | `popup_classifier` infers type from DOM text (login/delivery/consent/payment/generic) and chooses dismiss strategy. Optional **visual** popup classification (screenshot → vision) is not implemented. |
| **Selector independence** | ✅ Implemented | Vision can return **(x, y)** → `click_by_coordinates(page, x, y)` (no selector). Else click by **bbox center** from candidates. Else fallback to text/role. Execution memory caches selector only after validation pass. |

**To enable true visual grounding:** set `USE_VISION_GROUNDING=true` and ensure `AZURE_VISION_DEPLOYMENT` or `AZURE_DEPLOYMENT` points to a vision-capable model (e.g. gpt-4o). Vision is tried first; on failure we fall back to text-only element list.

---

## 1. Approach Overview

### 1.1 Design Principles

| Principle | Description |
|-----------|-------------|
| **Semantic parsing first** | Natural language or enterprise specs are converted to a **normalized JSON DSL** (TestCase + TestStep). No raw English reaches the executor. |
| **Assertions never click** | "Verify" / "Check" steps are **ASSERTION** type and go to the **Assertion Engine** only (inspect DOM/URL/title). They never perform click/type. |
| **Deterministic execution** | Actions use a fixed order of strategies; product selection uses scoring (no randomness). Selector caching ensures same element across runs. |
| **4-phase element resolution** | For CLICK/TYPE: Phase 0 (execution memory cache) → Phase 1 (Element Resolver) → Phase 2 (Smart Resolver, strict matching) → recovery (flow handlers + retry) → Phase 3 (Visual Grounding) → Phase 4 (Healing Agent). Same idea for TYPE with Phase 1 + Phase 2 (+ contenteditable/keyboard fallback). |
| **Site-specific flow handlers** | JSON flow configs (e.g. `lg_flow_config.json`) run at triggers like `after_pincode_check`, `before_select_delivery`, `before_checkout` to dismiss modals/popups. |
| **Interrupt handling** | Generic handler dismisses common blocking UI (OK, Continue, cookie banners) after key actions. |
| **State machine** | Page state (HOME, CATEGORY, PRODUCT_LIST, CART, CHECKOUT, etc.) is detected from URL/DOM and optionally validated for transitions. |

### 1.2 High-Level Flow

```
INPUT (Natural Language or Enterprise Spec)
    ↓
Semantic Parser → TestCase (id, title, steps: TestStep[])
    ↓
DeterministicExecutorV2.execute_test_case(test_case)
    ↓
For each step:
    • required_state? → detect_state(); if mismatch → FAIL
    • Route by step.type:
        - ASSERTION → AssertionEngine.execute_assertion(step)  [NO UI action]
        - ACTION / INPUT / NAVIGATION → _execute_action(step)
            - GOTO → page.goto(target)
            - CLICK/SELECT → Phase 0: memory cache → Phase 1: smart_click → Phase 2: smart_resolve_click → recovery → Phase 3: visual grounding → Phase 4: HealingAgent
            - FILL_PINCODE/TYPE → Phase 1: smart_type → Phase 2: smart_resolve_type
            - SELECT_OPTION → smart_select (+ flow handlers for delivery)
            - BUY_NOW/CHECKOUT/CONTINUE_AS_GUEST → mapped to CLICK target
        - WAIT → _execute_wait(step)
        - CONDITIONAL → _execute_conditional(step)
    • Post-step: run_flow_handlers(trigger) + handle_interrupts()
    • expected_state? → _wait_for_state_change(); on mismatch after retry → FAIL step (no blind success)
    • Save checkpoint
    ↓
OUTPUT: ExecutionResult (passed, executed_steps, total_steps, checkpoints, duration_ms, error?)
```

---

## 2. Input

### 2.1 API Entry (V2)

- **Endpoint:** `POST /ui-automation-v2/run`
- **Request body:** Either `natural_language` or `enterprise_spec`, plus optional `visible_browser`, `start_url`, `chat_id`.

**Option A — Natural language**

```json
{
  "natural_language": "Navigate to https://www.lg.com/in\nClick Air Solutions\nVerify page loaded\nSelect LG 5 Star (1.0) Split AC, AI Convertible 6-in-1\nClick Buy Now\nEnter pincode 560001 and check\nSelect free delivery\nClick Checkout\nClick Continue as guest",
  "visible_browser": true,
  "start_url": null
}
```

**Option B — Enterprise spec**

```json
{
  "enterprise_spec": {
    "Test Case ID": "TC_LG_001",
    "Objective": "Verify product selection and checkout",
    "Preconditions": ["Browser ready"],
    "Test Data": {"pincode": "560001"},
    "Steps": [
      {"Step": "Navigate to https://www.lg.com/in", "Expected Result": "Homepage loaded"},
      {"Step": "Click Air Solutions", "Expected Result": "Category page displayed"},
      {"Step": "Select LG AC", "Expected Result": "Product detail page displayed"}
    ]
  },
  "visible_browser": false
}
```

### 2.2 Internal Model (After Parsing)

All execution works on the **normalized TestCase**:

- **TestCase:** `id`, `title`, `objective`, `preconditions`, `test_data`, `steps[]`
- **TestStep:** `id`, `type`, `intent`, `target`, `value`, `metadata`, `required_state`, `expected_state`, `max_retries`, `timeout`

**Step types:** `NAVIGATION`, `ACTION`, `INPUT`, `ASSERTION`, `WAIT`, `CONDITIONAL`  
**Intents (examples):** `GOTO`, `CLICK`, `SELECT`, `SEARCH`, `ADD_TO_CART`, `BUY_NOW`, `CHECKOUT`, `CONTINUE_AS_GUEST`, `TYPE`, `FILL_PINCODE`, `SELECT_OPTION`, `PAGE_LOADED`, `ELEMENT_VISIBLE`, `TEXT_CONTAINS`, `URL_MATCHES`, etc.

---

## 3. Logic In Between

### 3.1 Semantic Parser (`semantic_parser.py`)

- **Input:** Raw string (natural language) or dict (enterprise spec).
- **Output:** `TestCase` with list of `TestStep`.
- **Rules (summary):**
  - Newline or comma splits steps; product lines (long text with “this product”/brand + commas) are kept as one step.
  - “Navigate to …” → `NAVIGATION` + `GOTO` + `target=url`.
  - “Verify/Check …” (and not “click on check”) → `ASSERTION` via `_parse_assertion()`.
  - “Click …” / “Select …” → `ACTION` + `CLICK` or `SELECT`; product-like steps get `metadata.is_product` and optional `required_state`/`expected_state`.
  - “Wait for N seconds” → `WAIT` with `metadata.duration_ms`.
  - Pincode/ZIP → `INPUT` + `FILL_PINCODE`; “Select free delivery” → `SELECT_OPTION`; “Search for X” → `SEARCH`; “Buy now” / “Checkout” / “Continue as guest” → corresponding intents with fixed targets.
- **Enterprise:** Each `Steps` item has “Step” (action) and “Expected Result” (parsed as assertion step after the action).

### 3.2 Enhanced Deterministic Executor (`enhanced_deterministic_executor.py`)

- **execute_natural_language(text, start_url)** → `SemanticTestParser.parse_natural_language()` → `execute_test_case()`.
- **execute_enterprise_format(spec)** → `SemanticTestParser.parse_enterprise_format()` → `execute_test_case()`.
- **execute_test_case(test_case):**
  - Builds `test_context` for healing/logger.
  - Resets environment (localStorage/cookies clear in try/except; no reload on about:blank); then **stabilize_before_run** (stability engine).
  - For each step:
    - **Pre-condition:** If `required_state` is set, `_detect_current_state()` must match; else return failed `ExecutionResult`.
    - **Routing:**
      - **ASSERTION** → `_execute_assertion(step)` → `AssertionEngine.execute_assertion(step)` (read-only).
      - **ACTION / INPUT / NAVIGATION** → `_execute_action(step)` (see below).
      - **WAIT** → `_execute_wait(step)` (from `metadata.duration_ms` or step value).
      - **CONDITIONAL** → `_execute_conditional(step)`.
    - **Post-step:** `_post_step_stabilize()` (flow handlers + interrupt handler + domcontentloaded + short wait).
    - **Post-condition:** If `expected_state` is set, `_wait_for_state_change()`; on mismatch, retry once (flow handlers + wait); if still mismatch, **fail the step** and return `ExecutionResult(passed=False, failed_step, error)` — no blind success.
    - Checkpoint appended; `executed_count` incremented only on success.
  - On any step failure: return `ExecutionResult(passed=False, failed_step, error)`.
  - On success: return `ExecutionResult(passed=True, executed_steps, checkpoints, duration_ms)`.
  - **Before run:** Stability engine `stabilize_before_run` (clear storage, disable animations, network idle, scroll top, dismiss popups). **Before action steps:** Contextual action router `route_before_step` (popup classifier, guest/delivery routing). **After step:** Popup classifier or interrupt handler, then `force_layout_stabilization`.

**_execute_action (summary):**

- **GOTO:** `page.goto(target)`, then wait for load.
- **CLICK / SELECT:**
  - If product step (`metadata.is_product`) and `SELECT`: try `IntentDispatcher.execute(SELECT_PRODUCT, {product_name}, page)` first.
  - Else: Phase 0 (execution memory cached selector) → Phase 1 `smart_click(page, target)` → Phase 2 `smart_resolve_click(page, target)` (returns `(bool, selector)` for cache-on-validation) → on failure, recovery (flow handlers + retry Phase 1/2) → Phase 3 Visual Grounding `resolve_visually` + `click_by_visual_result` → Phase 4 `HealingAgent.heal_click_failure` + `apply_healing_action`.
  - On success: store `_last_resolved_selector`; after **post-action validation** passes, save selector to execution memory. After major actions (buy/checkout/cart/add/product selection): run flow handlers, interrupt handler, wait for domcontentloaded/networkidle, short wait.
- **ADD_TO_CART / BUY_NOW / CHECKOUT / CONTINUE_AS_GUEST:** Mapped to CLICK with fixed target; CHECKOUT also runs `run_flow_handlers("before_checkout")`.
- **FILL_PINCODE / TYPE:** Phase 1 `smart_type(page, target, value)`; on failure Phase 2 `smart_resolve_type(page, target, value)`; optional fallback contenteditable/keyboard (e.g. for overlay inputs).
- **SELECT_OPTION:** Run flow handlers for delivery if target suggests delivery; then `smart_select(page, target)` with retry and optional healing.
- **SEARCH:** Wait for overlay, then focused input / contenteditable / global keyboard fallback (with existing helpers).
- **FILL_EMAIL / FILL_PHONE:** Direct fill on typical input selectors.

### 3.3 Element Resolver (`element_resolver.py`) — Phase 1

- **smart_click(page, label):** Tries multiple strategies in order: role button/link (exact then partial), get_by_text (exact then regex), locator text. When multiple matches, picks a visible one in viewport. Clicks first successful.
- **smart_type(page, label, value):** Expands keywords (e.g. pincode → pin, zip, postal). Tries get_by_label, placeholder, name, then visible inputs; fills and optionally blurs/tab.
- **smart_select(page, option):** Expands select keywords (e.g. free delivery → free shipping, standard, ₹0). Tries radio/label by text, then dropdown options; no healing.

### 3.4 Smart Resolver (`smart_resolver.py`) — Phase 2

- **smart_resolve_click(page, target):** Returns `(bool, Optional[str])` for cache-on-validation.
  - **Cache:** Check execution memory and file cache (hash of url + target); if hit and element clickable, click and return `(True, selector)`.
  - **Buttons:** Score with **weighted score** = semantic×0.5 + role×0.2 + visibility×0.1 + position×0.1 + container×0.1. **Semantic floor for e-commerce CTA:** `best_semantic >= 0.4` (avoids clicking "Shop" for "buy now"). Use **button aliases** (e.g. buy now, buynow → ["buy now", "add to cart", ...]).
  - **Links:** Same weighted scoring. **Strict rules:** (1) **Word overlap** — for category/product-like targets (e.g. "split air conditioners", "air solutions"), link text must contain at least one **word** from target (rejects "Promotions" for "split air conditioners"). (2) **Generic nav blocklist** — when target is category/product/CTA, skip links whose text is in blocklist: Shop, Promotions, Support, Contact, Careers, News, Blog, Sign in, Register, etc., unless link is an alias for target. (3) **Semantic floor** — `best_semantic >= 0.35` for any link candidate.
  - **Product cards:** If target is product selection, also score product card locators; try top candidates. Apply product-spec penalty for model mismatch (e.g. star rating, ton).
  - **Min confidence:** Per-target minimum (e.g. product selection 0.35, e-commerce CTA 0.4); if best combined score below threshold, return `(False, None)` so Phase 3/4 can run.
- **smart_resolve_type(page, target, value):** Cache + fuzzy match on placeholder/aria-label/name/id; focused input first; fallback for search/overlay inputs.
- **Selector cache:** File `selector_cache.json` (key = hash(url::target)); execution memory also caches selector only when **post-action validation** passes.

### 3.4a Visual Grounding Engine (`visual_grounding_engine.py`) — Phase 3

- **resolve_visually(page, target, intent, context):** Picks best element from visible clickables. **Vision path** (when `USE_VISION_GROUNDING=true`): capture screenshot, send image + element list to vision model (e.g. gpt-4o); model returns index or (x, y). **Text path:** Send list of (index, text, role) to LLM, get index. Returns `{index, text, element, coordinates?}` or None.
- **click_by_visual_result(page, visual_result):** (1) If `coordinates` (x, y) from vision → `click_by_coordinates(page, x, y)` (selector-independent). (2) Else if element has bbox → click bbox center. (3) Else click by text/role (button/link/get_by_text).
- **click_by_coordinates(page, x, y):** `page.mouse.click(x, y)` — no selector.
- **Env:** `USE_VISION_GROUNDING=true`, `AZURE_VISION_DEPLOYMENT` or `AZURE_DEPLOYMENT` (vision-capable model). Vision tried first; on failure fall back to text-only.

### 3.5 Healing Agent (`healing_agent.py`) — Phase 4

- **heal_click_failure(page, failed_target, previous_steps, test_context):** Collects visible button/link/text from page, adds semantic hints (e.g. guest checkout, free delivery). Sends to Azure OpenAI; expects JSON `{action, target}`.
- **apply_healing_action(page, action):** Interprets action (e.g. click by text) and performs it on the page.
- Only used when Phases 0–3 fail. Requires `AZURE_OPENAI_*` env vars.

### 3.6 Intent Dispatcher (`intent_dispatcher.py`)

- Used for **deterministic product selection** and other structured intents.
- **execute(intent, parameters, page):** Dispatches to handlers, e.g. `SELECT_PRODUCT` → `_handle_select_product` (keyword extraction, score all link/button/card text with `_similarity_score`, click best, validate state); `FILL_PINCODE` → find field by label/placeholder/name and fill; `SELECT_DELIVERY_OPTION`, guest checkout, etc.
- **valid_data_generator:** Used for pincode/email/phone when value not provided.

### 3.7 Assertion Engine (`assertion_engine.py`)

- **execute_assertion(step):** Dispatches by `step.intent` to methods that **only read** the page (no click/type):
  - **PAGE_LOADED:** body/title, no loader; optional context (home/category/detail/cart) for extra checks.
  - **ELEMENT_VISIBLE / ELEMENT_NOT_VISIBLE:** selector strategies then visibility check.
  - **TEXT_CONTAINS:** substring in page content.
  - **URL_MATCHES:** pattern in `page.url`.
  - **FILTER_APPLIED:** filter badges + product count.
  - **DELIVERY_OPTIONS_LOADED:** presence and visibility of delivery controls.
  - **BUTTON_ENABLED / BUTTON_DISABLED:** button by text + disabled/aria-disabled.
  - **ORDER_CONFIRMED:** keywords in content + optional order ID.
  - **ELEMENT_COUNT, PRODUCT_IN_CART, PRICE_VISIBLE:** self-explanatory read-only checks.
- Returns `AssertionResult(passed, message, actual, expected)`.

### 3.8 Flow Config Loader (`flow_config_loader.py`)

- **run_flow_handlers(page, trigger, url):** Resolves site from URL (e.g. lg.com → `lg`), loads `{site}_flow_config.json`, runs handlers whose `trigger` matches (e.g. `after_pincode_check`, `before_select_delivery`, `before_checkout`). Each handler has `actions`: `dismiss_modal` (button_texts), `run_interrupt_handler`, `wait` (ms). Dismissal tries role=button and get_by_text for given texts.

### 3.9 Interrupt Handler (`interrupt_handler.py`)

- **handle_interrupts(page, timeout_ms):** Finds modals/dialogs (role=dialog, .modal, etc.), then buttons with dismiss texts (OK, Continue, Close, Accept, Select delivery, etc.). Clicks to dismiss; also fallback full-page button search. Returns count of dismissed.

### 3.10 State Machine (`state_machine.py`)

- **detect_state(page):** URL-based rules first (e.g. /checkout → CHECKOUT, /cart → CART, /product/ → PRODUCT_DETAIL), then DOM-based (text/inputs for confirmation, payment, checkout, cart, product detail, list). HOME only for true base URL (e.g. path `/in` or origin); LG category paths (e.g. /air-conditioners, /split-ac) → CATEGORY before DOM checks.
- **validate_state_transition(page, expected_state, retry_on_mismatch):** Optional strict validation after actions (used by intent dispatcher for product/cart).

### 3.11 Stability Engine (`stability_engine.py`)

- **stabilize_before_run(page):** Run once after environment reset: clear cookies/storage (try/except, no reload on about:blank), disable animations via JS, wait for network idle, scroll to top, dismiss popups. Used by executor before first step.
- **force_layout_stabilization(page, timeout_ms):** After key steps: short wait, optional scroll, to reduce flakiness from layout shifts.

### 3.12 Action Validator (`action_validator.py`)

- **validate_action(page, step, success):** Post-action checks: e.g. after Buy Now → cart/checkout visible; after TYPE → value in field; after SELECT_OPTION → radio selected or option present. Used by executor after successful action; on pass, selector can be saved to execution memory.

### 3.13 Popup Classifier (`popup_classifier.py`)

- Classifies popup from **DOM text** (login, delivery, consent, payment, generic). Type-specific dismiss buttons (e.g. guest checkout → "Continue as guest", generic → "close", "OK").
- **handle_interrupts_classified(page, timeout_ms, current_step_guest_checkout):** Dismiss using classified strategy. Used in `_post_step_stabilize` when step is guest checkout; else fallback to generic interrupt handler.

### 3.14 Contextual Action Router (`contextual_action_router.py`)

- **route_before_step(page, step):** Before each action step, detect visible popup (popup classifier); route e.g. login + guest step → click guest button; delivery popup → flow handler + dismiss. Ensures blocking UI is handled before attempting the step.

### 3.15 Execution Memory (`execution_memory.py`)

- Persists state transitions and **selector cache**. **get_cached_selector(url, target, intent)** used in Phase 0; **set_cached_selector** called only when **post-action validation passes** (no cache on wrong click). Reduces flakiness and avoids re-resolving known-good selectors.

---

## 4. Output

### 4.1 API Response (V2)

**Success (200):**

```json
{
  "test_id": "auto_generated",
  "passed": true,
  "total_steps": 12,
  "executed_steps": 12,
  "failed_step": null,
  "error": null,
  "duration_ms": 45000,
  "assertion_count": 2,
  "action_count": 10,
  "checkpoints": [
    {
      "step_id": 1,
      "step_description": "GOTO",
      "state": "home",
      "timestamp": "2025-02-18T10:00:01",
      "success": true,
      "error": null
    }
  ],
  "plan": {
    "test_id": "auto_generated",
    "title": "Navigate to https://www.lg.com/in...",
    "steps": [
      {"step": 1, "type": "navigation", "intent": "GOTO", "description": "Navigate to page"},
      {"step": 2, "type": "action", "intent": "CLICK", "description": "Click Air Solutions"}
    ]
  },
  "script": "# Enhanced Deterministic System V2 Test Script\n..."
}
```

**Failure (200 with passed: false):**

```json
{
  "test_id": "auto_generated",
  "passed": false,
  "total_steps": 12,
  "executed_steps": 5,
  "failed_step": 6,
  "error": "Post-state validation failed: expected CATEGORY, got HOME. Step reported success but page state did not match.",
  "duration_ms": 18000,
  "checkpoints": [...],
  "plan": {...},
  "script": "..."
}
```

Other failure examples: `"All 4 phases failed for click: 'free delivery'"`, `"Failed to type into: 'pincode'"`.

### 4.2 ExecutionResult (internal)

- `test_id`, `passed`, `total_steps`, `executed_steps`, `failed_step`, `error`, `checkpoints[]`, `duration_ms`.
- Checkpoint: `step_id`, `step_description`, `state`, `timestamp`, `success`, `error`.

---

## 5. Real-Time Examples

### Example 1: Natural language → parsed steps → execution

**Input:**

```text
Navigate to https://www.lg.com/in
Click Air Solutions
Verify page loaded
Select LG 5 Star (1.0) Split AC, AI Convertible 6-in-1 Cooling
Click Buy Now
Enter pincode 560001 and check
Select free delivery
Click Checkout
```

**Parsed steps (conceptual):**

1. NAVIGATION GOTO target=https://www.lg.com/in  
2. ACTION CLICK target=Air Solutions, expected_state=CATEGORY  
3. ASSERTION PAGE_LOADED value=page  
4. ACTION SELECT target=LG 5 Star (1.0) Split AC..., metadata.is_product=true, required_state=PRODUCT_LIST, expected_state=PRODUCT_DETAIL  
5. ACTION BUY_NOW → CLICK target=buy now  
6. INPUT FILL_PINCODE target=pincode value=560001 (+ flow trigger after_pincode_check)  
7. ACTION SELECT_OPTION target=free delivery (+ flow trigger before_select_delivery)  
8. ACTION CHECKOUT → flow before_checkout + CLICK target=checkout  

**Execution:** Each step runs through the routing above; assertions only inspect; actions use 3-phase resolution and flow handlers where configured.

### Example 2: Enterprise spec with expected results

**Input:**

```json
{
  "Test Case ID": "TC_LG_001",
  "Steps": [
    {"Step": "Navigate to https://www.lg.com/in", "Expected Result": "Homepage loaded"},
    {"Step": "Click Air Solutions", "Expected Result": "Category displayed"}
  ]
}
```

**Parsed steps:**  
1. NAVIGATION GOTO.  
2. ASSERTION PAGE_LOADED (from “Homepage loaded”).  
3. ACTION CLICK target=Air Solutions.  
4. ASSERTION PAGE_LOADED value=category (from “Category displayed”).

### Example 3: Flow config (LG)

**File:** `flow_config/lg_flow_config.json`

- Trigger `after_pincode_check`: dismiss modal with button texts OK, Continue, Select delivery, etc.; then wait 800 ms.
- Trigger `before_select_delivery`: dismiss modal, wait 1000 ms.
- Trigger `before_checkout`: dismiss modal (OK, Continue, Close), wait 500 ms.

These run automatically when the executor hits the corresponding steps (e.g. after pincode step, before delivery selection, before checkout).

---

## 6. Boilerplate Code Snippets

### 6.1 Router — run test (V2)

**File:** `backend/routers/ui_automation_v2.py`

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from services.ui_automation.core.enhanced_deterministic_executor import (
    DeterministicExecutorV2,
    ExecutionResult,
)
from services.ui_automation.core.semantic_parser import SemanticTestParser

router_v2 = APIRouter(prefix="/ui-automation-v2", tags=["ui-automation-v2"])


class TestRequestV2(BaseModel):
    natural_language: Optional[str] = None
    enterprise_spec: Optional[Dict[str, Any]] = None
    visible_browser: bool = True
    start_url: Optional[str] = None
    chat_id: Optional[str] = None


class TestResponseV2(BaseModel):
    test_id: str
    passed: bool
    total_steps: int
    executed_steps: int
    failed_step: Optional[int] = None
    error: Optional[str] = None
    duration_ms: int
    checkpoints: List[Dict[str, Any]]
    assertion_count: int = 0
    action_count: int = 0
    plan: Optional[Dict[str, Any]] = None
    script: Optional[str] = None


@router_v2.post("/run", response_model=TestResponseV2)
async def run_test_v2(request: TestRequestV2):
    if not request.natural_language and not request.enterprise_spec:
        raise HTTPException(400, "Either natural_language or enterprise_spec is required")

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not request.visible_browser)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        executor = DeterministicExecutorV2(page, context)

        if request.natural_language:
            result: ExecutionResult = await executor.execute_natural_language(
                request.natural_language, start_url=request.start_url
            )
        else:
            result = await executor.execute_enterprise_format(request.enterprise_spec)

        await browser.close()

    return TestResponseV2(
        test_id=result.test_id,
        passed=result.passed,
        total_steps=result.total_steps,
        executed_steps=result.executed_steps,
        failed_step=result.failed_step,
        error=result.error,
        duration_ms=result.duration_ms,
        checkpoints=[{"step_id": cp.step_id, "state": cp.state, "success": cp.success} for cp in result.checkpoints],
        plan=None,
        script=None,
    )
```

### 6.2 Test model (DSL)

**File:** `backend/services/ui_automation/core/test_model.py`

```python
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class StepType(str, Enum):
    NAVIGATION = "NAVIGATION"
    ACTION = "ACTION"
    INPUT = "INPUT"
    ASSERTION = "ASSERTION"
    WAIT = "WAIT"
    CONDITIONAL = "CONDITIONAL"
    UNKNOWN = "UNKNOWN"  # Unparseable step → fail explicitly, no CLICK fallback


class Intent(str, Enum):
    GOTO = "GOTO"
    CLICK = "CLICK"
    SELECT = "SELECT"
    ADD_TO_CART = "ADD_TO_CART"
    BUY_NOW = "BUY_NOW"
    CHECKOUT = "CHECKOUT"
    CONTINUE_AS_GUEST = "CONTINUE_AS_GUEST"
    TYPE = "TYPE"
    FILL_PINCODE = "FILL_PINCODE"
    SELECT_OPTION = "SELECT_OPTION"
    SEARCH = "SEARCH"
    PAGE_LOADED = "PAGE_LOADED"
    ELEMENT_VISIBLE = "ELEMENT_VISIBLE"
    TEXT_CONTAINS = "TEXT_CONTAINS"
    URL_MATCHES = "URL_MATCHES"
    WAIT = "WAIT"
    UNKNOWN = "UNKNOWN"  # Parser could not infer intent


class PageState(str, Enum):
    HOME = "HOME"
    CATEGORY = "CATEGORY"
    PRODUCT_LIST = "PRODUCT_LIST"
    PRODUCT_DETAIL = "PRODUCT_DETAIL"
    CART = "CART"
    CHECKOUT = "CHECKOUT"
    CONFIRMATION = "CONFIRMATION"
    UNKNOWN = "UNKNOWN"


class TestStep(BaseModel):
    id: int
    type: StepType
    intent: Intent
    target: Optional[str] = None
    value: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    required_state: Optional[PageState] = None
    expected_state: Optional[PageState] = None
    max_retries: int = 1
    timeout: int = 5000

    class Config:
        use_enum_values = True


class TestCase(BaseModel):
    id: str
    title: str
    objective: Optional[str] = None
    preconditions: Optional[List[str]] = None
    test_data: Optional[Dict[str, Any]] = None
    steps: List[TestStep]

    class Config:
        use_enum_values = True
```

### 6.3 Semantic parser — parse natural language

**File:** `backend/services/ui_automation/core/semantic_parser.py`

```python
import re
from typing import List, Optional
from .test_model import TestCase, TestStep, StepType, Intent


class SemanticTestParser:
    @staticmethod
    def parse_natural_language(test_case_text: str, start_url: str = None) -> TestCase:
        steps = []
        step_id = 1
        raw_steps = [s.strip() for s in test_case_text.split("\n") if s.strip()]

        for raw_step in raw_steps:
            # Optional: split by comma only when not a product line
            sub_steps = [s.strip() for s in raw_step.split(",") if s.strip()]
            for sub in sub_steps:
                parsed = SemanticTestParser._parse_single_step(sub, step_id)
                if parsed:
                    steps.append(parsed)
                    step_id += 1

        return TestCase(
            id="auto_generated",
            title=(test_case_text[:50] + "..") if len(test_case_text) > 50 else test_case_text,
            steps=steps,
        )

    @staticmethod
    def _parse_single_step(step_text: str, step_id: int) -> Optional[TestStep]:
        step_lower = step_text.lower().strip()

        if step_lower.startswith(("navigate to", "go to")):
            url = re.search(r"https?://[^\s,]+", step_text)
            url = url.group() if url else "https://example.com"
            return TestStep(id=step_id, type=StepType.NAVIGATION, intent=Intent.GOTO, target=url)

        if step_lower.startswith(("verify", "check")) and "click" not in step_lower:
            return TestStep(id=step_id, type=StepType.ASSERTION, intent=Intent.PAGE_LOADED, value=step_text)

        if "click" in step_lower:
            target = re.sub(r"click\s+(?:on\s+)?", "", step_text, flags=re.I).strip()
            return TestStep(id=step_id, type=StepType.ACTION, intent=Intent.CLICK, target=target)

        if "wait" in step_lower:
            m = re.search(r"wait for (\d+)\s*seconds?", step_lower)
            secs = int(m.group(1)) if m else 1
            return TestStep(id=step_id, type=StepType.WAIT, intent=Intent.WAIT, metadata={"duration_ms": secs * 1000})

        return TestStep(id=step_id, type=StepType.ACTION, intent=Intent.CLICK, target=step_text)
```

### 6.4 Executor — execute test case and route steps

**File:** `backend/services/ui_automation/core/enhanced_deterministic_executor.py`

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from playwright.async_api import Page, BrowserContext
from .test_model import TestCase, TestStep, StepType, Intent
from .semantic_parser import SemanticTestParser
from .assertion_engine import AssertionEngine, AssertionResult
from .intent_dispatcher import IntentDispatcher
from .state_machine import detect_state


@dataclass
class ExecutionResult:
    test_id: str
    passed: bool
    total_steps: int
    executed_steps: int
    failed_step: Optional[int] = None
    error: Optional[str] = None
    checkpoints: List[dict] = None
    duration_ms: int = 0

    def __post_init__(self):
        if self.checkpoints is None:
            self.checkpoints = []


class DeterministicExecutorV2:
    def __init__(self, page: Page, context: BrowserContext):
        self.page = page
        self.context = context
        self.assertion_engine = AssertionEngine(page)
        self.intent_dispatcher = IntentDispatcher()
        self.checkpoints = []

    async def execute_natural_language(self, text: str, start_url: str = None) -> ExecutionResult:
        test_case = SemanticTestParser.parse_natural_language(text, start_url)
        return await self.execute_test_case(test_case)

    async def execute_test_case(self, test_case: TestCase) -> ExecutionResult:
        start = datetime.now()
        executed = 0
        try:
            for step in test_case.steps:
                if step.required_state:
                    current = await detect_state(self.page)
                    if current != step.required_state:
                        return ExecutionResult(
                            test_id=test_case.id,
                            passed=False,
                            total_steps=len(test_case.steps),
                            executed_steps=executed,
                            failed_step=step.id,
                            error=f"Expected state {step.required_state}, got {current}",
                            checkpoints=self.checkpoints,
                            duration_ms=int((datetime.now() - start).total_seconds() * 1000),
                        )

                if step.type == StepType.ASSERTION:
                    result = await self.assertion_engine.execute_assertion(step)
                    if not result.passed:
                        return ExecutionResult(
                            test_id=test_case.id,
                            passed=False,
                            total_steps=len(test_case.steps),
                            executed_steps=executed,
                            failed_step=step.id,
                            error=result.message,
                            checkpoints=self.checkpoints,
                            duration_ms=int((datetime.now() - start).total_seconds() * 1000),
                        )
                elif step.type in (StepType.ACTION, StepType.INPUT, StepType.NAVIGATION):
                    success, msg = await self._execute_action(step)
                    if not success:
                        return ExecutionResult(
                            test_id=test_case.id,
                            passed=False,
                            total_steps=len(test_case.steps),
                            executed_steps=executed,
                            failed_step=step.id,
                            error=msg,
                            checkpoints=self.checkpoints,
                            duration_ms=int((datetime.now() - start).total_seconds() * 1000),
                        )
                # ... WAIT, CONDITIONAL, post_step_stabilize, checkpoint
                executed += 1

            return ExecutionResult(
                test_id=test_case.id,
                passed=True,
                total_steps=len(test_case.steps),
                executed_steps=executed,
                checkpoints=self.checkpoints,
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )
        except Exception as e:
            return ExecutionResult(
                test_id=test_case.id,
                passed=False,
                total_steps=len(test_case.steps),
                executed_steps=executed,
                error=str(e),
                checkpoints=self.checkpoints,
                duration_ms=int((datetime.now() - start).total_seconds() * 1000),
            )

    async def _execute_action(self, step: TestStep):
        from .element_resolver import smart_click, smart_type
        from .smart_resolver import smart_resolve_click, smart_resolve_type

        if step.intent == Intent.GOTO:
            await self.page.goto(step.target, wait_until="domcontentloaded", timeout=30000)
            return True, f"Navigated to {step.target}"

        if step.intent in (Intent.CLICK, Intent.SELECT):
            # Phase 0: memory cache → Phase 1: smart_click → Phase 2: smart_resolve_click → Phase 3: visual → Phase 4: healing
            clicked = False
            try:
                await smart_click(self.page, step.target)
                clicked = True
            except Exception:
                try:
                    clicked, _ = await smart_resolve_click(self.page, step.target)
                except Exception:
                    pass
            if not clicked:
                # Phase 3 visual grounding, Phase 4 healing (see full impl.)
                return False, f"All phases failed for click: {step.target}"
            return True, f"Clicked {step.target}"

        if step.intent in (Intent.TYPE, Intent.FILL_PINCODE):
            try:
                await smart_type(self.page, step.target or "pincode", step.value)
                return True, f"Typed into {step.target}"
            except Exception:
                try:
                    ok = await smart_resolve_type(self.page, step.target or "pincode", step.value)
                    return (ok, f"Typed into {step.target}") if ok else (False, f"Type failed: {step.target}")
                except Exception as e:
                    return False, str(e)

        return False, f"Unhandled intent: {step.intent}"
```

### 6.5 Element resolver — Phase 1 click

**File:** `backend/services/ui_automation/core/element_resolver.py`

```python
import re
from playwright.async_api import Page


async def smart_click(page: Page, label: str):
    await page.wait_for_load_state("domcontentloaded", timeout=2000)
    await page.wait_for_timeout(500)

    candidates = [
        lambda: page.get_by_role("button", name=re.compile(re.escape(label), re.I)),
        lambda: page.get_by_role("link", name=re.compile(re.escape(label), re.I)),
        lambda: page.get_by_text(label, exact=True),
        lambda: page.get_by_text(re.compile(re.escape(label), re.I)),
        lambda: page.locator(f"text=/{re.escape(label)}/i"),
    ]

    for get_candidate in candidates:
        try:
            loc = get_candidate()
            if await loc.count() > 0:
                await loc.first.scroll_into_view_if_needed(timeout=2000)
                await loc.first.click(timeout=5000)
                return
        except Exception:
            continue
    raise Exception(f"smart_click failed for: {label}")
```

### 6.6 Smart resolver — Phase 2 with cache

**File:** `backend/services/ui_automation/core/smart_resolver.py`

```python
import hashlib
import json
import os
from playwright.async_api import Page
from difflib import SequenceMatcher
from typing import Optional

SELECTOR_CACHE_FILE = "selector_cache.json"
_cache = {}


def _hash(target: str, url: str) -> str:
    return hashlib.md5(f"{url}::{target}".encode()).hexdigest()


def _get_cached(target: str, url: str) -> Optional[str]:
    global _cache
    if not _cache and os.path.exists(SELECTOR_CACHE_FILE):
        with open(SELECTOR_CACHE_FILE) as f:
            _cache = json.load(f)
    return _cache.get(_hash(target, url))


def _save_cached(target: str, url: str, selector: str):
    _cache[_hash(target, url)] = selector
    with open(SELECTOR_CACHE_FILE, "w") as f:
        json.dump(_cache, f, indent=2)


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


async def smart_resolve_click(page: Page, target: str) -> bool:
    url = page.url
    sel = _get_cached(target, url)
    if sel:
        try:
            await page.locator(sel).first.click(timeout=5000)
            return True
        except Exception:
            pass

    buttons = await page.locator("button, a, [role='button']").all()
    best_score, best_el = 0.0, None
    for el in buttons[:50]:
        try:
            text = (await el.inner_text(timeout=500)).strip()
            if not text or len(text) > 200:
                continue
            s = similarity(target, text)
            if s > best_score and s > 0.4:
                best_score, best_el = s, el
        except Exception:
            continue

    if best_el:
        await best_el.click(timeout=5000)
        # Optionally cache selector (e.g. by generating from role+text)
        return True
    return False
```

### 6.7 Assertion engine — no UI action

**File:** `backend/services/ui_automation/core/assertion_engine.py`

```python
from playwright.async_api import Page
from .test_model import TestStep, Intent


class AssertionResult:
    def __init__(self, passed: bool, message: str, actual=None, expected=None):
        self.passed = passed
        self.message = message
        self.actual = actual
        self.expected = expected


class AssertionEngine:
    def __init__(self, page: Page):
        self.page = page

    async def execute_assertion(self, step: TestStep) -> AssertionResult:
        if step.intent == Intent.PAGE_LOADED:
            return await self._assert_page_loaded(step)
        if step.intent == Intent.ELEMENT_VISIBLE:
            return await self._assert_element_visible(step)
        if step.intent == Intent.TEXT_CONTAINS:
            return await self._assert_text_contains(step)
        return AssertionResult(False, f"Unknown assertion: {step.intent}")

    async def _assert_page_loaded(self, step: TestStep) -> AssertionResult:
        body = await self.page.query_selector("body")
        if not body:
            return AssertionResult(False, "Body not found")
        title = await self.page.title()
        if not title or title.lower() == "loading...":
            return AssertionResult(False, f"Invalid title: {title}")
        return AssertionResult(True, f"Page loaded: {title}", actual=title)

    async def _assert_element_visible(self, step: TestStep) -> AssertionResult:
        target = step.target or step.value
        if not target:
            return AssertionResult(False, "No target")
        try:
            visible = await self.page.is_visible(f"text={target}", timeout=2000)
            return AssertionResult(visible, f"Element '{target}' visible" if visible else f"Element '{target}' not visible")
        except Exception as e:
            return AssertionResult(False, str(e))

    async def _assert_text_contains(self, step: TestStep) -> AssertionResult:
        text = step.value or step.target
        if not text:
            return AssertionResult(False, "No text")
        content = await self.page.content()
        return AssertionResult(
            text.lower() in content.lower(),
            f"Page contains '{text}'" if text.lower() in content.lower() else f"Page does not contain '{text}'",
        )
```

### 6.8 Flow config (site-specific)

**File:** `backend/services/ui_automation/core/flow_config/lg_flow_config.json`

```json
{
  "site": "lg.com",
  "description": "LG India e-commerce flow handlers - popups, modals, delivery selection",
  "handlers": [
    {
      "trigger": "after_pincode_check",
      "description": "After pincode check, dismiss 'Select delivery option' popup",
      "actions": [
        {"type": "dismiss_modal", "button_texts": ["OK", "Continue", "Select delivery", "Select delivery option"]},
        {"type": "wait", "ms": 800}
      ]
    },
    {
      "trigger": "before_select_delivery",
      "description": "Before selecting delivery, ensure no modal blocks",
      "actions": [
        {"type": "dismiss_modal", "button_texts": ["OK", "Continue", "Select delivery"]},
        {"type": "wait", "ms": 1000}
      ]
    },
    {
      "trigger": "before_checkout",
      "description": "Before checkout, dismiss blocking modals",
      "actions": [
        {"type": "dismiss_modal", "button_texts": ["OK", "Continue", "Close"]},
        {"type": "wait", "ms": 500}
      ]
    }
  ]
}
```

### 6.9 Interrupt handler (generic)

**File:** `backend/services/ui_automation/core/interrupt_handler.py`

```python
from playwright.async_api import Page

DISMISS_TEXTS = [
    "ok", "continue", "close", "dismiss", "agree", "accept",
    "select delivery", "select delivery option", "proceed",
]


async def handle_interrupts(page: Page, timeout_ms: int = 2500) -> int:
    dismissed = 0
    for selector in ["[role='dialog']", ".modal:visible", "[class*='modal']:visible"]:
        try:
            modals = page.locator(selector)
            for i in range(await modals.count()):
                modal = modals.nth(i)
                if not await modal.is_visible():
                    continue
                buttons = modal.locator("button, a, [role='button']")
                for j in range(min(await buttons.count(), 5)):
                    btn = buttons.nth(j)
                    text = (await btn.inner_text(timeout=300)).strip().lower()
                    if any(d in text for d in DISMISS_TEXTS):
                        await btn.click(timeout=1000)
                        dismissed += 1
                        await page.wait_for_timeout(400)
                        break
                if dismissed:
                    break
        except Exception:
            continue
    return dismissed
```

### 6.10 State machine (detect state)

**File:** `backend/services/ui_automation/core/state_machine.py`

```python
from enum import Enum
from playwright.async_api import Page


class AppState(Enum):
    HOME = "home"
    CATEGORY = "category"
    PRODUCT_LIST = "product_list"
    PRODUCT_DETAIL = "product_detail"
    CART = "cart"
    CHECKOUT = "checkout"
    PAYMENT = "payment"
    ORDER_CONFIRMATION = "order_confirmation"
    UNKNOWN = "unknown"


def detect_by_url(url: str) -> AppState:
    u = url.lower()
    if "/order" in u or "/confirmation" in u:
        return AppState.ORDER_CONFIRMATION
    if "/checkout" in u:
        return AppState.CHECKOUT
    if "/cart" in u or "/basket" in u:
        return AppState.CART
    if "/product" in u or "/p/" in u:
        return AppState.PRODUCT_DETAIL
    if "/category" in u or "/air-solutions" in u:
        return AppState.CATEGORY
    if u.endswith("/") or u.endswith("/in"):
        return AppState.HOME
    return AppState.UNKNOWN


async def detect_state(page: Page) -> AppState:
    return detect_by_url(page.url)
```

---

## 7. File Reference

| File | Responsibility |
|------|----------------|
| `routers/ui_automation_v2.py` | HTTP API: parse request, launch browser, create executor, return TestResponseV2. |
| `core/test_model.py` | TestCase, TestStep, StepType (incl. UNKNOWN), Intent (incl. UNKNOWN), PageState (normalized DSL). |
| `core/semantic_parser.py` | Natural language / enterprise spec → TestCase; unparseable → UNKNOWN (no CLICK fallback). |
| `core/enhanced_deterministic_executor.py` | execute_test_case; reset + stabilize_before_run; route ASSERTION vs ACTION/INPUT/NAVIGATION; 4-phase resolution (0→1→2→recovery→3→4); contextual router before step; post-action validation; post-state fail on mismatch; _post_step_stabilize (popup + stability). |
| `core/element_resolver.py` | Phase 1: smart_click, smart_type, smart_select (multi-strategy, no AI). |
| `core/smart_resolver.py` | Phase 2: smart_resolve_click (weighted score, word overlap, blocklist, semantic floor, aliases, product cards) → (bool, selector); smart_resolve_type; selector cache. |
| `core/visual_grounding_engine.py` | Phase 3: resolve_visually (vision + text path), click_by_visual_result (coordinates → bbox → text), click_by_coordinates. |
| `core/healing_agent.py` | Phase 4: LLM-based healing for click/select failures. |
| `core/intent_dispatcher.py` | Deterministic handlers: SELECT_PRODUCT, FILL_PINCODE, SELECT_DELIVERY_OPTION, guest checkout, etc. |
| `core/assertion_engine.py` | Execute assertions by intent (PAGE_LOADED, ELEMENT_VISIBLE, TEXT_CONTAINS, …); read-only. |
| `core/flow_config_loader.py` | Load site flow config, run_flow_handlers(page, trigger). |
| `core/flow_config/<site>_flow_config.json` | Site-specific triggers and actions (dismiss_modal, wait). |
| `core/interrupt_handler.py` | handle_interrupts(page): dismiss common modals/cookie banners. |
| `core/stability_engine.py` | stabilize_before_run, force_layout_stabilization. |
| `core/action_validator.py` | validate_action (post-action checks for Buy Now, TYPE, SELECT_OPTION). |
| `core/popup_classifier.py` | Classify popup from DOM text; handle_interrupts_classified. |
| `core/contextual_action_router.py` | route_before_step (popup + guest/delivery routing). |
| `core/execution_memory.py` | get_cached_selector / set_cached_selector (cache-on-validation only); state transitions. |
| `core/state_machine.py` | detect_state(page), validate_state_transition. |
| `core/valid_data_generator.py` | generate_valid_data(field_label): pincode, email, phone, name, address. |

---

This gives you the full picture: **input** (NL or enterprise), **logic** (parser → executor → assertion/action with **4-phase resolution** plus Phase 3 visual grounding and Phase 4 healing, **strict post-state** fail on mismatch, **strict link/button matching** to avoid wrong clicks, flow config, popup classifier, stability, execution memory), and **output** (ExecutionResult / TestResponseV2 with checkpoints and plan). Use the boilerplate snippets as minimal templates; the real implementation in the repo has more strategies and edge cases.
