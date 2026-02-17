# Enterprise v4 Quick Start Guide

## 🚀 What Changed?

Your system was **guessing** with random exploration. Now it **executes deterministically**.

## ⚡ Quick Test (5 minutes)

### 1. Start Backend

```bash
cd backend
python run_uvicorn.py
```

### 2. Test v4 (Choose One)

#### Option A: Python Test Script

```bash
cd backend
python test_enterprise_v4.py
```

#### Option B: API Call

```bash
curl -X POST http://localhost:8004/api/ui-automation/run-enterprise-v4 \
  -H "Content-Type: application/json" \
  -d '{
    "raw_input": "navigate to https://www.lg.com/in\nclick on air solutions\nclick on split air conditioner",
    "visible_browser": true
  }'
```

#### Option C: Existing UI

1. Open chat UI: http://localhost:3000
2. Send message:
   ```
   navigate to https://www.lg.com/in
   click on air solutions
   click on split air conditioner
   ```
3. UI will automatically use v4 engine

### 3. Watch Results

You should see:
- ✅ 3 instructions compiled
- ✅ 3 steps executed
- ✅ No random exploration
- ✅ Health score > 0.9
- ✅ Execution time < 15s

## 📊 What to Expect

### Before (v3 - Random)
```
Iteration 1: Score intents → EXPLORE
Iteration 2: Random click → Failed
Iteration 3: Navigate back → about:blank
Result: FAILURE
```

### After (v4 - Deterministic)
```
Instruction 1: GOTO https://www.lg.com/in → ✅
Instruction 2: CLICK "air solutions" → ✅  
Instruction 3: CLICK "split air conditioner" → ✅
Result: SUCCESS (3/3)
```

## 🎯 Key Differences

| Feature | v3 | v4 |
|---------|----|----|
| Execution | Random exploration | Deterministic instructions |
| Planning | Intent scoring | Instruction compilation |
| Recovery | Blind navigation | Structured retry |
| State Check | None | After every step |
| Works on | LG India only | ANY application |

## 🔧 Configuration

No configuration needed! v4 automatically:
1. Compiles instructions from your test case
2. Validates instruction queue
3. Executes deterministically
4. Verifies state changes
5. Attempts structured recovery on failure

## 📝 Writing Test Cases

### Good (Deterministic)
```
navigate to https://www.lg.com/in
click on air solutions
click on split air conditioner
```

### Bad (Too vague)
```
buy something from LG
```

### Tips
- Be specific about what to click
- Use exact text visible on page
- List steps in order
- No need to add checkout logic unless you want it

## 🐛 Troubleshooting

### Problem: "No matching element found"
**Solution**: Check exact text on page. v4 uses fuzzy matching but works best with exact text.

### Problem: "No state change detected"
**Solution**: Element might not be clickable. Check if it's visible and enabled.

### Problem: "Instruction queue empty"
**Solution**: Make sure your test case has clear action words like "navigate", "click", "type".

## 📚 Learn More

- Full architecture: [ENTERPRISE_V4_ARCHITECTURE.md](./ENTERPRISE_V4_ARCHITECTURE.md)
- Code examples: [test_enterprise_v4.py](./backend/test_enterprise_v4.py)
- API docs: See `/run-enterprise-v4` endpoint

## ✅ Success Checklist

- [ ] Backend running
- [ ] Test executed
- [ ] 3/3 instructions completed
- [ ] Health score > 0.9
- [ ] No random exploration
- [ ] Screenshots captured

## 🎉 Ready for Production

v4 is production-ready and works for:
- ✅ B2C ecommerce
- ✅ B2B dashboards
- ✅ D2C apps
- ✅ Enterprise portals
- ✅ Admin panels

**No more guessing. Only deterministic execution.**
