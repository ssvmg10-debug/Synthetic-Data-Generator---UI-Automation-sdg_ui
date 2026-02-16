"""
Unit tests for SelectorValidator — run headless against a known local HTML page.
Asserts counts and matches to catch async/await bugs (e.g. un-awaited .count()).
"""
import os
import sys
import asyncio
from pathlib import Path

import pytest

# Support running from project root (backend. prefix) or from backend (services. prefix)
try:
    from services.ui_automation.utils.selector_validator import SelectorValidator
except ImportError:
    from backend.services.ui_automation.utils.selector_validator import SelectorValidator


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
HTML_FILE = FIXTURE_DIR / "selector_validation_page.html"


def _file_url(path: Path) -> str:
    return path.as_uri()


@pytest.fixture(scope="module")
def fixture_url():
    """URL to the fixture HTML (file://)."""
    if not HTML_FILE.exists():
        pytest.skip(f"Fixture not found: {HTML_FILE}")
    return _file_url(HTML_FILE)


@pytest.mark.asyncio
async def test_validate_script_counts_single_match(fixture_url):
    """Validator should find exactly one element for role=button name=Accept."""
    steps = [
        {"action": "click", "selector": "button:has-text('Accept all')", "description": "Accept cookies"},
    ]
    validator = SelectorValidator(headless=True)
    result = await validator.validate_script(fixture_url, steps, wait_for_load=True)
    assert result["validation_passed"] is True
    assert result["valid_count"] >= 1
    assert result["invalid_count"] == 0


@pytest.mark.asyncio
async def test_validate_script_locator_hint_role(fixture_url):
    """Steps with locator_hint (role/name) should be validated via get_by_role and count awaited."""
    steps = [
        {"action": "click", "selector": "button", "description": "Accept", "locator_hint": {"role": "button", "name": "Accept all"}},
    ]
    validator = SelectorValidator(headless=True)
    result = await validator.validate_script(fixture_url, steps, wait_for_load=True)
    assert result["validation_passed"] is True
    assert len(result["invalid_selectors"]) == 0


@pytest.mark.asyncio
async def test_validate_script_placeholder_match(fixture_url):
    """Input with placeholder 'Search' should match and validate."""
    steps = [
        {"action": "fill", "selector": "input[placeholder*='Search']", "value": "test", "description": "Search"},
    ]
    validator = SelectorValidator(headless=True)
    result = await validator.validate_script(fixture_url, steps, wait_for_load=True)
    assert result["validation_passed"] is True
    assert result["invalid_count"] == 0


@pytest.mark.asyncio
async def test_validate_script_invalid_selector_reported(fixture_url):
    """Selector that matches nothing and has no auto-fix (e.g. select with no fallback) → invalid."""
    # "select" action has no Playwright role fallback in validator, so this stays invalid
    steps = [
        {"action": "select", "selector": "#no-such-id-999", "value": "x", "description": "No such select"},
    ]
    validator = SelectorValidator(headless=True)
    result = await validator.validate_script(fixture_url, steps, wait_for_load=True)
    assert result["validation_passed"] is False
    assert result["invalid_count"] >= 1
    assert len(result["invalid_selectors"]) >= 1


@pytest.mark.asyncio
async def test_validate_script_multiple_steps_goto_click_fill(fixture_url):
    """Multi-step: goto (no selector), then click, then fill — all use awaited Playwright APIs."""
    steps = [
        {"action": "goto", "value": fixture_url, "description": "Open page"},
        {"action": "click", "selector": "button:has-text('Accept all')", "description": "Accept"},
        {"action": "fill", "selector": "input[placeholder*='Search']", "value": "shirt", "description": "Search"},
    ]
    validator = SelectorValidator(headless=True)
    result = await validator.validate_script(fixture_url, steps, wait_for_load=True)
    assert result["validated_steps"] is not None
    assert len(result["validated_steps"]) == 3
    assert result["stats"]["total_steps"] == 3
