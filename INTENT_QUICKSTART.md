# Intent-Based Automation - Quick Start Guide

## 🚀 Quick Start (2 minutes)

### 1. Install Dependencies

```bash
pip install fuzzywuzzy python-Levenshtein
```

### 2. Run Test

```bash
python test_intent_based_automation.py
```

### 3. Use in Your Code

```python
from services.ui_automation.core import execute_test_case_with_intents

async def test():
    result = await execute_test_case_with_intents(
        page=page,
        test_case="Search for laptop, select Dell XPS, add to cart",
        url="https://example.com"
    )
    print(f"Success: {result['success']}")
```

---

## 📖 Common Use Cases

### Search Product

```python
test_case = "Search for 'lg refrigerator'"
```

Generated intents:
```python
Intent(NAVIGATE, url="...")
Intent(SEARCH_PRODUCT, query="lg refrigerator")
```

### Select Product

```python
test_case = "Search for laptop, select Dell XPS 15"
```

Generated intents:
```python
Intent(NAVIGATE, url="...")
Intent(SEARCH_PRODUCT, query="laptop")
Intent(SELECT_PRODUCT, product_name="Dell XPS 15")
```

### Add to Cart

```python
test_case = "Search for phone, select iPhone 15, add to cart"
```

Generated intents:
```python
Intent(NAVIGATE, url="...")
Intent(SEARCH_PRODUCT, query="phone")
Intent(SELECT_PRODUCT, product_name="iPhone 15")
Intent(ADD_TO_CART)
```

### Checkout with Pincode

```python
test_case = """
Search for tv
Select LG 55 inch
Add to cart
Enter pincode 500032
Select free delivery
"""
```

Generated intents:
```python
Intent(NAVIGATE, url="...")
Intent(SEARCH_PRODUCT, query="tv")
Intent(SELECT_PRODUCT, product_name="LG 55 inch")
Intent(ADD_TO_CART)
Intent(SET_PINCODE, value="500032")
Intent(SELECT_DELIVERY_OPTION, option="free delivery")
```

---

## 🎯 Intent Types Cheat Sheet

| Intent | Required Params | Example |
|--------|----------------|---------|
| `NAVIGATE` | `url` | `Intent(NAVIGATE, url="https://example.com")` |
| `SEARCH_PRODUCT` | `query` | `Intent(SEARCH_PRODUCT, query="laptop")` |
| `SELECT_PRODUCT` | `product_name` | `Intent(SELECT_PRODUCT, product_name="Dell XPS")` |
| `ADD_TO_CART` | - | `Intent(ADD_TO_CART)` |
| `VIEW_CART` | - | `Intent(VIEW_CART)` |
| `PROCEED_TO_CHECKOUT` | - | `Intent(PROCEED_TO_CHECKOUT)` |
| `SET_PINCODE` | `value` | `Intent(SET_PINCODE, value="500032")` |
| `SELECT_DELIVERY_OPTION` | `option` | `Intent(SELECT_DELIVERY_OPTION, option="free")` |
| `SELECT_PAYMENT_METHOD` | `option` | `Intent(SELECT_PAYMENT_METHOD, option="card")` |

---

## 🔧 Configuration

### Without Azure OpenAI (Rule-based)

No configuration needed. System automatically uses keyword-based planning.

### With Azure OpenAI (LLM-based)

Set environment variables:

```bash
export AZURE_OPENAI_API_KEY="your-key"
export AZURE_OPENAI_ENDPOINT="https://your-endpoint.openai.azure.com/"
export AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4"
```

---

## 📊 Understanding Results

```python
result = await execute_test_case_with_intents(page, test_case, url)

# Check success
if result['success']:
    print("✅ All intents succeeded")
else:
    print(f"❌ {result['failure_count']} intents failed")

# Get timing
print(f"Total time: {result['total_time']:.2f}s")
print(f"Avg per intent: {result['avg_time_per_intent']:.2f}s")

# See which phases were used
print(f"Flow executors: {result['phase_stats']['flow_executors']}")
print(f"Fallback resolver: {result['phase_stats']['resolver']}")
print(f"Retries: {result['phase_stats']['retry']}")

# Check individual intents
for intent in result['intent_breakdown']:
    if not intent['success']:
        print(f"Failed: {intent['intent']} - {intent['error']}")
```

---

## 🐛 Common Issues & Fixes

### Issue: "No intents generated"

**Cause:** Test case not understood

**Fix:** Use more explicit language
```python
# ❌ Bad
test_case = "Do the shopping thing"

# ✅ Good
test_case = "Search for laptop, select Dell XPS, add to cart"
```

### Issue: "Product not found"

**Cause:** Product name too specific or mismatched

**Fix:** Use shorter, more generic names
```python
# ❌ Too specific
product_name = "LG 4 Star (1.5 Ton) Split AC 2026 Model with WiFi RS-Q19YNZE"

# ✅ Generic (uses fuzzy matching)
product_name = "LG 4 Star Split AC"
```

### Issue: "CTA button not found"

**Cause:** Button text doesn't match expected patterns

**Fix:** Check page and update preferred_text
```python
# Manually create intent with preferred text
intent = Intent(
    intent=IntentType.ADD_TO_CART,
    element_text="Add to Bag"  # Site uses "Bag" not "Cart"
)
```

### Issue: "Timeout waiting for results"

**Cause:** Slow page load or network issues

**Fix:** Already handled - system uses domcontentloaded, not networkidle

### Issue: "Pincode field not found"

**Cause:** Non-standard field naming

**Fix:** System tries multiple strategies automatically. If still fails, check logs for attempted strategies.

---

## 💡 Pro Tips

### 1. Use Natural Language

The intent planner understands natural test cases:

```python
# All of these work:
"Search for laptop"
"search for laptop"
"Find laptop"
"Look for laptop"
```

### 2. Be Specific for Products

```python
# ✅ Good
"Select LG 55 inch OLED TV"

# ❌ Too vague
"Select TV"
```

### 3. Chain Multiple Actions

```python
test_case = """
Search for smartphone
Select iPhone 15 Pro
Add to cart
View cart
Enter pincode 110001
Select express delivery
"""
```

### 4. Check State Validation

```python
for intent in result['intent_breakdown']:
    if not intent['state_validated']:
        print(f"Warning: {intent['intent']} succeeded but state not validated")
```

---

## 🎓 Examples

### E-commerce Purchase Flow

```python
test_case = """
Search for gaming laptop
Select ASUS ROG Strix
Add to cart
Proceed to checkout
Enter pincode 560001
Select standard delivery
Select credit card payment
"""

result = await execute_test_case_with_intents(page, test_case, url)
```

### Search and Compare

```python
test_case = """
Search for refrigerator
Select LG 260L Double Door
"""

result = await execute_test_case_with_intents(page, test_case, url)
```

### Simple Search

```python
test_case = "Search for washing machine"

result = await execute_test_case_with_intents(page, test_case, url)
```

---

## 📞 Getting Help

1. **Check logs**: All components log extensively
2. **Enable debug**: `logging.basicConfig(level=logging.DEBUG)`
3. **Read docs**: See `INTENT_BASED_ARCHITECTURE.md`
4. **Test individual components**: Import and test flows directly

---

## ✅ Checklist

Before running your first test:

- [ ] Dependencies installed (`fuzzywuzzy`, `python-Levenshtein`)
- [ ] Playwright browsers installed (`playwright install`)
- [ ] Test case written in natural language
- [ ] Target URL specified
- [ ] (Optional) Azure OpenAI credentials configured

---

## 🚦 Next Steps

1. **Run the test script**: `python test_intent_based_automation.py`
2. **Try your own test case**: Modify the test script
3. **Integrate into your project**: Use `execute_test_case_with_intents`
4. **Read full documentation**: `INTENT_BASED_ARCHITECTURE.md`

---

## 📚 Key Files

| File | Purpose |
|------|---------|
| `intent_executor.py` | Main entry point |
| `intent_planner.py` | Natural language → intents |
| `flow_router.py` | Routes intents to executors |
| `flow_search.py` | Search functionality |
| `flow_product.py` | Product selection |
| `flow_checkout.py` | Checkout process |
| `state_validation.py` | State validation |
| `cta_classifier.py` | Button scoring |

---

**Quick Reference Card - Keep Handy!**

```python
# Import
from services.ui_automation.core import execute_test_case_with_intents

# Execute
result = await execute_test_case_with_intents(page, test_case, url)

# Check
if result['success']:
    print(f"✅ Done in {result['total_time']:.2f}s")
else:
    print(f"❌ {result['failure_count']} failed")
```
