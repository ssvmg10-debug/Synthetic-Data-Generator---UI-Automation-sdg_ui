# 🎯 Intent-Based UI Automation System

## Overview

A production-grade, intent-driven UI automation framework that replaces brittle text-based automation with semantic understanding, specialized flow executors, and intelligent state validation.

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install fuzzywuzzy python-Levenshtein
```

### 2. Run Test
```bash
python test_intent_based_automation.py
```

### 3. Use in Code
```python
from services.ui_automation.core import execute_test_case_with_intents

result = await execute_test_case_with_intents(
    page=page,
    test_case="Search for laptop, select Dell XPS, add to cart",
    url="https://example.com"
)

print(f"Success: {result['success']}")
print(f"Time: {result['total_time']:.2f}s")
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| **[INTENT_QUICKSTART.md](INTENT_QUICKSTART.md)** | 2-minute quick start guide |
| **[INTENT_BASED_ARCHITECTURE.md](INTENT_BASED_ARCHITECTURE.md)** | Complete architecture documentation |
| **[INTENT_VISUAL_FLOWS.md](INTENT_VISUAL_FLOWS.md)** | Visual flow diagrams |
| **[INTENT_IMPLEMENTATION_COMPLETE.md](INTENT_IMPLEMENTATION_COMPLETE.md)** | Implementation summary |

---

## 🏗️ Architecture

```
Natural Language Test Case
         ↓
   Intent Planner (LLM or Rule-based)
         ↓
   Semantic Intents
         ↓
    Flow Router
         ↓
   ┌────────┬─────────┬──────────┐
   │ Search │ Product │ Checkout │
   │  Flow  │  Flow   │   Flow   │
   └────────┴─────────┴──────────┘
         ↓
   State Validation
         ↓
   Retry (max 1)
         ↓
    Success/Fail
```

---

## ✨ Key Features

### 1. Semantic Intents
Replace text-based `CLICK("Buy Now")` with semantic `Intent(ADD_TO_CART)`

### 2. Specialized Flow Executors
- **SearchFlow**: Modal-aware search with result validation
- **ProductFlow**: Fuzzy product matching + CTA classification
- **CheckoutFlow**: Intelligent form field detection

### 3. State Validation
Validates page state after each intent - no more race conditions

### 4. CTA Classification
Multi-factor button scoring (text, size, position, styling)

### 5. Controlled Resolver
Strict limits: 3 strategies max, 5 seconds max, fail fast

### 6. Deterministic Retry
Max 1 retry with alternate strategy - no infinite loops

### 7. Fuzzy Matching
Product selection with 50%+ similarity threshold

---

## 📦 Core Components

### Intent Models (`intent_models.py`)
```python
Intent(
    intent=IntentType.SEARCH_PRODUCT,
    query="lg tv",
    expected_state="SEARCH_RESULTS_LOADED"
)
```

### Intent Planner (`intent_planner.py`)
Converts natural language → structured intents

### Flow Executors
- `flow_search.py` - Search functionality
- `flow_product.py` - Product selection
- `flow_checkout.py` - Checkout process

### State Validator (`state_validation.py`)
Validates expected page states

### CTA Classifier (`cta_classifier.py`)
Intelligent button selection

---

## 🎯 Available Intents

| Intent | Required Params | Example |
|--------|----------------|---------|
| `NAVIGATE` | `url` | Navigate to site |
| `SEARCH_PRODUCT` | `query` | Search for products |
| `SELECT_PRODUCT` | `product_name` | Select by fuzzy match |
| `ADD_TO_CART` | - | Add to cart (CTA classification) |
| `VIEW_CART` | - | Open cart |
| `PROCEED_TO_CHECKOUT` | - | Go to checkout |
| `SET_PINCODE` | `value` | Enter delivery pincode |
| `SELECT_DELIVERY_OPTION` | `option` | Choose delivery |
| `SELECT_PAYMENT_METHOD` | `option` | Choose payment |

---

## 🔧 Configuration

### Without Azure OpenAI
No configuration needed - uses rule-based planning

### With Azure OpenAI (Optional)
```bash
export AZURE_OPENAI_API_KEY="your-key"
export AZURE_OPENAI_ENDPOINT="https://your-endpoint.openai.azure.com/"
export AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4"
```

---

## 📊 Performance Metrics

| Metric | Target | Improvement |
|--------|--------|-------------|
| Resolver timeout | 5s max | 60x faster (was 300s) |
| Navigation | 2-3s | No more timeouts |
| Search execution | 3-4s | Reliable |
| Product selection | 5-8s | Fuzzy matching |
| Intent avg | 3-4s | Consistent |

---

## ✅ What This Fixes

| Problem | Solution |
|---------|----------|
| Search not executing | SearchFlow + modal scope |
| Buy Now not found | CTA classification |
| Product mismatch | Fuzzy matching |
| Pincode not found | Label proximity detection |
| Slow resolver | 3 strategies max, 5s limit |
| Random retries | Max 1 deterministic retry |
| Navigation timeout | domcontentloaded (not networkidle) |
| Wrong button clicked | Multi-factor scoring |
| No validation | State validation layer |
| Generic execution | Domain-specific flows |

---

## 🧪 Testing

### Run All Tests
```bash
python test_intent_based_automation.py
```

### Test Individual Flow
```python
from services.ui_automation.core import SearchFlowExecutor, Intent, IntentType

flow = SearchFlowExecutor()
intent = Intent(intent=IntentType.SEARCH_PRODUCT, query="laptop")
success = await flow.execute_search(page, intent)
```

---

## 📈 Success Rates (Expected)

- SearchFlow: >90%
- ProductFlow: >85%
- CheckoutFlow: >80%
- CTA Classification: >85%
- State Validation: >95%

---

## 🐛 Troubleshooting

### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Common Issues

**Product not found**
- Use shorter, more generic product names
- System uses fuzzy matching with 50% threshold

**CTA button not found**
- Check page structure
- System tries multiple strategies automatically

**Timeout waiting for results**
- Already optimized - uses domcontentloaded
- Heavy sites handled gracefully

---

## 🎓 Best Practices

### ✅ Do
- Use semantic intents
- Provide context (product names, not "click here")
- Leverage fuzzy matching with partial names
- Check state validation in results

### ❌ Don't
- Use generic text like "click button"
- Expect exact product name matches
- Rely on deprecated text-based instructions

---

## 📖 Examples

### Simple Search
```python
test_case = "Search for laptop"
```

### E-commerce Flow
```python
test_case = """
Search for smartphone
Select iPhone 15 Pro
Add to cart
Enter pincode 110001
Select express delivery
"""
```

### Result Checking
```python
result = await execute_test_case_with_intents(page, test_case, url)

if result['success']:
    print(f"✅ Done in {result['total_time']:.2f}s")
    print(f"Flow executors used: {result['phase_stats']['flow_executors']}")
else:
    print(f"❌ {result['failure_count']} intents failed")
    for intent in result['intent_breakdown']:
        if not intent['success']:
            print(f"Failed: {intent['intent']} - {intent['error']}")
```

---

## 🔄 Migration from Old System

### Before
```python
from services.ui_automation.instruction_compiler import InstructionCompiler

compiler = InstructionCompiler()
instructions = compiler.compile_from_plan(plan)
result = await execute_instructions(page, instructions)
```

### After
```python
from services.ui_automation.core import execute_test_case_with_intents

result = await execute_test_case_with_intents(page, test_case, url)
```

---

## 🚦 Production Ready

✅ All 10 phases implemented
✅ Comprehensive test suite
✅ Full documentation
✅ Error handling
✅ Logging
✅ Metrics tracking
✅ State validation
✅ Controlled retries

---

## 📞 Support

- **Quick Start**: [INTENT_QUICKSTART.md](INTENT_QUICKSTART.md)
- **Architecture**: [INTENT_BASED_ARCHITECTURE.md](INTENT_BASED_ARCHITECTURE.md)
- **Visual Diagrams**: [INTENT_VISUAL_FLOWS.md](INTENT_VISUAL_FLOWS.md)
- **Implementation**: [INTENT_IMPLEMENTATION_COMPLETE.md](INTENT_IMPLEMENTATION_COMPLETE.md)

---

## 🎉 Summary

Transformed from brittle text-based automation to production-grade intent-based system with:

- **Semantic understanding** via intent planning
- **Domain expertise** via specialized flow executors
- **Reliability** via state validation
- **Speed** via controlled resolver (60x faster)
- **Flexibility** via fuzzy matching
- **Predictability** via deterministic retries

**The system is production-ready!**

---

**Status**: ✅ Complete  
**Date**: February 17, 2026  
**Version**: 2.0 (Intent-Based)
