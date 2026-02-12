# Why We Don't Achieve 100% UI Automation (LG India & Hilti India)

You already use **Planner**, **Generator**, and **Healer** agents with your config (`.env` for Azure OpenAI and DB). This document explains the **concrete limitations** in the current design that prevent 100% pass rate on real enterprise sites, and what would be needed to get closer.

---

## 1. **Selector design: "first" and no container scope**

**What we do today**

- Planner maps phrases like "first product" or "first product link" to a **single** selector string, e.g.  
  `a[href*='product'], .product a, .product-card a, article a`
- Generator always uses **`.first()`** on that locator:  
  `page.locator(selector).first().click()`

**Why this breaks**

- **First in DOM order ≠ first product on screen.**  
  The first match is often the **header/nav** "Products" link, not the first product card in the main content. We never scope to a **container** (e.g. `main`, `.product-listing`, `.search-results`), so we frequently click the wrong element.
- **Sites differ.**  
  LG and Hilti use different class names and structure. One generic selector list cannot fit both; we have no **per-application** or **per-page** selector strategy.

**Gap:** No **container-scoped** “first product” (e.g. “within main content”) and no **per-app** selector strategy.

---

## 2. **Healer has no page context**

**What we do today**

- Healer gets: **script** (full test code) and **error** (message from Playwright).
- It tries: **registry** → **rule-based alternatives** → **LLM suggestions**.
- LLM gets only the **failed selector string** and **error text**. It does **not** get:
  - Current page HTML/DOM
  - Screenshot
  - List of visible elements

**Why this breaks**

- Without DOM or screenshot, the healer and LLM are **guessing** alternative selectors. They don’t know what’s actually on the page, so suggestions can be invalid or match the wrong element.
- Real self-healing (e.g. testRigor-style) often uses **live page structure** (or screenshot + vision) to pick a robust fallback. We don’t.

**Gap:** Healer (and LLM) do **not** receive **page HTML** or **screenshot**; healing is context-blind.

---

## 3. **One selector per step, one retry per run**

**What we do today**

- Each step uses **one** primary selector and at most **one** fallback (e.g. `text=element_name`).
- If the test **fails**, we run the **healer once**, then **re-run the entire test** with the healed script.

**Why this breaks**

- A single step can fail for many reasons (timing, wrong element, overlay). We only try **one** alternative per step in the script, and **one** full retry after healing. That’s often not enough for flaky or complex pages.
- We don’t **try multiple selectors in sequence** in the same run (e.g. try selector A, then B, then C until one works).

**Gap:** No **multi-selector try sequence** per step and only **one** heal + full re-run.

---

## 4. **Timing and heavy pages**

**What we do today**

- After clicks we wait for `domcontentloaded` then `networkidle` (with timeouts).
- Enterprise sites (LG/Hilti) often have:
  - Long-running requests
  - Dynamic content (megamenus, lazy-loaded lists)
  - Cookie/modals that appear at different times

**Why this breaks**

- **networkidle** can fire too early or too late depending on the site; we don’t adapt per step or per app.
- We don’t wait for **specific** elements (e.g. “wait for product grid to have at least 1 item”) before clicking “first product”. So we sometimes click before content is ready.

**Gap:** No **adaptive waits** (e.g. wait for a container to be visible/have children) and no **per-step/per-app** load strategy.

---

## 5. **Verify steps are generic**

**What we do today**

- For “verify” we use either:
  - `toContainText(expected)`, or
  - `waitFor({ state: 'visible' })` on a selector (often `body`) when the description mentions “reach”, “payment”, “shipping”, etc.

**Why this breaks**

- **body** is visible as soon as the page loads; it doesn’t prove we reached “payment” or “shipping”. So we can **pass** even when we’re on the wrong page.
- We don’t verify **URL** or **specific elements** (e.g. “element containing ‘Payment’ or ‘Order summary’”). So our “verify” step is weak.

**Gap:** Verify doesn’t use **URL** or **strong, page-specific** visibility checks.

---

## 6. **No visual or semantic “first product”**

**What we do today**

- “First product” is implemented only as **first match of a CSS/text locator** in DOM order.

**Why this breaks**

- We don’t use:
  - **Visual order** (e.g. first product card in the viewport)
  - **Stable attributes** (e.g. `data-product-id`) that might be added by the backend
  - **Structure** (e.g. “first `article` inside `.product-grid`”)

So we’re sensitive to DOM order and layout changes.

**Gap:** No **scoped** or **structure-based** “first product” (e.g. first product inside a known container).

---

## 7. **Application and flow differences**

**Reality of LG / Hilti**

- **LG India:** Shopping may redirect to a **partner** or **different domain** for cart/checkout. Our flows assume one domain; we don’t handle cross-domain or redirect-to-partner.
- **Hilti:** May require **login** or **account** for cart/checkout. We don’t persist session or reuse a logged-in state; each test starts **guest** and from scratch.
- **Cookie / consent:** Banners and modals differ by site and region. We have generic “Accept cookie” selectors, but one size doesn’t fit all.

**Gap:** No **per-application** flow strategy (redirects, login, consent) and no **session reuse**.

---

## 8. **Summary: what’s missing for higher pass rate**

| Limitation | Impact | Direction to fix |
|------------|--------|-------------------|
| “First” = DOM order, no container scope | Clicks nav instead of first product | Scope “first product” to a main/content container; add per-app selectors |
| Healer has no DOM/screenshot | Blind selector suggestions | Pass HTML snapshot or screenshot (and optionally use vision API) into healer/LLM |
| One selector per step, one retry | Fragile and not resilient | Multi-selector try list per step; optional multi-retry with healing |
| Fixed load strategy (networkidle, etc.) | Timing issues on heavy sites | Adaptive waits (e.g. wait for product grid); optional per-app timeouts |
| Weak verify (body / generic visible) | False passes | Verify URL or specific “payment/shipping” elements |
| No session / cross-domain / login | Fails on login- or redirect-based flows | Session reuse; explicit login step; handle redirects |

---

## 9. **Using your config (env)**

The stack **already uses** your config:

- **Backend / E2E:** `.env` in project root and `backend/.env` are loaded (e.g. in `run_enterprise_e2e.py`, `run_migrations.py`, `create_db.py`, and `backend/utils/azure_openai.py`).
- **Azure OpenAI:** `AZURE_API_KEY`, `AZURE_ENDPOINT`, `AZURE_DEPLOYMENT` (e.g. gpt-4.1), `AZURE_API_VERSION` are used for Planner LLM enrichment and Healer LLM suggestions.
- **Database:** `DATABASE_URL` is used for migrations, E2E persistence (ui_testcases, ui_execution_runs, healing_history, locator_registry, workflow_executions).

So the **limitations above are not due to missing config**; they come from **design choices** (no page context in healer, single-selector-per-step, no container scope, no session/redirect handling). Addressing the gaps in the table above would move us toward higher automation coverage while still using the same planner, generator, and healer agents and your existing env.
