# Run multiple Synthetic Data + UI Automation tests
$port = 8002
try { $null = Invoke-WebRequest -Uri "http://localhost:8002/health" -UseBasicParsing -TimeoutSec 2 } catch { $port = 8001 }
$baseUrl = "http://localhost:$port"

$tests = @(
  # ========================= LG ENTERPRISE FLOWS (10) =========================
  @{ name = 'lg_buy_tv_under_30k'; text = "navigate to this application https://www.lg.com/in
click on search option and search for lg 108cm tv and then click on buynow for any product under 30000
then fill the pincode as 500032, then click on check, then click on checkout
then continue as guest and fill all mandatory billing and shipping details" },

  @{ name = 'lg_search_washing_machine'; text = "open this application https://www.lg.com/in
in the search box search for front load washing machine
from the results click on any washing machine product
verify product details page is visible and add the product to cart
open the cart page and verify the selected washing machine is present in cart" },

  @{ name = 'lg_tv_category_nav'; text = "open this application https://www.lg.com/in
from the top navigation open TV or Audio Video category
navigate to LED or OLED TVs listing page
click on any tv product from the grid
add the tv to cart and go to cart page" },

  @{ name = 'lg_filter_oled_tv'; text = "open this application https://www.lg.com/in
go to tv or audio video category and open tv listing
apply filter for OLED tvs
select any OLED tv from filtered results
open product details and verify price and key specifications are visible" },

  @{ name = 'lg_search_soundbar_add_to_cart'; text = "open this application https://www.lg.com/in
use search option to search for soundbar
from the search results click on first soundbar product
add soundbar to cart
open cart and verify soundbar item is listed" },

  @{ name = 'lg_guest_checkout_flow'; text = "open this application https://www.lg.com/in
search for any tv product and add it to cart
go to cart and click on checkout
if login or register page is shown choose to continue as guest if available
fill required shipping details on checkout page and proceed until payment step without completing payment" },

  @{ name = 'lg_pincode_delivery_check'; text = "open this application https://www.lg.com/in
search for refrigerator product and open any refrigerator details page
in the pincode or delivery availability section enter pincode 500032
click on check availability button
verify delivery or availability message is displayed for that pincode" },

  @{ name = 'lg_compare_two_products'; text = "open this application https://www.lg.com/in
navigate to tv category listing
select any two tv products using compare or checkbox if available
open comparison view
verify both selected products appear in comparison table with specifications" },

  @{ name = 'lg_cart_quantity_update'; text = "open this application https://www.lg.com/in
search for any monitor product and add it to cart
open cart page and increase quantity of the monitor to 2
verify quantity is updated and total price is recalculated" },

  @{ name = 'lg_remove_item_from_cart'; text = "open this application https://www.lg.com/in
search for soundbar and add any soundbar product to cart
open cart page
remove soundbar item from cart
verify cart becomes empty or soundbar item is no longer listed" },

  # ========================= HILTI ENTERPRISE FLOWS (10) ======================
  @{ name = 'hilti_rotary_hammer_basic'; text = "open this application https://www.hilti.in/
navigate to power tools section then open rotary hammers category
click on any rotary hammer product
add the product to cart and go to cart page" },

  @{ name = 'hilti_search_rotary_hammer'; text = "open this application https://www.hilti.in/
in the search box search for rotary hammer
open first rotary hammer product from search results
add it to cart and verify item is visible in cart" },

  @{ name = 'hilti_cordless_drill_add_to_cart'; text = "open this application https://www.hilti.in/
navigate to cordless tools or cordless drill drivers category
open any cordless drill product details page
add the cordless drill to cart
go to cart page and verify cordless drill item is displayed" },

  @{ name = 'hilti_accessories_navigation'; text = "open this application https://www.hilti.in/
from main navigation open accessories or bits and inserts section
open any accessory product details page
verify product information and specifications are visible" },

  @{ name = 'hilti_cart_update_quantity'; text = "open this application https://www.hilti.in/
search for hammer drill bit and add any bit to cart
open cart page and increase quantity of the item to 2
verify quantity update is reflected in cart summary" },

  @{ name = 'hilti_view_cart_from_header'; text = "open this application https://www.hilti.in/
search for any construction chemical product and add it to cart
use header cart icon or cart link to open cart
verify added product is visible in cart and price is displayed" },

  @{ name = 'hilti_checkout_guest_or_login'; text = "open this application https://www.hilti.in/
search for rotary hammer and add it to cart
go to cart and click on proceed to checkout
on login or customer identification page either login if account exists or continue as guest if option is available
navigate until shipping address page without placing final order" },

  @{ name = 'hilti_search_anchor_system'; text = "open this application https://www.hilti.in/
use search to look for anchor system
open any anchor system product details page
verify technical data or documents section is visible on the page" },

  @{ name = 'hilti_support_contact_navigation'; text = "open this application https://www.hilti.in/
from header or footer navigate to contact or support page
verify that support or contact information is shown
check that at least one contact method like phone number or email is visible" },

  @{ name = 'hilti_my_account_or_sign_in_link'; text = "open this application https://www.hilti.in/
locate my account or sign in link in header
click on sign in or my account
verify that login page or account page is displayed" }
)

foreach ($tc in $tests) {
  Write-Host "================================================================================" -ForegroundColor Cyan
  Write-Host "TEST: $($tc.name)" -ForegroundColor Yellow
  Write-Host "================================================================================" -ForegroundColor Cyan

  # Synthetic Data Agent
  Write-Host "[Synthetic] $($tc.name)" -ForegroundColor Green
  $body1 = @{ user_input = $tc.text; model = "GaussianCopula" } | ConvertTo-Json
  try {
    $r1 = Invoke-RestMethod -Uri "$baseUrl/synthetic/generate-from-text" -Method POST -Body $body1 -ContentType "application/json" -TimeoutSec 420
    Write-Host "  status: $($r1.message) run_id: $($r1.run_id) schema_id: $($r1.schema_id) rows: $($r1.rows_generated)" -ForegroundColor Green
  } catch {
    Write-Host "  FAILED: $_" -ForegroundColor Red
  }

  # UI Automation Agent
  Write-Host "[UI] $($tc.name)" -ForegroundColor Green
  $body2 = @{ raw_input = $tc.text } | ConvertTo-Json
  try {
    $r2 = Invoke-RestMethod -Uri "$baseUrl/ui/run-workflow" -Method POST -Body $body2 -ContentType "application/json" -TimeoutSec 900
    Write-Host "  success: $($r2.success) status: $($r2.status) message: $($r2.message)" -ForegroundColor Green
    if ($r2.error) { Write-Host "  error: $($r2.error)" -ForegroundColor Red }
  } catch {
    Write-Host "  FAILED: $_" -ForegroundColor Red
  }

  Write-Host "" 
}
