# What Gets Stored in Locator Registry — From Your 5 Test Cases

The **Locator Registry** stores one entry per **unique step** that succeeds: key = `site|path|normalized_target|intent`.  
- **site** = `lg.com` (from URL)  
- **path** = path of the **page URL when that step runs** (e.g. `/in` on homepage, `/in/air-solutions` after clicking Air Solutions)  
- **normalized_target** = target text, lowercased and trimmed (e.g. `air solutions`, `buy now`)  
- **intent** = `CLICK` or `SELECT`  

**When we write:** Only when that step **succeeds** (the element was found and clicked). So the first time you run a test we might not have an entry yet; after a successful run we add/update it.

---

## Test case 1 — Water purifiers flow

| Step (what user said) | ELR key (example) | What we store in that entry |
|-----------------------|-------------------|-----------------------------|
| click on home appliances | `lg.com|/in|home appliances|CLICK` | primary_selector (e.g. `a[href="/in/home-appliances"]` or aria), fallback_selectors, dom_fingerprint, confidence, success_count |
| click on all water purifiers | `lg.com|/in/home-appliances|all water purifiers|CLICK` | same structure |
| click on LG 8L RO + Carbon Filter... (product) | `lg.com|/in/...|lg 8l ro + carbon filter water purifier...|CLICK` | selector that found that product link/card |
| click on buy now | `lg.com|/in/.../product/...|buy now|CLICK` | e.g. button or link for Buy Now on PDP |
| click on check (pincode) | `lg.com|/in/...|check|CLICK` (or path where pincode UI is) | check button beside pincode |
| click on free delivery | `lg.com|/in/...|free delivery|CLICK` or `SELECT` | radio/option for free delivery |
| click on checkout | `lg.com|/in/...|checkout|CLICK` | checkout button |
| click on continue... (guest) | `lg.com|/in/...|continue as guest|CLICK` | guest checkout button |

**Fill pincode / fill billing** → We do **not** store these in ELR as CLICK; we may cache the **search input** or **pincode** input in execution_memory for TYPE.

---

## Test case 2 — Search LG TV flow

| Step | ELR key (example) | What we store |
|------|-------------------|----------------|
| click on search option | `lg.com|/in|search|CLICK` | ✅ You already have this: `a[href="#search"]` |
| search for lg tv 108cm | (TYPE — not stored in ELR; execution_memory for "search" + TYPE) | — |
| click on any product | `lg.com|/in/search/...|any product|CLICK` | selector that found first product link |
| click on buy now | same as test 1 (path = product page) | |
| check, free delivery, checkout, continue as guest | same pattern as test 1, path = cart/checkout page | |

---

## Test case 3 — Air solutions + QR + place order

| Step | ELR key (example) | What we store |
|------|-------------------|----------------|
| click on air solutions | `lg.com|/in|air solutions|CLICK` | nav link for Air Solutions |
| click on split air conditioners | `lg.com|/in/air-solutions|split air conditioners|CLICK` | category link |
| click on any one product | `lg.com|/in/.../split-ac/...|any product|CLICK` or similar path | first product link |
| click on buy now | (PDP path) | |
| check, free delivery, checkout, guest | (cart/checkout path) | |
| click on QR code (payment) | `lg.com|/in/...|qr code|CLICK` (path = payment step) | QR code option |
| click on all checkboxes | `lg.com|/in/...|all checkboxes|CLICK` or we might store as single intent | checkboxes in payment |
| click on place order | `lg.com|/in/...|place order|CLICK` | Place order button |

---

## Test case 4 — Banner + Audio + filters

| Step | ELR key (example) | What we store |
|------|-------------------|----------------|
| click on buy electronics & IT (banner) | `lg.com|/in|buy electronics & it|CLICK` | banner CTA |
| click on Audio | `lg.com|/in|audio|CLICK` (or path after banner) | Audio link |
| click on party speakers (filter checkbox) | `lg.com|/in/.../audio/...|party speakers|CLICK` or `SELECT` | filter checkbox |
| click on product LG XBOOM RNC5... | `lg.com|/in/...|lg xboom rnc5...|CLICK` | product link |
| buy now, pincode check, free delivery, checkout, guest, QR, checkboxes, place order | same as test 3 | |

---

## Test case 5 — Sitemap

| Step | ELR key (example) | What we store |
|------|-------------------|----------------|
| click on sitemap | `lg.com|/in|sitemap|CLICK` | sitemap link |

---

## Complete list of distinct “targets” that can get an ELR entry

From your five flows, these are the **normalized_target** values (plus path) that will get entries when those steps succeed:

| normalized_target (examples) | Intent | Typical path(s) |
|------------------------------|--------|------------------|
| home appliances | CLICK | /in |
| all water purifiers | CLICK | /in/home-appliances or similar |
| air solutions | CLICK | /in |
| split air conditioners | CLICK | /in/air-solutions or similar |
| search | CLICK | /in (you have this) |
| any product | CLICK | /in/search/..., /in/.../split-ac/..., etc. |
| buy now | CLICK | product page path |
| check | CLICK | cart/checkout (pincode check) |
| free delivery | CLICK or SELECT | checkout page |
| checkout | CLICK | cart page |
| continue as guest | CLICK | checkout page |
| qr code | CLICK | payment step |
| all checkboxes | CLICK | payment step |
| place order | CLICK | payment step |
| buy electronics & it | CLICK | /in |
| audio | CLICK | /in or after banner |
| party speakers | CLICK/SELECT | audio/category page |
| sitemap | CLICK | /in |
| + specific product names (e.g. lg 8l ro..., lg xboom rnc5...) | CLICK | category/listing path |

So we **do** store: every such **click/select** step, keyed by **site | path | normalized_target | intent**. Same label on a **different path** (e.g. “buy now” on PDP vs “checkout” on cart) = different keys = different entries.

---

## What is stored inside each ELR entry

For each key we store (and use) this:

```json
{
  "site": "lg.com",
  "page_url": "https://www.lg.com/in",
  "normalized_target": "air solutions",
  "intent": "CLICK",
  "primary_selector": { "type": "css", "value": "nav a[href='/in/air-solutions']" },
  "fallback_selectors": [
    { "type": "aria", "value": "role=link[name='Air Solutions']" },
    { "type": "xpath", "value": "//nav//a[contains(., 'Air Solutions')]" }
  ],
  "dom_fingerprint": {
    "tag": "a",
    "parent_chain": ["nav", "ul", "li"],
    "text_hash": "...",
    "attribute_hash": "...",
    "sibling_index": 2
  },
  "confidence_score": 0.92,
  "success_count": 14,
  "failure_count": 1,
  "last_verified": "2026-02-18T20:30:00Z"
}
```

- **primary_selector** = the selector we used when the step succeeded (or from crawl).  
- **fallback_selectors** = other working selectors we found later (or from crawl).  
- **dom_fingerprint** = structural info so if the primary breaks we can find a similar element.  
- **confidence_score / success_count / failure_count / last_verified** = so we can demote or prefer this entry.

---

## Summary

- From your **five test cases**, we store **every successful CLICK/SELECT** step in the Locator Registry.  
- Each entry is identified by **site | path | normalized_target | intent**.  
- We store **primary + fallback selectors**, optional **DOM fingerprint**, and **confidence** data.  
- We **use** these entries by injecting **locator_candidates** into the plan and trying them **first** (Phase 0) on the next run.  
- So: **home appliances**, **air solutions**, **search**, **buy now**, **check**, **free delivery**, **checkout**, **continue as guest**, **qr code**, **place order**, **sitemap**, **audio**, **party speakers**, **buy electronics & it**, **any product**, and specific product names will **all** get stored (and reused) as you run and succeed on those steps.
