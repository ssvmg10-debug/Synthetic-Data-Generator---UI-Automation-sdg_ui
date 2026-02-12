# LangGraph Workflow Diagrams

## 🎨 Visual Architecture

### 1. Synthetic Data Generation Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SYNTHETIC DATA WORKFLOW                          │
│                        (Linear Flow)                                │
└─────────────────────────────────────────────────────────────────────┘

    ┌───────────────┐
    │     START     │
    └───────┬───────┘
            │
            ▼
    ┌───────────────────────────┐
    │  NODE 1: Parse Test Case  │
    │  - Extract URLs           │
    │  - Parse context          │
    └───────────┬───────────────┘
                │
                ▼
    ┌───────────────────────────┐
    │  NODE 2: Crawl Pages      │
    │  - Check cache (24h TTL)  │
    │  - Extract form schemas   │
    │  - Save to crawl_cache    │
    └───────────┬───────────────┘
                │
                ▼
    ┌───────────────────────────┐
    │  NODE 3: Merge Schemas    │
    │  - Combine test case +    │
    │    crawler results        │
    │  - Use GPT-4 to merge     │
    │  - Save to schema table   │
    └───────────┬───────────────┘
                │
                ▼
    ┌───────────────────────────┐
    │  NODE 4: Generate Data    │
    │  - Use SDV engine         │
    │  - Generate N rows        │
    │  - Save to synthetic_data │
    └───────────┬───────────────┘
                │
                ▼
            ┌───────┐
            │  END  │
            └───────┘
```

**State Object:**
```typescript
{
  test_case: string,          // User input
  num_rows: number,           // How many rows to generate
  urls: string[],             // Extracted URLs
  crawled_schemas: object,    // Schemas from crawled pages
  merged_schema: object,      // Final merged schema
  schema_id: number,          // DB schema ID
  run_id: number,             // DB run ID
  generated_data: array,      // Final synthetic data
  error: string | null,
  current_step: string
}
```

---

### 2. UI Automation Workflow (Self-Healing)

```
┌─────────────────────────────────────────────────────────────────────┐
│                   UI AUTOMATION WORKFLOW                            │
│                  (Self-Healing Loop)                                │
└─────────────────────────────────────────────────────────────────────┘

    ┌───────────────┐
    │     START     │
    └───────┬───────┘
            │
            ▼
    ┌───────────────────────────┐
    │  NODE 1: Plan Test        │
    │  ✅ Uses PlannerAgent     │
    │  - Parse test case        │
    │  - Create structured plan │
    └───────────┬───────────────┘
                │
                ▼
    ┌───────────────────────────┐
    │  NODE 2: Generate Script  │
    │  ✅ Uses GeneratorAgent   │
    │  - Create Playwright code │
    │  - Save test case to DB   │
    └───────────┬───────────────┘
                │
                ▼
    ┌───────────────────────────┐
    │  NODE 3: Execute Test     │
    │  - Run Playwright script  │
    │  - Capture errors         │
    └───────────┬───────────────┘
                │
                ▼
    ┌───────────────────────────┐
    │  NODE 4: Monitor          │
    │  - Check status           │
    │  - Count healing attempts │
    └───────────┬───────────────┘
                │
                ├─────[PASSED?]─────────┐
                │                       │
                │ No                    │ Yes
                ▼                       ▼
    [Max attempts reached?]         ┌───────┐
                │                   │  END  │
                │ No                └───────┘
                ▼
    ┌───────────────────────────┐
    │  NODE 5: Heal Failure     │  ◄──────┐
    │  ✅ Uses HealerAgent      │         │
    │  - Analyze error          │         │
    │  - Generate new locators  │         │
    │  - Save healing_history   │         │
    └───────────┬───────────────┘         │
                │                         │
                ▼                         │
    ┌───────────────────────────┐         │
    │  NODE 6: Retry Execution  │         │
    │  - Run healed script      │         │
    │  - Check result           │         │
    └───────────┬───────────────┘         │
                │                         │
                ├─────[FAILED?]───────────┘
                │      (loop back)
                │
                │ [PASSED]
                ▼
            ┌───────┐
            │  END  │
            └───────┘
```

**State Object:**
```typescript
{
  test_case: string,              // User input
  max_healing_attempts: number,   // Max retries (default: 3)
  structured_plan: object,        // From PlannerAgent
  playwright_script: string,      // Generated script
  testcase_id: number,            // DB test case ID
  execution_status: string,       // 'pending' | 'passed' | 'failed'
  healing_attempts: number,       // Current attempt count
  healed: boolean,                // Was healing successful?
  healing_history: array,         // All healing attempts
  last_error_locator: string,     // Failed selector
  error: string | null,
  current_step: string
}
```

---

### 3. Self-Healing Decision Tree

```
                    ┌──────────────────┐
                    │  Test Executed   │
                    └────────┬─────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
                PASSED?           FAILED?
                    │                 │
                    ▼                 ▼
            ┌──────────┐      ┌─────────────────┐
            │   END    │      │ Attempts < Max? │
            │  (Success)│      └────────┬────────┘
            └──────────┘               │
                             ┌─────────┴─────────┐
                             │                   │
                            YES                 NO
                             │                   │
                             ▼                   ▼
                    ┌─────────────────┐  ┌──────────┐
                    │  HealerAgent    │  │   END    │
                    │  Analyzes Error │  │ (Failed) │
                    └────────┬────────┘  └──────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
         Healing Strategy:         Healing Strategy:
         Attribute Fallback        GPT-4 Analysis
                │                         │
                ▼                         ▼
        ┌──────────────┐          ┌──────────────┐
        │ Try: class   │          │ Analyze DOM  │
        │ Try: text    │          │ Suggest best │
        │ Try: xpath   │          │ alternative  │
        └──────┬───────┘          └──────┬───────┘
               │                         │
               └────────┬────────────────┘
                        │
                        ▼
                ┌───────────────┐
                │ Retry Script  │
                │ with Healed   │
                │ Locators      │
                └───────┬───────┘
                        │
                  [Loop Back to
                   Test Executed]
```

---

### 4. Agent Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     LANGGRAPH INTEGRATION                           │
└─────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────┐
    │         FastAPI Router Layer                    │
    │  /api/synthetic-data/generate-from-text         │
    │  /api/ui-automation/run-workflow                │
    └─────────────────┬───────────────────────────────┘
                      │
                      ▼
    ┌─────────────────────────────────────────────────┐
    │         LangGraph Workflow Layer                │
    │  ┌───────────────┐   ┌────────────────┐        │
    │  │ Synthetic Data│   │ UI Automation  │        │
    │  │   StateGraph  │   │   StateGraph   │        │
    │  └───────┬───────┘   └────────┬───────┘        │
    └──────────┼──────────────────────┼───────────────┘
               │                      │
               ▼                      ▼
    ┌──────────────────┐   ┌──────────────────────┐
    │  Workflow Nodes  │   │   Workflow Nodes     │
    │  - parse         │   │   - plan (Planner)   │
    │  - crawl         │   │   - generate (Gen)   │
    │  - merge         │   │   - execute          │
    │  - generate      │   │   - monitor          │
    └──────────────────┘   │   - heal (Healer)    │
                           │   - retry            │
                           └──────────┬───────────┘
                                      │
                                      ▼
                           ┌──────────────────────┐
                           │  Existing Agents     │
                           │  ✅ PlannerAgent    │
                           │  ✅ GeneratorAgent  │
                           │  ✅ HealerAgent     │
                           │  ✅ ValidatorAgent  │
                           └──────────────────────┘
```

---

### 5. Database Schema Relations

```
┌─────────────────────────────────────────────────────────────────────┐
│                     DATABASE TABLES                                 │
└─────────────────────────────────────────────────────────────────────┘

    Workflow State Tables:
    
    ┌────────────────────┐
    │ agent_checkpoints  │  ← LangGraph state persistence
    │ - thread_id        │
    │ - checkpoint_id    │
    │ - state_json       │
    │ - checkpoint_metadata│
    └────────────────────┘
    
    ┌────────────────────┐
    │ workflow_executions│  ← Track workflow runs
    │ - workflow_type    │
    │ - status           │
    │ - current_node     │
    │ - result_json      │
    └────────────────────┘
    
    
    Self-Healing Tables:
    
    ┌────────────────────┐      ┌────────────────────┐
    │  ui_testcases      │──────│  healing_history   │
    │  - id              │      │  - testcase_id (FK)│
    │  - test_case       │      │  - failed_locator  │
    │  - structured_plan │      │  - healed_locator  │
    │  - script          │      │  - strategy_used   │
    │  - status          │      │  - success         │
    └────────────────────┘      │  - confidence_score│
                                └────────────────────┘
    
    
    Crawling Cache:
    
    ┌────────────────────┐
    │   crawl_cache      │  ← 24-hour cache
    │   - url (unique)   │
    │   - schema_json    │
    │   - html_snapshot  │
    │   - expires_at     │
    └────────────────────┘
    
    
    Agent Memory:
    
    ┌────────────────────┐
    │   agent_memory     │  ← Long-term memory
    │   - agent_type     │
    │   - memory_key     │
    │   - memory_value   │
    │   - embedding      │
    │   - relevance_score│
    └────────────────────┘
```

---

### 6. Healing Strategies Flowchart

```
    ┌───────────────────────┐
    │  Locator Failed       │
    │  (e.g., button#submit)│
    └──────────┬────────────┘
               │
               ▼
    ┌──────────────────────────────────┐
    │  Strategy 1: Attribute Fallback  │
    │  - Try ID → Class → Name → Text  │
    └──────────┬───────────────────────┘
               │
               ├─[Success?]─→ ✅ Return healed locator
               │
               ▼ [No]
    ┌──────────────────────────────────┐
    │  Strategy 2: Fuzzy Text Match    │
    │  - Find similar text content     │
    │  - Match partial strings         │
    └──────────┬───────────────────────┘
               │
               ├─[Success?]─→ ✅ Return healed locator
               │
               ▼ [No]
    ┌──────────────────────────────────┐
    │  Strategy 3: Context-Aware       │
    │  - Look at parent/sibling els    │
    │  - Use relative positioning      │
    └──────────┬───────────────────────┘
               │
               ├─[Success?]─→ ✅ Return healed locator
               │
               ▼ [No]
    ┌──────────────────────────────────┐
    │  Strategy 4: GPT-4 Analysis      │
    │  - Send HTML snapshot to GPT-4   │
    │  - Get AI-suggested locator      │
    │  - Confidence score > 0.8?       │
    └──────────┬───────────────────────┘
               │
               ├─[Success?]─→ ✅ Return healed locator
               │
               ▼ [No]
            ┌──────┐
            │ FAIL │
            └──────┘
```

---

## 🎯 Key Benefits Visualization

```
┌──────────────────────────────────────────────────────────────┐
│  WITHOUT LangGraph         │  WITH LangGraph                 │
├────────────────────────────┼─────────────────────────────────┤
│  Manual agent orchestration│  Automatic state management     │
│  No state persistence      │  Built-in checkpointing         │
│  Hard-coded retry logic    │  Declarative workflows          │
│  No healing audit trail    │  Complete healing history       │
│  Single-pass execution     │  Multi-attempt self-healing     │
│  Brittle tests             │  Resilient tests                │
└──────────────────────────────────────────────────────────────┘
```

---

**Legend:**
- ✅ = Integrated existing agent
- ← = One-to-many relationship
- → = Flow direction
- ◄─ = Loop back
