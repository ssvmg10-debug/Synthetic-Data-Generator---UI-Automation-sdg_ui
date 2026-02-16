# LG India – 20 complex test cases

Use these as **raw_input** with **POST /ui/run** to exercise the full guest checkout flow.

## Coverage

| # | Product type        | Price band   | City / Pincode   |
|---|---------------------|-------------|------------------|
| 1 | 108cm TV            | Under 30k    | Hyderabad 500032 |
| 2 | Washing machine 7kg | Under 50k    | Delhi 110001     |
| 3 | Double door fridge  | Under 25k    | Mumbai 400001    |
| 4 | 1.5 ton AC          | Under 40k    | Bangalore 560001 |
| 5 | OLED TV 139cm       | Under 1L     | Chennai 600001   |
| 6 | Microwave           | Under 15k    | Pune 411001      |
| 7 | RO water purifier   | Under 20k    | Kolkata 700001   |
| 8 | Dryer 9kg           | Under 60k    | Ahmedabad 380001 |
| 9 | Smart TV 125cm      | Under 45k    | Jaipur 302001    |
|10 | Bottom freezer fridge | Under 35k  | Lucknow 226001   |
|11 | Inverter AC 1 ton   | Under 35k    | Coimbatore 641001|
|12 | Front load 8kg      | Under 55k    | Chandigarh 160001|
|13 | Mini fridge         | Under 18k    | Kochi 682001     |
|14 | 80cm TV             | Under 20k    | Nagpur 440001    |
|15 | French door fridge  | Under 80k    | Surat 395001     |
|16 | Dual inverter AC    | Under 45k    | Indore 452001    |
|17 | Semi-auto washer    | Under 12k    | Bhopal 462001    |
|18 | 4K TV 139cm         | Under 55k    | Vadodara 390001  |
|19 | Top load 6.5kg      | Under 22k    | Visakhapatnam 530001|
|20 | Split AC 1 ton      | Under 30k    | Thiruvananthapuram 695001|

## How to run

### Single test (e.g. from UI or curl)

```bash
curl -X POST http://localhost:8000/ui/run \
  -H "Content-Type: application/json" \
  -d '{"raw_input": "Navigate to https://www.lg.com/in. Accept cookies. Search for lg 108cm tv. Click Buy Now for a product under 30000. Enter pincode 500032 and click Check. Select free delivery. Proceed to Checkout. Continue as guest. Fill billing address."}'
```

### Load from JSON (Python)

```python
import json
with open("test_cases/lg_india_test_cases.json") as f:
    data = json.load(f)
for tc in data["test_cases"]:
    raw_input = tc["raw_input"]
    # POST to /ui/run with raw_input
```

### Optional: run all via script

From `backend`:

```bash
python test_cases/run_lg_test_cases.py
```

(Requires backend running and optional `BASE_URL` env for API base.)
