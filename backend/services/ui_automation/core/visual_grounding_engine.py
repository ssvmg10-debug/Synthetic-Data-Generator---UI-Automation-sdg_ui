"""
Module 3 — Visual Grounding Engine (Claude-like perception layer)

Two modes:
A) Text-only: send list of element (index, text, role) to LLM → pick index (existing).
B) Vision (Claude-like): capture screenshot, send image + element list to vision model →
   model "sees" the UI and returns index or (x,y) → click by coordinates or by bbox.

Env: USE_VISION_GROUNDING=true and AZURE_VISION_DEPLOYMENT (e.g. gpt-4o) to enable vision.
"""
import base64
import logging
import json
import os
import re
from typing import Optional, Dict, Any, List, Tuple
from playwright.async_api import Page

logger = logging.getLogger(__name__)

USE_VISION = os.getenv("USE_VISION_GROUNDING", "").lower() in ("1", "true", "yes")
VISION_DEPLOYMENT = os.getenv("AZURE_VISION_DEPLOYMENT") or os.getenv("AZURE_DEPLOYMENT") or "gpt-4o"


async def _collect_clickable_candidates(page: Page, limit: int = 50) -> List[Dict[str, Any]]:
    """Extract clickable elements with bbox, text, role, visibility."""
    candidates = []
    selectors = [
        "button:visible, [role='button']:visible",
        "a:visible",
        "[data-testid]:visible",
        "[data-test-id]:visible",
        "[class*='button']:visible, [class*='btn']:visible",
    ]
    seen_texts = set()
    for sel in selectors:
        try:
            loc = page.locator(sel)
            n = await loc.count()
            for i in range(min(n, 25)):
                if len(candidates) >= limit:
                    break
                el = loc.nth(i)
                try:
                    box = await el.bounding_box(timeout=500)
                    if not box or box.get("width", 0) < 2 or box.get("height", 0) < 2:
                        continue
                    text = (await el.inner_text(timeout=300)).strip()[:80]
                    if not text or text in seen_texts:
                        continue
                    seen_texts.add(text)
                    role = await el.get_attribute("role") or ("button" if "button" in sel else "link")
                    candidates.append({
                        "index": len(candidates),
                        "text": text,
                        "role": role,
                        "bbox": box,
                        "selector": f"internal:{sel}:nth({i})",
                    })
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Collect candidates {sel}: {e}")
        if len(candidates) >= limit:
            break
    return candidates


async def _capture_screenshot_base64(page: Page, full_page: bool = False) -> Optional[str]:
    """Capture viewport (or full page) as PNG base64 for vision API."""
    try:
        buf = await page.screenshot(type="png", full_page=full_page, timeout=10000)
        return base64.b64encode(buf).decode("ascii")
    except Exception as e:
        logger.debug(f"Screenshot capture failed: {e}")
        return None


async def click_by_coordinates(page: Page, x: float, y: float) -> bool:
    """Click at (x, y) in viewport — true selector independence (Claude-style)."""
    try:
        await page.mouse.click(x, y, timeout=3000)
        logger.info(f"  ✅ Clicked by coordinates ({x:.0f}, {y:.0f})")
        return True
    except Exception as e:
        logger.error(f"click_by_coordinates failed: {e}")
        return False


async def resolve_visually_with_vision(
    page: Page,
    target: str,
    intent: str,
    candidates: List[Dict[str, Any]],
    client: Any,
) -> Optional[Dict[str, Any]]:
    """
    Claude-like: send screenshot + prompt to vision model; model sees UI and returns index or coordinates.
    """
    screenshot_b64 = await _capture_screenshot_base64(page)
    if not screenshot_b64:
        return None
    list_for_model = [
        {"index": c["index"], "text": c["text"][:60], "role": c["role"]}
        for c in candidates[:30]
    ]
    prompt = f"""You are a UI automation agent with visual understanding. The user wants to: "{target}" (intent: {intent}).

Look at the screenshot. Below are visible clickable elements (index, text, role):
{json.dumps(list_for_model, indent=2)}

Which element index (0-based) best matches the target? Consider layout and semantics (e.g. "Continue as guest" = "Guest checkout").
Reply with ONLY a JSON object: {{ "index": <number> }} or {{ "index": <number>, "x": <center_x>, "y": <center_y> }} if you can give click coordinates.
If no match, return {{ "index": -1 }}."""

    try:
        response = client.chat.completions.create(
            model=VISION_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You return only valid JSON: index (0-based), and optionally x,y for click position."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"},
                        },
                    ],
                },
            ],
            temperature=0.1,
            max_tokens=150,
        )
        raw = response.choices[0].message.content.strip()
        if "```" in raw:
            raw = re.sub(r"```\w*\n?", "", raw).strip()
        out = json.loads(raw)
        idx = out.get("index", -1)
        if idx < 0 or idx >= len(candidates):
            return None
        chosen = candidates[idx]
        result = {"index": idx, "text": chosen["text"], "element": chosen}
        if "x" in out and "y" in out:
            try:
                result["coordinates"] = (float(out["x"]), float(out["y"]))
            except (TypeError, ValueError):
                pass
        return result
    except Exception as e:
        logger.debug(f"Vision grounding failed: {e}")
        return None


async def resolve_visually(
    page: Page,
    target: str,
    intent: str,
    context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Use LLM to pick the best matching element from visible clickables.
    Returns {"index": int, "text": str} or None.
    """
    client = None
    try:
        api_key = (
            os.getenv("AZURE_OPENAI_KEY")
            or os.getenv("AZURE_OPENAI_API_KEY")
            or os.getenv("AZURE_API_KEY")
        )
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_ENDPOINT")
        if not api_key or not endpoint:
            logger.warning("Visual grounding: Azure OpenAI not configured")
            return None
        from openai import AzureOpenAI
        client = AzureOpenAI(
            api_key=api_key,
            api_version=os.getenv("AZURE_API_VERSION", "2024-02-01"),
            azure_endpoint=endpoint,
        )
    except Exception as e:
        logger.warning(f"Visual grounding client: {e}")
        return None

    try:
        candidates = await _collect_clickable_candidates(page, limit=40)
        if not candidates:
            logger.warning("Visual grounding: no clickable candidates")
            return None

        # Claude-like: try vision first (screenshot + model sees UI) when enabled
        if USE_VISION and client:
            try:
                result = await resolve_visually_with_vision(page, target, intent, candidates, client)
                if result:
                    logger.info(f"Visual grounding (vision): chose index {result.get('index')} -> '{result.get('text', '')[:50]}'")
                    return result
            except Exception as e:
                logger.debug(f"Vision path failed, falling back to text: {e}")

        # Text-only: send element list to LLM (no screenshot)
        list_for_model = [
            {"index": c["index"], "text": c["text"], "role": c["role"]}
            for c in candidates
        ]
        prompt = f"""You are a UI automation expert. The user tried to click/select: "{target}" (intent: {intent}).

Available visible elements (index, text, role):
{json.dumps(list_for_model, indent=2)}

Which single element index best matches the target? Consider semantic equivalence (e.g. "Continue as guest" = "Guest checkout", "Free delivery" = "Standard delivery ₹0").
Return ONLY valid JSON: {{ "index": <number>, "reason": "<brief>" }}
If no good match, return {{ "index": -1, "reason": "no match" }}."""

        model_name = os.getenv("AZURE_DEPLOYMENT") or "gpt-4o"
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You return only valid JSON with 'index' and 'reason'."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=150,
        )
        raw = response.choices[0].message.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1].replace("json", "").strip()
        out = json.loads(raw)
        idx = out.get("index", -1)
        if idx < 0 or idx >= len(candidates):
            logger.info(f"Visual grounding: no match (reason: {out.get('reason')})")
            return None
        chosen = candidates[idx]
        logger.info(f"Visual grounding: chose index {idx} -> '{chosen['text'][:50]}'")
        return {"index": idx, "text": chosen["text"], "element": chosen}
    except Exception as e:
        logger.error(f"Visual grounding error: {e}")
        return None


async def click_by_visual_result(page: Page, visual_result: Dict[str, Any]) -> bool:
    """
    Click the element from visual grounding. Prefer: 1) coordinates (vision), 2) bbox center, 3) text/role.
    """
    try:
        # 1) Claude-like: click by coordinates if vision returned (x, y)
        coords = visual_result.get("coordinates")
        if coords and len(coords) >= 2:
            return await click_by_coordinates(page, coords[0], coords[1])

        # 2) Click by bounding box center (selector-independent)
        elem = visual_result.get("element")
        if elem and elem.get("bbox"):
            bbox = elem["bbox"]
            cx = bbox.get("x", 0) + (bbox.get("width", 0) / 2)
            cy = bbox.get("y", 0) + (bbox.get("height", 0) / 2)
            return await click_by_coordinates(page, cx, cy)

        # 3) Fallback: click by text/role (DOM-based)
        text = visual_result.get("text") or (elem or {}).get("text")
        if not text:
            return False
        for strategy in [
            lambda: page.get_by_role("button", name=text),
            lambda: page.get_by_role("button", name=text, exact=False),
            lambda: page.get_by_role("link", name=text),
            lambda: page.get_by_role("link", name=text, exact=False),
            lambda: page.get_by_text(text, exact=True),
            lambda: page.get_by_text(text, exact=False),
        ]:
            try:
                loc = strategy()
                if await loc.count() > 0:
                    await loc.first.scroll_into_view_if_needed(timeout=2000)
                    await loc.first.click(timeout=5000)
                    return True
            except Exception:
                continue
        return False
    except Exception as e:
        logger.error(f"click_by_visual_result: {e}")
        return False
