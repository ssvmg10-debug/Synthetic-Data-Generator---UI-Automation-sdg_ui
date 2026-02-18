# UI Automation V3 — Integration Audit

This document confirms **all implemented fixes and components are used** in the current flow (no dead code for LG).

---

## Where we store commonly used routes, selectors, locators, DOM structure

**Yes — we store them, and we use them.** Below is what we store and where.

### 1. **Locator Registry (ELR)** — `backend/locator_registry.json`

**We use it:** Plan adapter injects ELR selectors into each step as `locator_candidates`; the executor tries them **first** (Phase 0) before site knowledge, smart_click, or healing.

**What we store (per key `site|path|normalized_target|intent`):**

| Field | Description |
|-------|-------------|
| `site` | e.g. `lg.com` |
| `page_url` | Normalized page URL (path, no fragment/query) |
| `normalized_target` | e.g. `search`, `air solutions` |
| `intent` | e.g. `CLICK`, `SELECT` |
| **`primary_selector`** | `{ "type": "css" \| "aria" \| "xpath", "value": "a[href='#search']" }` |
| **`fallback_selectors`** | List of `{ type, value }` for fallbacks |
| **`dom_fingerprint`** | `tag`, `parent_chain`, `text_hash`, `attribute_hash`, `sibling_index` for structural recovery when selector breaks |
| **`confidence_score`** | 0–1 from success/failure and recency |
| **`success_count`** / **`failure_count`** | For confidence and demotion |
| **`last_verified`** | ISO timestamp |

**When we write:**  
- After a **successful click**: `promotion_engine.promote_on_success()` → `locator_registry.add_or_update()` or `add_fallback()` + `record_success()`.  
- After **crawl**: `locator_registry.bootstrap_from_site_knowledge()` from site_knowledge pages.  
- On **failure** of an ELR selector: `demote_on_failure()` → `record_failure()` (can demote primary to fallback).

**Example from your run:** Your file already has  
`lg.com|/in|search|CLICK` → primary `a[href="#search"]`, confidence 0.98, success_count 1. So the “click search” step is stored and will be tried first next time.

---

### 2. **Execution memory** — `backend/services/ui_automation/core/execution_memory.json`

**We use it:** Executor Phase 4 (after ELR, fingerprint, generator) tries cached selectors for the current URL + target + intent.

**What we store:**

| Store | Key | Value |
|-------|-----|--------|
| **selectors** | `md5(url::target::intent)` | Single selector string (legacy) |
| **selectors_v2** | `v2_` + hash(env, url, intent_type, normalized_target) | `{ "selector", "bounding_box", "container_info", "dom_path" }` |
| **state_transitions** | — | `{ "from", "to", "step_id" }` (last 200) |
| **stable_paths** | per site | List of step labels for “known good” path (last 20) |

**When we write:** After a successful **click** (and validation), `set_cached_selector_v2()` or `set_cached_selector()`. For **search input**, we cache `input:focus` for (url, `"search"`, `TYPE`) so the next run can try it in Phase 3.

---

### 3. **Site knowledge** — `backend/site_knowledge.json` (or project root)

**We use it:** Executor Phase 5: `site_knowledge.try_click()` for the current page and target.

**What we store (per URL, per label):**

| Field | Description |
|-------|-------------|
| **text** | Visible text / aria-label |
| **tag** | `a`, `button`, etc. |
| **href** | For links |
| **css** | e.g. `a[href='/in/air-solutions']` (from crawl) |
| **role**, **aria_label**, **data_testid** | For accessibility / test IDs |
| **parent_chain** | Parent tag names (for DOM structure) |

**When we write:** `record_from_page()` on every visited page (and during crawl).

---

### 4. **Element history** — `backend/services/ui_automation/core/element_history.json`

**We use it:** Resolution engine uses it to **boost** candidates that match the last successful fingerprint for that step; and for **learned wait** (p95 of past success delays).

**What we store (per step key):**  
`fingerprint` (tag, role, ancestor_path, ordinal, text_preview), `selector`, `bounding_box`, `last_delays_ms`.

**When we write:** After a successful click when resolution returns a fingerprint.

---

### 5. **DOM fingerprint (recovery)** — used at runtime, not a separate file

**We use it:** When an ELR entry has `dom_fingerprint`, the executor Phase 2 calls `find_by_fingerprint()` to find an element with similar structure (tag, parent_chain, attributes) and use that selector. Stored **inside ELR entries** as `dom_fingerprint`.

---

### Summary: are we storing and using?

| Question | Answer |
|----------|--------|
| Are we storing **commonly used routes**? | Yes — in **execution_memory** (state_transitions, stable_paths) and **site_knowledge** (per-URL labels). |
| Are we storing **selectors / locators**? | Yes — in **Locator Registry** (primary + fallbacks), **execution_memory** (selector cache), **site_knowledge** (css, href, etc.). |
| Are we storing **DOM structure**? | Yes — **parent_chain** in site_knowledge and in ELR **dom_fingerprint**; **element_history** fingerprint for scoring. |
| Is **Locator Registry** used? | Yes — **enrich_plan_with_elr** and **plan_to_test_case** inject `locator_candidates` from ELR; executor **Phase 0** tries them first; **promote_on_success** and **demote_on_failure** update ELR. |
| Where is the registry file? | **`backend/locator_registry.json`** (you already have an entry for `search` CLICK). |

## Request path (V2)

1. **API**: `POST /ui-automation-v2/run` with `natural_language` or `enterprise_spec`
2. **Router** (`routers/ui_automation_v2.py`): Launches Playwright browser, creates `DeterministicExecutorV2`, calls `execute_natural_language()` or `execute_enterprise_format()`
3. **Executor** (`core/enhanced_deterministic_executor.py`): Parses test case, runs steps, uses all components below

## Components in use (no hardcoding)

| Component | Where used | Purpose |
|-----------|-------------|---------|
| **Semantic Parser** | `SemanticTestParser.parse_natural_language()` | Converts English → TestCase; `_split_compound_instruction()` splits "click X and search for Y" into separate steps |
| **Site Knowledge** | `site_knowledge.record_from_page()`, `site_knowledge.try_click()` | After GOTO and in Phase 0.5 of CLICK; pre-crawl data from `site_knowledge.json` (from `run_lg_site_crawl`) |
| **Execution Memory** | `ExecutionMemory` (Phase 0 cache) | `get_cached_selector_v2` / `set_cached_selector_v2`; state transitions; persists to `execution_memory.json` |
| **Contextual Action Router** | `route_before_step()` before each step | Popup classification + dismiss; LG quick menu close when `lg.com` in URL |
| **Popup Classifier** | `classify_visible_popup`, `dismiss_popup_by_type`, `handle_interrupts_classified` | Login/delivery/consent/generic; quick-close for LG |
| **Flow Handlers** | `run_flow_handlers(page, trigger)` | `lg_flow_config.json`: after_pincode_check, before_select_delivery, before_checkout |
| **Element Resolver** | `smart_click`, `smart_type`, `smart_select` | Multi-strategy click/type/select; search and nav-specific strategies |
| **Resolution Decision Engine** | `resolve_click_with_fallbacks`, `classify_intent` | Confidence-based fallbacks when smart_click fails |
| **Healing Agent** | `heal_click_failure`, `apply_healing_action` | LLM suggests alternative click; **Mem0** search/add when `MEM0_API_KEY` set |
| **Wait Strategy** | `wait_after_navigation`, `wait_for_stable_dom`, `wait_after_major_action` | Stability after nav and after major actions |
| **Valid Data Generator** | `generate_valid_data` in FILL_FORM | Billing/shipping form fill with synthetic data |
| **Interrupt Handler** | `handle_interrupts()` | After flow handlers for cookie/popup dismiss |

## Site crawl (pre-populate cache)

- **Script**: `python -m backend.run_lg_site_crawl` (or `--headless`, `--validate`)
- **Output**: `backend/site_knowledge.json` (or project root depending on CWD)
- **Executor**: Loads same file at import; records every visited page during runs

## Confidence / “confid”

- **Resolution Decision Engine**: Uses intent-specific strong confidence thresholds; no separate “Confid” service — confidence is built into resolution and intent classification.
- **Healing Agent**: Returns and uses `confidence` in healing suggestion JSON.

## Mem0

- **Healing Agent** (`core/healing_agent.py`): If `MEM0_API_KEY` is set, `_mem0_search()` injects past healing context into the LLM prompt; `_mem0_add()` stores successful heals for future runs.

## No LG-specific hardcoding

- LG is detected by URL (`lg.com` in URL) only for: (1) contextual router quick-menu close, (2) flow config site key `lg`. All selectors and labels are generic (search, checkout, guest, free delivery, pincode, etc.).

---

## V3 — Enterprise Deterministic (ELR + Fingerprint + Promotion)

V3 adds a **deterministic-first** resolution pipeline and learning so the system behaves as “a deterministic engine that learns and occasionally asks AI for help.”

### New components

| Component | File | Purpose |
|-----------|------|---------|
| **Enterprise Locator Registry (ELR)** | `core/locator_registry.py` | Persistent primary + fallback selectors, DOM fingerprint, confidence (success/failure, stability, recency). Data: `backend/locator_registry.json`. |
| **DOM Fingerprint Engine** | `core/dom_fingerprint.py` | Capture tag, parent_chain, attribute_hash, text_hash, sibling_index; `find_by_fingerprint()` for structural recovery when selector breaks (no AI). |
| **Selector Confidence** | `locator_registry._compute_confidence()` | `base * stability_weight * recency_weight`; demote when &lt; 0.4. |
| **Self-Learning Promotion** | `core/promotion_engine.py` | On success: `promote_on_success()` → add/update ELR; on ELR failure: `demote_on_failure()` → record_failure, possibly demote primary. |
| **Locator Enrichment** | `core/plan_adapter.py` | `enrich_plan_with_elr(plan)` and per-step ELR lookup in `plan_to_test_case()`; injects `locator_candidates`, `elr_lookup_key`, `elr_entry` into step metadata. |

### Resolution order (V3)

0. **ELR** primary + fallbacks (from step metadata)  
1. **DOM Fingerprint** match (if stored fingerprint exists; similarity &gt; 0.75)  
2. **Generator** selectors  
3. **Execution memory** (cache)  
4. **SiteKnowledge**  
5. **smart_click** (element_resolver)  
6. **Resolution engine**  
7. **Retry** (backoff + resolution)  
8. **Healing agent**  
9. **Visual grounding**  
10. **Playwright HealerAgent** (if db)

### Crawl → ELR bootstrap

- **Site Knowledge** `record_from_page()` now extracts per element: `css`, `role`, `aria_label`, `data_testid`, `parent_chain` (rich selectors).
- After **site crawl** (`site_crawl_runner.run_site_crawl()`), `locator_registry.bootstrap_from_site_knowledge(site_knowledge.get_pages_for_bootstrap())` runs automatically to seed ELR from crawl data.

### Router

- Before building the test case, the router calls `enrich_plan_with_elr(plan, request.start_url)` so steps get ELR-backed `locator_candidates` when available.
- Logs and responses use **V3** branding (Enhanced Deterministic System V3).

### TYPE (search) and Mem0

- **Search input normalization**: TYPE steps like “type X in search input” are normalized to target `"search"` (plan adapter + executor) so the resolver uses search overlay and keywords.
- **Execution memory**: Successful search input use is cached (`search` + `TYPE`) so the next run can try the cached selector (e.g. `input:focus`) in Phase 3.
- **Mem0**: When `MEM0_API_KEY` is set, the healing agent uses Mem0 for *click* healing (search before heal, add after success). For *TYPE* failures on search, the executor tries Mem0 in Phase 3: searches memories for “search input” and, if a selector is found in the memory content, uses it to fill and press Enter.
- **Stored routes**: Commonly used navigation and clicks are stored in **site_knowledge**, **execution_memory**, and **ELR**; they are reused so the system does not re-resolve from scratch every time.
