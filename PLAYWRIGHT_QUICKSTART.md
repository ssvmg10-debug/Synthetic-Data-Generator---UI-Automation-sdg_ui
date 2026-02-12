# Playwright Test Agents - Quick Start Guide

## 🎯 What Are Playwright Test Agents?

Three AI-powered agents built into Playwright:
- **🎭 Planner**: Creates test plans from requirements
- **🎭 Generator**: Converts plans into executable tests
- **🎭 Healer**: Auto-fixes broken tests

## 🚀 Setup (One-Time)

```bash
# 1. Install packages (already done ✅)
cd backend
npm install

# 2. Install browsers (already done ✅)
npx playwright install

# 3. Initialize agents
POST http://localhost:8000/ui/playwright-agents/init
```

## 📋 Usage Examples

### Option 1: Use Our Standard Workflow (Recommended)

**The easiest way** - Our system automatically uses Playwright Test Agents:

```http
POST http://localhost:8000/ui/run
Content-Type: application/json

{
  "raw_input": "Test checkout: open https://sauce-demo.myshopify.com/, add grey shirt to cart, checkout",
  "use_synthetic_data": false
}
```

Our agents (Planner → Generator → Executor → Healer) now use Playwright Test Agents internally! ✨

### Option 2: Direct Playwright Agent API

**For advanced control** - Call agents directly:

#### Step 1: Create Test Plan

```http
POST http://localhost:8000/ui/playwright-agents/planner
Content-Type: application/json

{
  "request": "Generate test plan for guest checkout flow",
  "base_url": "https://sauce-demo.myshopify.com/"
}
```

Response:
```json
{
  "success": true,
  "plan_file": "specs/guest-checkout-flow.md",
  "plan_content": "# Test Plan: Guest Checkout...",
  "message": "Test plan generated successfully"
}
```

#### Step 2: Generate Test Code

```http
POST http://localhost:8000/ui/playwright-agents/generator
Content-Type: application/json

{
  "plan_file": "specs/guest-checkout-flow.md"
}
```

Response:
```json
{
  "success": true,
  "test_file": "test_outputs/guest-checkout-flow.spec.ts",
  "test_content": "import { test, expect } from '@playwright/test';...",
  "message": "Playwright test generated successfully"
}
```

#### Step 3: Execute Test

```bash
npx playwright test test_outputs/guest-checkout-flow.spec.ts --headed
```

#### Step 4: Heal if Failed

```http
POST http://localhost:8000/ui/playwright-agents/healer
Content-Type: application/json

{
  "test_file": "test_outputs/guest-checkout-flow.spec.ts",
  "error_message": "Timeout waiting for selector \"#checkout-button\"",
  "max_retries": 3
}
```

Response:
```json
{
  "success": true,
  "healed": true,
  "actions": [
    "Identified failed selector: #checkout-button",
    "Replaced with alternative: [data-testid='checkout-button']"
  ],
  "message": "Test healed successfully"
}
```

## 🎨 What Changed in Our System

### Before
```python
planner = PlannerAgent()  # Basic planning
generator = GeneratorAgent()  # Basic generation
healer = HealerAgent()  # Basic healing
```

### After (Now with AI! 🤖)
```python
planner = PlannerAgent(use_playwright_agents=True)  # AI-powered planning
generator = GeneratorAgent(use_playwright_agents=True)  # AI-powered generation
healer = HealerAgent(use_playwright_agents=True)  # AI-powered healing
```

**Result**: Smarter tests, better self-healing, more reliable automation! 🎉

## 📁 File Structure

```
backend/
├── playwright.config.ts          ← Playwright configuration
├── package.json                  ← Node dependencies
├── specs/                        ← Test plans (Markdown)
│   └── *.md
├── test_outputs/                 ← Generated tests
│   ├── seed.spec.ts             ← Environment setup
│   ├── test_*.spec.js           ← Our JS tests
│   └── *.spec.ts                ← PW Agent TS tests
└── services/ui_automation/agents/
    └── playwright_test_agents.py ← Integration wrapper
```

## 🔥 Key Benefits

1. **AI-Powered**: Playwright's AI helps generate and heal tests
2. **Self-Healing**: Automatically fixes broken selectors
3. **Human-Readable**: Markdown plans are easy to review
4. **Live Verification**: Selectors verified during generation
5. **Best Practices**: Follows Playwright recommendations

## 🎯 When to Use What

### Use Standard Workflow (`/ui/run`)
- ✅ Normal test automation
- ✅ Quick test generation
- ✅ Integration with synthetic data
- ✅ Self-healing included
- ✅ **Most common use case**

### Use Direct Playwright Agents
- ✅ Need full control over each step
- ✅ Want to review plans before generation
- ✅ Custom modifications to generated tests
- ✅ Advanced debugging scenarios

## 📊 API Endpoints Summary

| Endpoint | Purpose | Method |
|----------|---------|--------|
| `/ui/run` | Complete workflow (recommended) | POST |
| `/ui/playwright-agents/init` | Initialize agents | POST |
| `/ui/playwright-agents/planner` | Create test plan | POST |
| `/ui/playwright-agents/generator` | Generate test code | POST |
| `/ui/playwright-agents/healer` | Auto-fix broken tests | POST |

## 🚨 Troubleshooting

### Backend not starting?
```bash
# Check backend terminal for errors
# Restart if needed:
cd backend
C:\Users\gparavasthu\Workspace\Truvelocity\code_export\agentic-sdlc-platform\venv\Scripts\python.exe -m uvicorn main:app --reload
```

### Tests failing?
1. Check logs in `backend/test_outputs/logs_*.txt`
2. Use Healer agent to auto-fix
3. Review generated test in `backend/test_outputs/`

### Can't find playwright?
```bash
cd backend
npm install @playwright/test
npx playwright install
```

## ✅ Status

- [x] Playwright Test Agents configured
- [x] Integration with existing agents
- [x] API endpoints created
- [x] Documentation complete
- [x] Backend running

**Everything is ready to use!** 🚀

## 📚 Learn More

- Full documentation: [PLAYWRIGHT_TEST_AGENTS.md](PLAYWRIGHT_TEST_AGENTS.md)
- Official docs: https://playwright.dev/docs/test-agents

---

**Ready to test?** Try the standard workflow first:
```
POST http://localhost:8000/ui/run
Body: { "raw_input": "your test case here" }
```
