# 🎯 Intent-Based System - UI Integration Complete

## ✅ Integration Status

The intent-based automation system (v2.0) has been **fully integrated** with the backend API and is ready for UI consumption.

---

## 🔌 New API Endpoint

### POST `/ui/intent-based/run`

**Purpose**: Execute UI automation using the new intent-based architecture

**Request Body**:
```json
{
  "test_case": "Search for lg tv, select LG AC, add to cart, enter pincode 500032",
  "url": "https://www.lg.com/in",
  "chat_id": null,
  "visible_browser": true
}
```

**Response**:
```json
{
  "success": true,
  "test_case_id": 123,
  "chat_id": 45,
  "status": "running",
  "architecture": "intent-based-v2",
  "message": "Intent-based automation started in background"
}
```

**Features**:
- ✅ Background execution (non-blocking)
- ✅ Chat integration (progress updates)
- ✅ Live status tracking
- ✅ Metrics collection
- ✅ Headless/visible browser support

---

## 📊 How It Works

```
UI Request (POST /ui/intent-based/run)
         ↓
    Save Test Case
         ↓
  Start Background Task
         ↓
   Intent Planner
         ↓
   Flow Executors
         ↓
   State Validation
         ↓
   Record Results
         ↓
  Update Chat & DB
```

---

## 🎨 Frontend Integration Guide

### 1. Simple Usage

```typescript
// Send request
const response = await fetch('http://localhost:8000/ui/intent-based/run', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    test_case: "Search for laptop, select Dell XPS, add to cart",
    url: "https://example.com",
    visible_browser: true
  })
});

const result = await response.json();
console.log(`Test case ID: ${result.test_case_id}`);
console.log(`Chat ID: ${result.chat_id}`);

// Poll for status
const status = await fetch(`http://localhost:8000/ui/current-run/status`);
const statusData = await status.json();
console.log(`Stage: ${statusData.stage}`);
```

### 2. With Chat Integration

```typescript
// Include chat_id to get progress updates
const response = await fetch('http://localhost:8000/ui/intent-based/run', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    test_case: "...",
    url: "...",
    chat_id: 123,  // Existing chat
    visible_browser: true
  })
});

// Check chat for progress
const chat = await fetch(`http://localhost:8000/chats/${result.chat_id}`);
const chatData = await chat.json();
// chatData.messages will contain progress updates
```

### 3. Poll for Completion

```typescript
async function pollForCompletion(testCaseId: number) {
  while (true) {
    const status = await fetch(
      `http://localhost:8000/ui/current-run/status`
    );
    const data = await status.json();
    
    if (!data.running || data.test_case_id !== testCaseId) {
      // Completed or stopped
      break;
    }
    
    console.log(`Current stage: ${data.stage}`);
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
}
```

---

## 📋 Available Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/ui/intent-based/run` | POST | Start intent-based automation |
| `/ui/current-run/status` | GET | Get current run status |
| `/ui/current-run/live-screenshot` | GET | Get live screenshot |
| `/ui/results/{execution_id}` | GET | Get execution results |
| `/ui/enterprise-v3/metrics/{id}` | GET | Get detailed metrics |

---

## 🎯 UI Components Needed

### 1. Intent-Based Test Form

```tsx
function IntentBasedTestForm() {
  const [testCase, setTestCase] = useState('');
  const [url, setUrl] = useState('');
  const [visible, setVisible] = useState(true);
  
  const handleSubmit = async () => {
    const response = await fetch('/ui/intent-based/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        test_case: testCase,
        url: url,
        visible_browser: visible
      })
    });
    
    const result = await response.json();
    // Navigate to results page or show progress
  };
  
  return (
    <form onSubmit={handleSubmit}>
      <textarea 
        value={testCase}
        onChange={e => setTestCase(e.target.value)}
        placeholder="e.g., Search for laptop, select Dell XPS, add to cart"
      />
      <input
        value={url}
        onChange={e => setUrl(e.target.value)}
        placeholder="https://example.com"
      />
      <label>
        <input
          type="checkbox"
          checked={visible}
          onChange={e => setVisible(e.target.checked)}
        />
        Visible Browser
      </label>
      <button type="submit">Run Intent-Based Test</button>
    </form>
  );
}
```

### 2. Progress Monitor

```tsx
function IntentBasedProgress({ testCaseId }: { testCaseId: number }) {
  const [status, setStatus] = useState<any>(null);
  
  useEffect(() => {
    const interval = setInterval(async () => {
      const response = await fetch('/ui/current-run/status');
      const data = await response.json();
      
      if (data.running && data.test_case_id === testCaseId) {
        setStatus(data);
      } else {
        setStatus({ ...data, running: false });
        clearInterval(interval);
      }
    }, 2000);
    
    return () => clearInterval(interval);
  }, [testCaseId]);
  
  if (!status?.running) {
    return <div>Completed!</div>;
  }
  
  return (
    <div>
      <h3>Running Intent-Based Test</h3>
      <p>Stage: {status.stage}</p>
      <ProgressBar stage={status.stage} />
    </div>
  );
}
```

### 3. Architecture Selector

```tsx
function ArchitectureSelector() {
  const [architecture, setArchitecture] = useState<'intent-based' | 'enterprise-v3'>('intent-based');
  
  return (
    <select value={architecture} onChange={e => setArchitecture(e.target.value as any)}>
      <option value="intent-based">
        🎯 Intent-Based (v2.0) - Recommended
      </option>
      <option value="enterprise-v3">
        🏢 Enterprise v3 (Legacy)
      </option>
    </select>
  );
}
```

---

## 🔄 Migration Path

### For Existing UI Users

1. **Keep existing endpoints** - Enterprise v3 still works
2. **Add new button** - "Run with Intent-Based (v2.0)"
3. **Show architecture badge** - Let users know which system they're using

### Recommended UI Flow

```
┌─────────────────────────────────────┐
│  Select Architecture:               │
│  ( ) Enterprise v3                  │
│  (•) Intent-Based v2.0 (Recommended)│
└─────────────────────────────────────┘
         ↓
┌─────────────────────────────────────┐
│  Test Case:                         │
│  [text area]                        │
│  URL: [input]                       │
│  [x] Visible Browser                │
│  [Run Test]                         │
└─────────────────────────────────────┘
         ↓
┌─────────────────────────────────────┐
│  Status: Running                    │
│  Stage: executing                   │
│  Progress: ████░░ 60%               │
│  [Live Screenshot]                  │
└─────────────────────────────────────┘
         ↓
┌─────────────────────────────────────┐
│  ✅ Test Passed                     │
│  Total Intents: 5                   │
│  Success: 5/5 (100%)                │
│  Time: 12.3s                        │
│  Avg/Intent: 2.5s                   │
│  [View Details]                     │
└─────────────────────────────────────┘
```

---

## 📦 Backend Changes Made

### 1. New Endpoint Added

File: `backend/routers/ui_automation.py`

Added:
- `IntentBasedRequest` model
- `POST /ui/intent-based/run` endpoint
- Background task execution
- Chat integration
- Metrics recording

### 2. Imports Updated

The endpoint uses:
```python
from services.ui_automation.core import execute_test_case_with_intents
```

All intent system components are accessible via:
```python
from services.ui_automation.core import (
    Intent,
    IntentType,
    IntentExecutor,
    execute_test_case_with_intents,
    FlowRouter,
    StateValidator,
    CTAClassifier,
)
```

---

## 🧪 Testing the Integration

### Manual Test

```bash
curl -X POST http://localhost:8000/ui/intent-based/run \
  -H "Content-Type: application/json" \
  -d '{
    "test_case": "Search for lg tv",
    "url": "https://www.lg.com/in",
    "visible_browser": true
  }'
```

### Expected Response

```json
{
  "success": true,
  "test_case_id": 1,
  "chat_id": 5,
  "status": "running",
  "architecture": "intent-based-v2",
  "message": "Intent-based automation started in background"
}
```

### Check Status

```bash
curl http://localhost:8000/ui/current-run/status
```

Response:
```json
{
  "running": true,
  "stage": "executing",
  "test_case_id": 1
}
```

---

## 📊 Metrics Available

After execution completes, you can fetch metrics:

```bash
curl http://localhost:8000/ui/results/{execution_id}
```

The result includes:
- Total intents
- Success/failure count
- Execution time
- Phase usage stats (flow executors vs resolver)
- Intent breakdown
- State validation results

---

## 🎨 UI/UX Recommendations

### 1. Badge System

Show architecture being used:
- 🎯 **Intent-Based v2.0** (green badge)
- 🏢 **Enterprise v3** (blue badge)

### 2. Progress Stages

Map backend stages to user-friendly labels:

| Backend Stage | UI Label |
|--------------|----------|
| `intent_planning` | "📋 Planning Intents" |
| `executing` | "🎬 Executing Tests" |
| `complete` | "✅ Complete" |
| `error` | "❌ Failed" |

### 3. Results Display

Show intent-based metrics:
```
✅ Test Passed

📊 Execution Summary
━━━━━━━━━━━━━━━━━━━━
Total Intents:     5
Success:           5/5 (100%)
Total Time:        12.3s
Avg Time/Intent:   2.5s

📈 Phase Usage
━━━━━━━━━━━━━━━━━━━━
Flow Executors:    4 (80%)
Resolver Fallback: 1 (20%)
Retries:           0 (0%)

📋 Intent Breakdown
━━━━━━━━━━━━━━━━━━━━
1. ✅ SEARCH_PRODUCT (2.1s) [validated]
2. ✅ SELECT_PRODUCT (3.5s) [validated]
3. ✅ ADD_TO_CART (2.8s) [validated]
4. ✅ SET_PINCODE (2.2s) [validated]
5. ✅ SELECT_DELIVERY (1.7s) [validated]
```

---

## 🚀 Next Steps for UI Team

### Phase 1: Basic Integration (1-2 days)

- [ ] Add "Intent-Based Test" button/tab
- [ ] Create request form (test case + URL)
- [ ] Show execution status
- [ ] Display results

### Phase 2: Enhanced UX (2-3 days)

- [ ] Architecture selector (v2.0 vs v3)
- [ ] Live progress monitoring
- [ ] Intent breakdown visualization
- [ ] Metrics dashboard
- [ ] Chat integration for progress

### Phase 3: Advanced Features (3-5 days)

- [ ] Side-by-side comparison (v2.0 vs v3)
- [ ] Template library (common test patterns)
- [ ] Intent history
- [ ] Performance analytics
- [ ] Export results

---

## 💡 Sample Test Cases for UI

Provide these as templates:

### 1. E-commerce Search
```
Search for laptop, select Dell XPS 15, add to cart
```

### 2. Full Checkout Flow
```
Search for smartphone
Select iPhone 15 Pro
Add to cart
Enter pincode 110001
Select express delivery
```

### 3. Product Comparison
```
Search for lg refrigerator
Select LG 260L Double Door
View details
```

---

## 🎓 Training Materials Needed

Create:
1. **User Guide**: How to write effective test cases
2. **Demo Video**: Intent-based automation in action
3. **FAQ**: Common questions about intent system
4. **Comparison**: Intent-based vs Enterprise v3
5. **Best Practices**: Writing test cases for maximum success

---

## ✅ Integration Checklist

- [x] Backend endpoint created (`/ui/intent-based/run`)
- [x] Background task execution implemented
- [x] Chat integration added
- [x] Status polling endpoint available
- [x] Metrics recording implemented
- [x] Error handling complete
- [x] Documentation created
- [ ] Frontend UI components
- [ ] Testing with UI team
- [ ] User documentation
- [ ] Demo video/screenshots

---

## 📞 Support

For UI integration help:
- See [INTENT_QUICKSTART.md](INTENT_QUICKSTART.md) for quick reference
- See [INTENT_BASED_ARCHITECTURE.md](INTENT_BASED_ARCHITECTURE.md) for details
- Check [INTENT_VISUAL_FLOWS.md](INTENT_VISUAL_FLOWS.md) for flow diagrams

---

**Status**: ✅ Backend Integration Complete  
**Ready For**: UI Development  
**Date**: February 17, 2026  
**Version**: 2.0 (Intent-Based)
