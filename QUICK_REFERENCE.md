# State-Driven Architecture - Quick Reference

## 🚀 Quick Start

### Run with New Architecture
```python
from services.ui_automation.enterprise_flow_engine import EnterpriseFlowEngine

engine = EnterpriseFlowEngine(
    mode="STATE_DRIVEN",  # New intelligent mode
    structured_plan=your_test_plan,
    headless=False
)

result = await engine.run("https://your-url.com")
print(f"Success: {result.success} | Health: {result.health_score}/100")
```

### Fallback to Legacy
```python
engine = EnterpriseFlowEngine(
    mode="INSTRUCTION",  # Legacy text-based mode
    structured_plan=your_test_plan
)
```

---

## 📋 Architecture Layers

| Layer | File | Purpose | Key Method |
|-------|------|---------|------------|
| 1 | `page_intelligence.py` | Detect page type | `detect_page_type()` |
| 2 | `intent_normalizer.py` | English → Intent | `normalize()` |
| 3 | `context_executor.py` | Smart execution | `execute_intent()` |
| 4 | `state_validator.py` | Validate changes | `validate()` |
| 5 | `product_matcher.py` | Find products | `find_best_product_match()` |

---

## 🎯 Supported Intents

### Shopping
- `SEARCH_PRODUCT` - Search for items
- `SELECT_PRODUCT` - Pick specific product
- `BUY_PRODUCT` - Buy now button
- `ADD_TO_CART` - Add to basket
- `VIEW_CART` - Open cart
- `CHECKOUT` - Proceed to checkout

### Cart & Checkout
- `UPDATE_QUANTITY` - Change item count
- `REMOVE_ITEM` - Delete from cart
- `APPLY_COUPON` - Use discount code
- `GUEST_CHECKOUT` - Continue as guest

### Forms
- `ENTER_SHIPPING_INFO` - Delivery address
- `ENTER_BILLING_INFO` - Payment address
- `VERIFY_DELIVERY` - Check pincode
- `SELECT_DELIVERY_METHOD` - Choose shipping

### Generic
- `NAVIGATE` - Go to URL
- `CLICK_ELEMENT` - Click anything
- `TYPE_TEXT` - Enter text
- `WAIT` - Pause execution

---

## 🔍 Page Types Detected

| Page Type | Signals | Example |
|-----------|---------|---------|
| `HOME` | Hero banner, featured products | lg.com/in |
| `CATEGORY` | Category nav, subcategories | /air-solutions |
| `PRODUCT_LISTING` | Product cards (3+), filters, sorting | /air-conditioners |
| `PRODUCT_DETAIL` | Add to cart, price, single product | /ac-xyz123 |
| `SEARCH_RESULTS` | Search results text, product cards | /search?q=tv |
| `CART` | Cart items, total, checkout button | /cart |
| `CHECKOUT` | Billing form, payment method | /checkout |
| `LOGIN` | Email + password inputs | /login |
| `MODAL` | Dialog overlay | Cookie banner, search popup |

---

## 🧮 Product Matching

### Similarity Score Calculation
```
Base Fuzzy Score (0-1):
  - Ratio: 20%
  - Partial: 30%
  - Token Sort: 25%
  - Token Set: 25%

Feature Boosts:
  - Brand match: +15%
  - Model match: +20%
  - Capacity match: +15%
  - Number match: +10%
  - Keyword match: +10%

Final Score = Fuzzy (60%) + Features (40%)
```

### Thresholds
- `0.60` - Minimum match
- `0.85` - Excellent match

---

## ✅ State Validations

### Validation Types

| Type | Checks | When |
|------|--------|------|
| `URL_CHANGE` | URL different | After navigation |
| `MODAL_OPENED` | Dialog visible | After click |
| `MODAL_CLOSED` | Dialog hidden | After close |
| `PAGE_LOAD` | DOM loaded | After navigation |
| `ELEMENT_VISIBLE` | Element appeared | After action |
| `ELEMENT_HIDDEN` | Element gone | After dismiss |
| `TEXT_CHANGED` | Content updated | After edit |
| `COUNT_CHANGED` | Item count changed | After add/remove |

---

## 📊 Result Metrics

### EnterpriseFlowResult
```python
result = {
    "success": bool,              # Overall success
    "goal_reached": bool,         # Goal achieved
    "steps_executed": int,        # Steps completed
    "instructions_compiled": int, # Total steps
    "failed_at": int,            # First failure step
    "execution_time": float,      # Total seconds
    "health_score": float,        # 0-100 quality
    "screenshots": list,          # Failure screenshots
    "error": str,                # Error message
}
```

### Health Score
```
Score = (success_rate * 100) - (validation_failures * 5)
```

---

## 🐛 Debugging

### Enable Detailed Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Logs For
1. **Page Detection**
   ```
   🔍 Detecting page type...
   ✅ Detected: PageState(type=PRODUCT_LISTING, confidence=0.85)
   ```

2. **Intent Normalization**
   ```
   🧠 Normalizing: 'click on buynow for LG AC'
   ✅ Normalized to: Intent(BUY_PRODUCT, target='LG AC')
   ```

3. **Product Matching**
   ```
   🔍 Finding product: 'LG 108cm tv'
   Found 12 product containers
   ✅ Best match: LG 108 cm Smart TV (score: 0.92)
   ```

4. **State Validation**
   ```
   🔍 Validating 2 rules...
   ✅ URL_CHANGE: URL changed
   ✅ ELEMENT_VISIBLE: Element visible
   ```

---

## 🔧 Customization

### Add Custom Intent Pattern
Edit `intent_normalizer.py`:
```python
INTENT_PATTERNS = [
    (r'your_pattern_here', ActionIntent.YOUR_ACTION),
    # ... existing patterns
]
```

### Adjust Similarity Threshold
Edit `product_matcher.py`:
```python
self.match_threshold = 0.60  # Lower = more matches
self.excellent_threshold = 0.85
```

### Add Page Detection Signal
Edit `page_intelligence.py`:
```python
signals["your_signal"] = await self.page.locator(
    'your-selector'
).count() > 0
```

---

## 🚨 Troubleshooting

### Issue: Page type not detected correctly
**Solution:** Check signals in logs, adjust detection rules

### Issue: Product not matched
**Solution:** Check similarity score, lower threshold or improve name

### Issue: State validation fails but action succeeded
**Solution:** Adjust validation rules or make them optional

### Issue: Slower than INSTRUCTION mode
**Solution:** Normal (1-2s overhead), worth it for reliability

---

## 📈 Performance Tips

1. **Use headless=True for speed**
   ```python
   engine = EnterpriseFlowEngine(headless=True)
   ```

2. **Reduce validation timeout**
   ```python
   ValidationRule(StateChangeType.PAGE_LOAD, timeout=3000)
   ```

3. **Skip optional validations**
   ```python
   ValidationRule(..., required=False)
   ```

---

## 🎯 Best Practices

### 1. Write Clear Intent Descriptions
```python
# ❌ Bad
{"action": "click button"}

# ✅ Good
{"action": "buy LG 4 Star (1.5 Ton) Split AC"}
```

### 2. Provide Context in Plans
```python
{
    "action": "click buy now",
    "locator_hint": "Buy Now button for LG AC",  # Helps!
    "ui_intent": "click"
}
```

### 3. Use Specific Product Names
```python
# ❌ Vague
"buy ac"

# ✅ Specific
"buy LG 4 Star 1.5 Ton Split Air Conditioner"
```

### 4. Let Validation Catch Issues
```python
# Don't:
await page.click()
await page.wait_for_timeout(5000)  # Blind wait

# Do:
result = await executor.execute_intent(intent)
# Validation happens automatically
```

---

## 📝 Test Cases

### Simple Test
```python
{
    "steps": [
        {"action": "navigate to https://example.com"},
        {"action": "search for laptop"},
        {"action": "click first product"}
    ]
}
```

### Complex Test
```python
{
    "steps": [
        {"action": "navigate to https://lg.com/in"},
        {"action": "click on Air Solutions"},
        {"action": "click on Split Air Conditioners"},
        {"action": "buy LG 4 Star (1.5 Ton) Split AC", 
         "locator_hint": "Buy Now for LG 4 Star AC"},
        {"action": "enter pincode 500032"},
        {"action": "click on Check"},
        {"action": "select free delivery option"},
        {"action": "click on Checkout"},
        {"action": "continue as guest"}
    ]
}
```

---

## 🎓 Learning Resources

### Documentation
- `STATE_DRIVEN_ARCHITECTURE.md` - Full architecture guide
- `STATE_DRIVEN_IMPLEMENTATION_COMPLETE.md` - Implementation details
- This file - Quick reference

### Code Examples
- `test_state_driven.py` - Test suite with examples

### Core Files to Study
1. `page_intelligence.py` - How page detection works
2. `context_executor.py` - How execution logic works
3. `product_matcher.py` - How product matching works

---

## 💡 Key Concepts

### Context Over Text
```python
# Text-based (OLD)
page.click("Buy Now")  # Blind

# Context-aware (NEW)
if page_type == PRODUCT_LISTING:
    product_card = find_product("LG AC")
    product_card.click("Buy Now")
```

### Intent Over Instructions
```python
# Instruction (OLD)
CLICK('Buy Now')

# Intent (NEW)
BUY_PRODUCT(target="LG 4 Star AC")
→ System figures out HOW based on context
```

### Validation Over Assumptions
```python
# Assumption (OLD)
await click()
# Assume it worked

# Validation (NEW)
await click()
validate_url_changed()
validate_element_visible()
```

---

## 🎯 Success Checklist

- [ ] MODE set to STATE_DRIVEN
- [ ] Test plans have clear descriptions
- [ ] Product names are specific
- [ ] Page types detected correctly
- [ ] Intents normalized properly
- [ ] Products matched accurately
- [ ] State validations passing
- [ ] Health score > 85

---

## 📞 Support

If issues persist:
1. Check logs for each layer
2. Verify page detection
3. Check intent normalization
4. Review product matching scores
5. Examine validation results
6. Try INSTRUCTION mode as fallback

---

**Quick Ref Version: 1.0 | Last Updated: 2026-02-16**
