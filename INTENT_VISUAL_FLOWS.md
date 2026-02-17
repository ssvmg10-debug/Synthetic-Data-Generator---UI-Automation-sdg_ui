# Intent-Based Architecture - Visual Flow Diagrams

## 🎯 System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER TEST CASE                                │
│  "Search for lg tv, click buy now for LG AC, enter pincode"    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   INTENT PLANNER                                 │
│  Converts natural language → Semantic intents                   │
│  • LLM-based (Azure OpenAI) OR Rule-based (keywords)            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SEMANTIC INTENTS                               │
│  [                                                               │
│    Intent(SEARCH_PRODUCT, query="lg tv"),                      │
│    Intent(SELECT_PRODUCT, product_name="LG AC"),               │
│    Intent(ADD_TO_CART),                                         │
│    Intent(SET_PINCODE, value="500032")                         │
│  ]                                                               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FLOW ROUTER                                   │
│  Routes each intent to appropriate executor                     │
└─────────────┬──────────────────┬──────────────────┬─────────────┘
              │                  │                  │
              ▼                  ▼                  ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │  SEARCH FLOW    │ │  PRODUCT FLOW   │ │ CHECKOUT FLOW   │
    │                 │ │                 │ │                 │
    │ • Modal scope   │ │ • Fuzzy match   │ │ • Label prox    │
    │ • Input find    │ │ • CTA scoring   │ │ • Pincode field │
    │ • Result wait   │ │ • Cart validate │ │ • Delivery opt  │
    └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
             │                   │                   │
             ▼                   ▼                   ▼
    ┌─────────────────────────────────────────────────────────────┐
    │              STATE VALIDATION                                │
    │  Validates expected page state after each intent             │
    └─────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
                   ┌──────────────┐
                   │   Success?   │
                   └──┬────────┬──┘
                      │        │
                  YES │        │ NO
                      │        │
                      │        ▼
                      │  ┌────────────────┐
                      │  │ Retry (max 1)  │
                      │  │ Alt. strategy  │
                      │  └────────┬───────┘
                      │           │
                      ▼           ▼
                ┌─────────────────────────┐
                │    INTENT RESULT        │
                │ • Success/Fail          │
                │ • Execution time        │
                │ • Phase used            │
                │ • State validated       │
                └─────────────────────────┘
```

---

## 🔄 SearchFlow Executor

```
┌───────────────────────────────────────────────────────────┐
│              SEARCH_PRODUCT Intent                         │
│              query="lg tv"                                 │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Detect Search Modal?  │
            └───┬──────────────┬────┘
                │              │
            YES │              │ NO
                │              │
                ▼              ▼
    ┌─────────────────┐  ┌─────────────────┐
    │ Click search    │  │ Search on       │
    │ icon/button     │  │ main page       │
    └────────┬────────┘  └────────┬────────┘
             │                    │
             ▼                    │
    ┌─────────────────┐          │
    │ Wait for modal  │          │
    │ [role=dialog]   │          │
    └────────┬────────┘          │
             │                    │
             └──────────┬─────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Get Search Container  │
            │ (modal or page)       │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Find Search Input     │
            │ • type=search         │
            │ • placeholder         │
            │ • aria-label          │
            │ • name=search         │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Fill input + Enter    │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ STATE VALIDATION:     │
            │ Wait for product      │
            │ cards loaded          │
            └───────────┬───────────┘
                        │
                        ▼
                   ✅ Success
```

---

## 🛍️ ProductFlow Executor

```
┌───────────────────────────────────────────────────────────┐
│              SELECT_PRODUCT Intent                         │
│              product_name="LG AC"                          │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Get all product cards │
            │ .product-card         │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Fuzzy Match Product   │
            │ • partial_ratio       │
            │ • token_set_ratio     │
            │ • Best score > 50%    │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Click best match      │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ STATE VALIDATION:     │
            │ Wait for product page │
            │ (Buy button visible)  │
            └───────────┬───────────┘
                        │
                        ▼
                   ✅ Success


┌───────────────────────────────────────────────────────────┐
│              ADD_TO_CART Intent                            │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ CTA CLASSIFICATION    │
            │ Get all buttons       │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Score each button:    │
            │ • Text similarity 40% │
            │ • Button size     20% │
            │ • Price proximity 20% │
            │ • CSS styling     20% │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Select highest score  │
            │ (min threshold 0.3)   │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Click CTA button      │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ STATE VALIDATION:     │
            │ Wait for cart update  │
            │ (badge/message)       │
            └───────────┬───────────┘
                        │
                        ▼
                   ✅ Success
```

---

## 📦 CheckoutFlow Executor

```
┌───────────────────────────────────────────────────────────┐
│              SET_PINCODE Intent                            │
│              value="500032"                                │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Find Pincode Input    │
            │ Strategy cascade:     │
            └───────────┬───────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Direct attrs │ │ Placeholder  │ │ ARIA label   │
│ name=pincode │ │ placeholder= │ │ aria-label=  │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       └────────────────┼────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Label proximity?      │
            │ Find <label> with     │
            │ "pincode" text        │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Get associated input  │
            │ • for= attribute      │
            │ • parent container    │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Fill pincode value    │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Find "Check" button   │
            │ (optional)            │
            └───────────┬───────────┘
                        │
                        ▼
                   ✅ Success


┌───────────────────────────────────────────────────────────┐
│         SELECT_DELIVERY_OPTION Intent                      │
│         option="free delivery"                             │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ STATE VALIDATION:     │
            │ Wait for radio btns   │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Get all radio buttons │
            │ input[type=radio]     │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Match by text:        │
            │ • Check label text    │
            │ • Check parent text   │
            │ • Keyword matching    │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Select radio button   │
            │ radio.check()         │
            └───────────┬───────────┘
                        │
                        ▼
                   ✅ Success
```

---

## 🎯 CTA Classification Scoring

```
┌───────────────────────────────────────────────────────────┐
│                  All Page Buttons                          │
│  [Buy Now] [Add to Cart] [Save] [Share] [Details]        │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ For each button:      │
            │ Calculate 4 scores    │
            └───────────┬───────────┘
                        │
        ┌───────────────┼───────────────┬──────────────┐
        │               │               │              │
        ▼               ▼               ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────┐ ┌──────────┐
│ TEXT (40%)   │ │ SIZE (20%)   │ │ PROX(20%)│ │ CSS(20%) │
│              │ │              │ │          │ │          │
│ Fuzzy match  │ │ Button area  │ │ Distance │ │ Classes  │
│ to "buy",    │ │ Width×Height │ │ to price │ │ primary, │
│ "add cart"   │ │              │ │ element  │ │ cta, etc │
└──────┬───────┘ └──────┬───────┘ └─────┬────┘ └─────┬────┘
       │                │               │            │
       │  Example:      │  Example:     │  Example:  │  Example:
       │  0.9 (match)   │  0.8 (large)  │  0.7 (near)│  1.0 (yes)
       │                │               │            │
       └────────────────┴───────────────┴────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ WEIGHTED TOTAL:       │
            │ 0.9×0.4 + 0.8×0.2     │
            │ + 0.7×0.2 + 1.0×0.2   │
            │ = 0.85                │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Sort by score         │
            │ Return highest        │
            │ (if score > 0.3)      │
            └───────────┬───────────┘
                        │
                        ▼
                ✅ [Buy Now] selected
```

---

## 🔄 Retry Strategy

```
┌───────────────────────────────────────────────────────────┐
│                   Execute Intent                           │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Route to Flow         │
            │ Executor              │
            └───────────┬───────────┘
                        │
                        ▼
                ┌───────────────┐
                │   Success?    │
                └───┬───────┬───┘
                YES │       │ NO
                    │       │
                    │       ▼
                    │   ┌──────────────────────┐
                    │   │ Is retry enabled?    │
                    │   └───┬──────────────┬───┘
                    │   YES │              │ NO
                    │       │              │
                    │       ▼              ▼
                    │   ┌──────────────┐  ┌──────────┐
                    │   │ Retry with   │  │ Return   │
                    │   │ ALTERNATE    │  │ failure  │
                    │   │ strategy:    │  └──────────┘
                    │   │              │
                    │   │ • Resolver   │
                    │   │ • Generic    │
                    │   └──────┬───────┘
                    │          │
                    │          ▼
                    │   ┌──────────────┐
                    │   │  Success?    │
                    │   └───┬──────┬───┘
                    │   YES │      │ NO
                    │       │      │
                    └───────┴──────┴────────────┐
                                                 │
                                                 ▼
                            ┌─────────────────────────────┐
                            │      RESULT                 │
                            │ • success: bool             │
                            │ • execution_time: float     │
                            │ • phase_used: str           │
                            │ • retry_attempted: bool     │
                            │ • state_validated: bool     │
                            └─────────────────────────────┘

MAX RETRIES = 1
NO INFINITE LOOPS
FAIL FAST FOR CRITICAL INTENTS
```

---

## 🌐 Navigation Strategy

```
┌───────────────────────────────────────────────────────────┐
│              page.goto(url)                                │
└───────────────────────┬───────────────────────────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ wait_until=           │
            │ "domcontentloaded"    │
            │                       │
            │ ✅ RELIABLE           │
            │ ✅ FAST               │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ OPTIONAL:             │
            │ wait_for_load_state(  │
            │   "networkidle",      │
            │   timeout=5000        │
            │ )                     │
            │                       │
            │ ⚠️  Fail gracefully   │
            │ ⚠️  OK for heavy sites│
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Stabilization buffer  │
            │ wait(2000ms)          │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Body check (optional) │
            │ body.wait_for()       │
            └───────────┬───────────┘
                        │
                        ▼
                   ✅ Ready


BEFORE: networkidle (primary) → TIMEOUT on heavy sites
AFTER:  domcontentloaded (primary) → RELIABLE
```

---

## 📊 Phase Usage Flow

```
           Intent Execution
                  │
                  ▼
        ┌─────────────────┐
        │  Flow Executor? │
        └────┬────────┬───┘
         YES │        │ NO
             │        │
             ▼        ▼
    ┌────────────┐  ┌──────────────┐
    │ SearchFlow │  │ Generic      │
    │ ProductFlow│  │ Resolver     │
    │ CheckoutFlow│  │ (controlled) │
    └─────┬──────┘  └──────┬───────┘
          │                │
          └────────┬───────┘
                   │
                   ▼
            ┌──────────────┐
            │   Success?   │
            └───┬──────┬───┘
            YES │      │ NO
                │      │
                │      ▼
                │   ┌──────────────┐
                │   │ Retry with   │
                │   │ Resolver     │
                │   └──────┬───────┘
                │          │
                └──────────┘
                   │
                   ▼
              Record phase used:
              • flow_executor
              • resolver
              • retry


METRICS:
- Flow executor usage: 70-80%
- Resolver usage: 20-30%
- Retry attempts: <10%
```

---

## 🎭 Modal Scope Control

```
          Page State Check
                 │
                 ▼
        ┌────────────────┐
        │ Is modal open? │
        │ [role=dialog]  │
        └────┬───────┬───┘
         YES │       │ NO
             │       │
             ▼       ▼
    ┌────────────┐ ┌──────────┐
    │ Container= │ │Container=│
    │ Modal      │ │ Page     │
    └─────┬──────┘ └─────┬────┘
          │              │
          └──────┬───────┘
                 │
                 ▼
      ┌──────────────────────┐
      │ Scope all selectors  │
      │ to container         │
      └──────────┬───────────┘
                 │
                 ▼
      container.locator(selector)


BEFORE: page.query_selector() → Wrong element
AFTER:  container.query_selector() → Correct element

Example:
┌─────────────────────────────────────┐
│ Page                                │
│  <button>Search (wrong)</button>    │
│                                     │
│  <div role="dialog"> ← MODAL        │
│    <input type="search">            │
│    <button>Search (correct)</button>│
│  </div>                             │
└─────────────────────────────────────┘
```

---

## 🔍 Fuzzy Product Matching

```
        Product Cards on Page:
        ┌────────────────────────────┐
        │ LG 4 Star (1.5 Ton) Split │
        │ AC 2026 Model RS-Q19YNZE  │
        ├────────────────────────────┤
        │ Samsung 1.5T Inverter AC  │
        ├────────────────────────────┤
        │ Daikin 1.5T Split AC      │
        └────────────────────────────┘

        User Query: "LG 4 Star Split AC"
                          │
                          ▼
            ┌─────────────────────────┐
            │ For each card:          │
            │ • partial_ratio         │
            │ • token_set_ratio       │
            └─────────────┬───────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
    Card 1:           Card 2:          Card 3:
    Score=92          Score=35          Score=28
    (Best Match!)     (Samsung)         (Daikin)

                          │
                          ▼
            ┌─────────────────────────┐
            │ Select Card 1           │
            │ (score > 50 threshold)  │
            └─────────────────────────┘


BEFORE: Exact match only → FAIL
AFTER:  Fuzzy match (>50%) → SUCCESS
```

---

## 📈 System Metrics Dashboard

```
┌────────────────────────────────────────────────────────────┐
│                 EXECUTION METRICS                          │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Total Intents:          5                                │
│  Executed:               5                                │
│  Success:                4 (80%)                          │
│  Failed:                 1 (20%)                          │
│                                                            │
│  Total Time:             15.3s                            │
│  Avg Time/Intent:        3.1s                             │
│                                                            │
├────────────────────────────────────────────────────────────┤
│                 PHASE USAGE                                │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Flow Executors:         3 (75%)                          │
│  ├─ SearchFlow:          1                                │
│  ├─ ProductFlow:         1                                │
│  └─ CheckoutFlow:        1                                │
│                                                            │
│  Resolver:               1 (25%)                          │
│  Retries:                1 (20%)                          │
│                                                            │
├────────────────────────────────────────────────────────────┤
│                 INTENT BREAKDOWN                           │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  1. ✅ SEARCH_PRODUCT        (2.1s) [validated]          │
│  2. ✅ SELECT_PRODUCT        (3.5s) [validated]          │
│  3. ✅ ADD_TO_CART           (2.8s) [validated]          │
│  4. ❌ SET_PINCODE           (4.2s) [failed]             │
│  5. ✅ SELECT_DELIVERY       (2.7s) [validated]          │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

**All diagrams represent the production-grade intent-based architecture implementation.**
