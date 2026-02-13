# Quick Start Guide - Phase 1 Features

## 🚀 Using the New Fuzzy Matching & Validation Features

### Installation

No additional dependencies needed! Phase 1 uses only Python standard library and existing packages.

---

## Feature 1: Fuzzy Text Matching

### Basic Usage

```python
from services.ui_automation.utils.fuzzy_matcher import FuzzyMatcher

# Initialize with threshold (0.0 - 1.0)
matcher = FuzzyMatcher(threshold=0.65)

# Check if two strings match
if matcher.is_match("grey shirt", "Grey jacket"):
    print("Match found!")
    
# Get similarity score
score = matcher.similarity("grey shirt", "Grey jacket")
print(f"Similarity: {score:.2f}")  # 0.57
```

### Finding Best Match

```python
query = "add to cart"
candidates = ["Add to Cart", "Add to Bag", "Buy Now", "Wishlist"]

match = matcher.find_best_match(query, candidates)
if match:
    matched_text, score = match
    print(f"Best match: '{matched_text}' (score: {score:.2f})")
    # Output: Best match: 'Add to Cart' (score: 0.95)
```

### Finding Multiple Matches

```python
query = "checkout"
candidates = ["Checkout", "Proceed to Checkout", "Complete Order", "Pay Now"]

matches = matcher.find_all_matches(query, candidates, top_n=3)
for text, score in matches:
    print(f"  - {text}: {score:.2f}")
# Output:
#   - Checkout: 1.00
#   - Proceed to Checkout: 0.82
```

### Convenience Functions

```python
from services.ui_automation.utils.fuzzy_matcher import fuzzy_match, find_fuzzy_match

# Quick boolean check
if fuzzy_match("Login", "login"):
    print("Match!")

# Quick best match
match = find_fuzzy_match("cart", ["Cart", "Checkout", "Orders"])
print(match)  # ("Cart", 1.0)
```

---

## Feature 2: Selector Validation

### Pre-Execution Validation

```python
from services.ui_automation.utils.selector_validator import SelectorValidator
import asyncio

async def validate_my_test():
    validator = SelectorValidator(fuzzy_threshold=0.65, headless=True)
    
    steps = [
        {
            "action": "click",
            "selector": "button:has-text('grey shirt')",
            "description": "Click on product"
        },
        {
            "action": "fill",
            "selector": "input[name='email']",
            "value": "test@example.com",
            "description": "Enter email"
        }
    ]
    
    result = await validator.validate_script(
        url="https://www.saucedemo.com",
        steps=steps
    )
    
    print(f"Validation passed: {result['validation_passed']}")
    print(f"Invalid selectors: {len(result['invalid_selectors'])}")
    print(f"Auto-fixed: {len(result['auto_fixed'])}")
    
    if result['auto_fixed']:
        print("\nAuto-fixed selectors:")
        for fix in result['auto_fixed']:
            print(f"  {fix['original']} → {fix['fixed']}")
    
    if result['validation_passed']:
        # Safe to execute test
        return result['validated_steps']
    else:
        # Review issues
        for invalid in result['invalid_selectors']:
            print(f"❌ {invalid['description']}: {invalid['reason']}")

# Run validation
asyncio.run(validate_my_test())
```

### Quick Validation

```python
from services.ui_automation.utils.selector_validator import validate_selectors

async def quick_check():
    steps = [{"action": "click", "selector": "button:has-text('Login')"}]
    result = await validate_selectors("https://example.com", steps)
    return result['validation_passed']
```

---

## Feature 3: Enhanced Healing

The healer now automatically uses fuzzy matching when `failure_page_elements` is provided.

### In Your Test Runner

```python
from services.ui_automation.agents.healer.agent import HealerAgent

# Initialize with fuzzy matching enabled
healer = HealerAgent(
    use_playwright_agents=False,
    fuzzy_threshold=0.65  # NEW: Fuzzy matching threshold
)

# When healing a failed test
result = healer.heal(
    script=failed_script,
    error=error_message,
    db=db_session,
    failed_locator=failed_selector,
    # NEW: Provide page elements for fuzzy matching
    failure_page_elements=[
        {"tag": "button", "text": "Grey jacket", "ariaLabel": ""},
        {"tag": "button", "text": "Add to Cart", "ariaLabel": "Add Grey jacket to cart"}
    ],
    failure_url=current_url,
    plan=test_plan,
    failed_step_index=step_index
)

if result['healed']:
    print(f"✅ Healed using: {result['strategy']}")
    if result['strategy'] == 'fuzzy':
        print(f"   Fuzzy matched: {result['original_selector']} → {result['healed_locator']}")
    
    # Execute healed script
    execute_test(result['healed_script'])
else:
    print("❌ Could not heal")
```

---

## Feature 4: Timeout Reduction

The executor now fails fast at 120 seconds instead of 600 seconds.

### No Code Changes Required

The timeout is automatically applied. Tests that would hang for 10 minutes now fail at 2 minutes.

```python
from services.ui_automation.engine.executor import PlaywrightExecutor

executor = PlaywrightExecutor()

# Timeout is now 120s (was 600s)
result = executor.execute(
    script=test_script,
    test_case_id=123,
    capture_step_screenshots=True,
    headed=True
)
```

---

## Integration Example: Complete Flow

### Validate → Execute → Heal

```python
import asyncio
from services.ui_automation.utils.selector_validator import SelectorValidator
from services.ui_automation.engine.executor import PlaywrightExecutor
from services.ui_automation.agents.healer.agent import HealerAgent

async def run_test_with_validation_and_healing(test_case):
    """Complete flow with Phase 1 features"""
    
    # Step 1: Validate selectors before execution
    print("🔍 Validating selectors...")
    validator = SelectorValidator(fuzzy_threshold=0.65)
    
    validation = await validator.validate_script(
        url=test_case['target_url'],
        steps=test_case['steps']
    )
    
    if not validation['validation_passed']:
        print(f"⚠️  Found {len(validation['invalid_selectors'])} invalid selectors")
        print(f"✅ Auto-fixed {len(validation['auto_fixed'])} selectors")
    
    # Use validated steps
    validated_steps = validation['validated_steps']
    
    # Step 2: Generate script from validated steps
    script = generate_playwright_script(validated_steps)
    
    # Step 3: Execute with 120s timeout
    print("▶️  Executing test...")
    executor = PlaywrightExecutor()
    
    result = executor.execute(
        script=script,
        test_case_id=test_case['id'],
        capture_step_screenshots=True,
        headed=True
    )
    
    # Step 4: If failed, try healing with fuzzy matching
    if result['status'] == 'failed':
        print("🔧 Attempting to heal...")
        
        healer = HealerAgent(fuzzy_threshold=0.65)
        
        heal_result = healer.heal(
            script=script,
            error=result['error'],
            db=db_session,
            failure_page_elements=result.get('page_elements'),
            failure_url=result.get('failure_url'),
            plan=test_case,
            failed_step_index=result.get('failed_step')
        )
        
        if heal_result['healed']:
            print(f"✅ Healed using {heal_result['strategy']} strategy")
            
            # Retry with healed script
            result = executor.execute(
                script=heal_result['healed_script'],
                test_case_id=test_case['id'],
                capture_step_screenshots=True,
                headed=True
            )
    
    return result

# Usage
test_case = {
    'id': 1,
    'target_url': 'https://www.saucedemo.com',
    'steps': [
        {"action": "goto", "url": "https://www.saucedemo.com"},
        {"action": "fill", "selector": "input[name='user-name']", "value": "standard_user"},
        {"action": "fill", "selector": "input[name='password']", "value": "secret_sauce"},
        {"action": "click", "selector": "input[type='submit']"}
    ]
}

result = asyncio.run(run_test_with_validation_and_healing(test_case))
print(f"Final result: {result['status']}")
```

---

## Configuration Options

### Fuzzy Matcher Thresholds

```python
# Lenient (catches more matches, more false positives)
matcher = FuzzyMatcher(threshold=0.55)

# Balanced (recommended)
matcher = FuzzyMatcher(threshold=0.65)

# Strict (fewer matches, higher confidence)
matcher = FuzzyMatcher(threshold=0.75)
```

### Validator Settings

```python
# Headless (faster, for CI/CD)
validator = SelectorValidator(headless=True)

# Headed (see what's happening, for debugging)
validator = SelectorValidator(headless=False)

# Custom fuzzy threshold
validator = SelectorValidator(fuzzy_threshold=0.70)
```

### Healer Settings

```python
# Without Playwright agents (faster)
healer = HealerAgent(use_playwright_agents=False, fuzzy_threshold=0.65)

# With Playwright agents (more features)
healer = HealerAgent(use_playwright_agents=True, fuzzy_threshold=0.65)
```

---

## Testing Your Changes

### Run Phase 1 Tests

```bash
cd backend
python -m pytest tests/test_phase1_implementation.py -v
```

### Expected Output

```
============================= 13 passed in 0.38s ==============================
✅ TestFuzzyMatcher::test_exact_match PASSED
✅ TestFuzzyMatcher::test_case_insensitive PASSED
✅ TestFuzzyMatcher::test_punctuation_normalization PASSED
✅ TestFuzzyMatcher::test_partial_match PASSED
✅ TestFuzzyMatcher::test_find_best_match PASSED
✅ TestFuzzyMatcher::test_find_all_matches PASSED
✅ TestFuzzyMatcher::test_no_match_below_threshold PASSED
✅ TestFuzzyMatcher::test_convenience_functions PASSED
✅ TestHealerIntegration::test_fuzzy_match_extraction PASSED
✅ TestHealerIntegration::test_fuzzy_match_with_page_elements PASSED
✅ TestSelectorValidator::test_validator_initialization PASSED
✅ TestSelectorValidator::test_text_extraction PASSED
✅ TestSelectorValidator::test_selector_generation PASSED
```

---

## Troubleshooting

### Issue: Fuzzy matcher not finding matches

**Solution:** Lower the threshold

```python
# Try lower threshold
matcher = FuzzyMatcher(threshold=0.55)
```

### Issue: Validator taking too long

**Solution:** Use headless mode and reduce page load wait

```python
validator = SelectorValidator(headless=True)
result = await validator.validate_script(url, steps, wait_for_load=False)
```

### Issue: Healer not using fuzzy matching

**Solution:** Ensure failure_page_elements is provided

```python
# Make sure to pass page elements
result = healer.heal(
    script=script,
    error=error,
    db=db_session,
    failure_page_elements=page_elements  # ← This is required!
)
```

---

## Performance Tips

1. **Cache validation results:** If testing same page multiple times, cache validated selectors

2. **Batch validation:** Validate multiple scripts in parallel using asyncio

3. **Adjust thresholds:** Higher threshold = faster (fewer candidates checked)

4. **Use headless mode:** Much faster than headed for validation

---

## Next Steps

After Phase 1, consider:

1. **Collect metrics:** Track fuzzy match success rates
2. **Tune thresholds:** Adjust based on your domain
3. **Add semantic matching:** Use embeddings for "buy" ≈ "purchase"
4. **Implement Phase 2:** Journey extraction, focused crawling, grounded planning

---

## Support

For issues or questions:
1. Check test file: `backend/tests/test_phase1_implementation.py`
2. Review implementation: `PHASE1_IMPLEMENTATION_COMPLETE.md`
3. See full proposal: `UI_AUTOMATION_FAILURE_ANALYSIS.md`
