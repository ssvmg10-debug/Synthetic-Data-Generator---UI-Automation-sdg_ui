"""
LG India (https://www.lg.com/in) – 20+ end-to-end UI automation test cases.
Use with: POST /ui/run or /ui/run-workflow with raw_input = test case text.
Or run via: python -c "from lg_test_cases import LG_TEST_CASES; print(LG_TEST_CASES[0]['text'])"
"""
from typing import List, Dict, Any, Optional

# Base URL used in all cases
LG_BASE = "https://www.lg.com/in"

LG_TEST_CASES: List[Dict[str, Any]] = [
    # --- E-commerce: Search, PDP, Cart, Checkout ---
    {
        "id": "lg_01_buy_tv_under_30k",
        "name": "Buy TV under 30k – search, PDP, pincode, checkout",
        "text": f"""navigate to this application {LG_BASE}
click on search option and search for lg 108cm tv and then click on buy now for any product under 30000
then fill the pincode as 500032, then click on check, then click on checkout
then click on continue with this condition (complete purchase as guest)
then fill billing and shipping details""",
    },
    {
        "id": "lg_02_search_washing_machine_cart",
        "name": "Search washing machine, open PDP, add to cart, verify cart",
        "text": f"""open this application {LG_BASE}
in the search box search for front load washing machine
from the results click on any washing machine product
verify product details page is visible and add the product to cart
open the cart page and verify the selected washing machine is present in cart""",
    },
    {
        "id": "lg_03_tv_category_nav_add_cart",
        "name": "TV/Audio category → TV listing → product → add to cart",
        "text": f"""open this application {LG_BASE}
from the top navigation open TV or Audio Video category
navigate to LED or OLED TVs listing page
click on any tv product from the grid
add the tv to cart and go to cart page""",
    },
    {
        "id": "lg_04_filter_oled_tv_verify_specs",
        "name": "Filter OLED TVs, select product, verify specs",
        "text": f"""open this application {LG_BASE}
go to tv or audio video category and open tv listing
apply filter for OLED tvs
select any OLED tv from filtered results
open product details and verify price and key specifications are visible""",
    },
    {
        "id": "lg_05_search_soundbar_add_cart",
        "name": "Search soundbar, first result, add to cart, verify cart",
        "text": f"""open this application {LG_BASE}
use search option to search for soundbar
from the search results click on first soundbar product
add soundbar to cart
open cart and verify soundbar item is listed""",
    },
    {
        "id": "lg_06_guest_checkout_flow",
        "name": "Guest checkout – search, cart, checkout, guest, shipping",
        "text": f"""open this application {LG_BASE}
search for any tv product and add it to cart
go to cart and click on checkout
if login or register page is shown choose to continue as guest if available
fill required shipping details on checkout page and proceed until payment step without completing payment""",
    },
    {
        "id": "lg_07_pincode_delivery_check",
        "name": "Refrigerator PDP – pincode 500032, check delivery",
        "text": f"""open this application {LG_BASE}
search for refrigerator product and open any refrigerator details page
in the pincode or delivery availability section enter pincode 500032
click on check availability button
verify delivery or availability message is displayed for that pincode""",
    },
    {
        "id": "lg_08_compare_two_products",
        "name": "Compare two TVs – comparison view and specs",
        "text": f"""open this application {LG_BASE}
navigate to tv category listing
select any two tv products using compare or checkbox if available
open comparison view
verify both selected products appear in comparison table with specifications""",
    },
    {
        "id": "lg_09_cart_quantity_update",
        "name": "Add monitor to cart, increase quantity to 2, verify total",
        "text": f"""open this application {LG_BASE}
search for any monitor product and add it to cart
open cart page and increase quantity of the monitor to 2
verify quantity is updated and total price is recalculated""",
    },
    {
        "id": "lg_10_remove_item_from_cart",
        "name": "Add soundbar to cart, remove item, verify cart empty",
        "text": f"""open this application {LG_BASE}
search for soundbar and add any soundbar product to cart
open cart page
remove soundbar item from cart
verify cart becomes empty or soundbar item is no longer listed""",
    },
    # --- Home Appliances ---
    {
        "id": "lg_11_refrigerator_category",
        "name": "Home Appliances → Refrigerators → open a product",
        "text": f"""open this application {LG_BASE}
from main menu open Home Appliances
navigate to Refrigerators category
click on any refrigerator product
verify product details page loads with price and add to cart or buy option""",
    },
    {
        "id": "lg_12_laundry_washing_machine",
        "name": "Laundry / Washing machines listing and PDP",
        "text": f"""open this application {LG_BASE}
go to Home Appliances then Laundry or Washing Machines
open the washing machines listing page
click on any washing machine product
verify product page shows specifications and buy or add to cart button""",
    },
    {
        "id": "lg_13_microwave_search",
        "name": "Search microwave, open first result, verify PDP",
        "text": f"""open this application {LG_BASE}
click on search and search for microwave oven
from results click on first microwave product
verify product details page is visible with key features""",
    },
    {
        "id": "lg_14_air_conditioner_category",
        "name": "Air Solutions → AC category → product",
        "text": f"""open this application {LG_BASE}
from navigation open Air Solutions
go to Air Conditioners category
click on any split or window AC product
verify product page and check delivery or buy options""",
    },
    # --- Computing & Monitors ---
    {
        "id": "lg_15_computing_monitors",
        "name": "Computing → Monitors → open product",
        "text": f"""open this application {LG_BASE}
open Computing from main menu
navigate to Monitors
click on any monitor product
verify product details and add to cart or buy now visible""",
    },
    {
        "id": "lg_16_laptop_gram",
        "name": "Computing → Laptop / LG gram – open product",
        "text": f"""open this application {LG_BASE}
go to Computing then Laptop or LG gram
open any laptop product page
verify specifications and purchase options are shown""",
    },
    # --- Support & Info ---
    {
        "id": "lg_17_support_warranty",
        "name": "Support → Warranty or Product Support",
        "text": f"""open this application {LG_BASE}
from header or footer open Support
navigate to Warranty Information or Product Support
verify warranty or support content is displayed""",
    },
    {
        "id": "lg_18_contact_us",
        "name": "Support → Contact Us",
        "text": f"""open this application {LG_BASE}
go to Support then Contact Us or Contact
verify contact options like phone, email or chat are visible""",
    },
    {
        "id": "lg_19_shop_offers",
        "name": "Shop → Offers / Promotions",
        "text": f"""open this application {LG_BASE}
from menu open Shop then Offers or Promotions
open any offer or promotion page
verify offer details or linked product listing is shown""",
    },
    {
        "id": "lg_20_tv_buying_guide",
        "name": "TV/Audio → Buying Guide",
        "text": f"""open this application {LG_BASE}
open TV or Audio Video category
navigate to Buying Guide or TV Buying Guide if available
verify guide or editorial content loads""",
    },
    {
        "id": "lg_21_accessories_category",
        "name": "Accessories category – browse and open product",
        "text": f"""open this application {LG_BASE}
from main menu open Accessories
browse refrigerator or TV accessories
click on any accessory product
verify product page and add to cart or buy option""",
    },
    {
        "id": "lg_22_my_account_sign_in",
        "name": "My LG / Sign in link",
        "text": f"""open this application {LG_BASE}
locate My LG or Sign in in the header
click on Sign in or My LG
verify login or account page is displayed""",
    },
    {
        "id": "lg_23_search_refrigerator_pincode",
        "name": "Search refrigerator, PDP, pincode check",
        "text": f"""open this application {LG_BASE}
search for refrigerator
open first refrigerator product
enter pincode 500032 and click check
verify availability or delivery message""",
    },
    {
        "id": "lg_24_multiple_products_cart",
        "name": "Add two different products to cart",
        "text": f"""open this application {LG_BASE}
search for tv and add first tv to cart
search for soundbar and add first soundbar to cart
open cart page
verify both tv and soundbar are listed in cart""",
    },
    {
        "id": "lg_25_life_upgrade_sale",
        "name": "Navigate to Life-Upgrade Sale or promotion",
        "text": f"""open this application {LG_BASE}
from Shop or home page find Life-Upgrade Sale or similar promotion
click on the promotion or sale link
verify sale page or product listing loads""",
    },
]


def get_all_raw_inputs() -> List[str]:
    """Return list of raw_input strings for all LG test cases (e.g. for batch run)."""
    return [tc["text"] for tc in LG_TEST_CASES]


def get_test_case_by_id(tc_id: str) -> Optional[Dict[str, Any]]:
    """Return test case dict by id (e.g. lg_01_buy_tv_under_30k)."""
    for tc in LG_TEST_CASES:
        if tc.get("id") == tc_id:
            return tc
    return None
