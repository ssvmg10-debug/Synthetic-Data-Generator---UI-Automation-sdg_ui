# LG India E2E – Run Report

**Run:** 2026-02-13T09:29:56.612683Z

| Total | Passed | Failed | Pass rate |
|-------|--------|--------|----------|
| 25 | 0 | 25 | 0.0% |

## Target: 100%

> **Note:** This run failed because the **backend was not running** (connection refused on localhost:8000). To get real E2E results: start the backend (`cd backend && python -m uvicorn main:app --port 8000`), then run `python run_lg_test_cases.py --all --report reports/lg_e2e` again.

## Results

- **lg_01_buy_tv_under_30k** – FAIL  
  Buy TV under 30k – search, PDP, pincode, checkout
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_02_search_washing_machine_cart** – FAIL  
  Search washing machine, open PDP, add to cart, verify cart
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_03_tv_category_nav_add_cart** – FAIL  
  TV/Audio category → TV listing → product → add to cart
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_04_filter_oled_tv_verify_specs** – FAIL  
  Filter OLED TVs, select product, verify specs
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_05_search_soundbar_add_cart** – FAIL  
  Search soundbar, first result, add to cart, verify cart
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_06_guest_checkout_flow** – FAIL  
  Guest checkout – search, cart, checkout, guest, shipping
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_07_pincode_delivery_check** – FAIL  
  Refrigerator PDP – pincode 500032, check delivery
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_08_compare_two_products** – FAIL  
  Compare two TVs – comparison view and specs
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_09_cart_quantity_update** – FAIL  
  Add monitor to cart, increase quantity to 2, verify total
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_10_remove_item_from_cart** – FAIL  
  Add soundbar to cart, remove item, verify cart empty
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_11_refrigerator_category** – FAIL  
  Home Appliances → Refrigerators → open a product
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_12_laundry_washing_machine** – FAIL  
  Laundry / Washing machines listing and PDP
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_13_microwave_search** – FAIL  
  Search microwave, open first result, verify PDP
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_14_air_conditioner_category** – FAIL  
  Air Solutions → AC category → product
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_15_computing_monitors** – FAIL  
  Computing → Monitors → open product
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_16_laptop_gram** – FAIL  
  Computing → Laptop / LG gram – open product
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_17_support_warranty** – FAIL  
  Support → Warranty or Product Support
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_18_contact_us** – FAIL  
  Support → Contact Us
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_19_shop_offers** – FAIL  
  Shop → Offers / Promotions
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_20_tv_buying_guide** – FAIL  
  TV/Audio → Buying Guide
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_21_accessories_category** – FAIL  
  Accessories category – browse and open product
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_22_my_account_sign_in** – FAIL  
  My LG / Sign in link
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_23_search_refrigerator_pincode** – FAIL  
  Search refrigerator, PDP, pincode check
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_24_multiple_products_cart** – FAIL  
  Add two different products to cart
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **lg_25_life_upgrade_sale** – FAIL  
  Navigate to Life-Upgrade Sale or promotion
  - Error: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>

