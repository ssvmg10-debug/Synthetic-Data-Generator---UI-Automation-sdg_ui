"""
Test Data Vault & Environment Manager – production-grade.
Manage synthetic data (addresses, emails), test accounts, environment toggles (staging vs prod),
test payment endpoints, feature flags. Use for deterministic automation data.
"""
from typing import Dict, Any, Optional
import os
import logging

logger = logging.getLogger(__name__)

# Environment toggles (set UI_AUTOMATION_STAGING=1, UI_AUTOMATION_MOCK_PAYMENT=1)
def get_environment() -> str:
    """Return 'staging' or 'prod' based on env."""
    return "staging" if os.environ.get("UI_AUTOMATION_STAGING", "").strip() in ("1", "true", "yes") else "prod"


def use_mock_payment() -> bool:
    """Whether to stub external payment/gateway in automation."""
    return os.environ.get("UI_AUTOMATION_MOCK_PAYMENT", "").strip() in ("1", "true", "yes")


# Deterministic synthetic data for tests (no PII in repo; override via env or vault)
DEFAULT_SYNTHETIC = {
    "name": "Test User",
    "address": "123 Test Street, Block A",
    "city": "Hyderabad",
    "state": "Telangana",
    "pincode": "500032",
    "phone": "9876543210",
    "email": "test.automation@example.com",
}


def get_synthetic_address(override: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Return deterministic address for automation. Prefer env vars then defaults.
    In production, replace with encrypted vault lookup.
    """
    out = dict(DEFAULT_SYNTHETIC)
    out["name"] = os.environ.get("UI_TEST_NAME", out["name"])
    out["address"] = os.environ.get("UI_TEST_ADDRESS", out["address"])
    out["city"] = os.environ.get("UI_TEST_CITY", out["city"])
    out["pincode"] = os.environ.get("UI_TEST_PINCODE", out["pincode"])
    out["phone"] = os.environ.get("UI_TEST_PHONE", out["phone"])
    out["email"] = os.environ.get("UI_TEST_EMAIL", out["email"])
    if override:
        out.update(override)
    return out


def get_test_account(app_key: str) -> Optional[Dict[str, str]]:
    """
    Return test account credentials for app (e.g. lg_in). Store in env or vault only.
    Format: {"email": "...", "password": "..."} or None for guest checkout.
    """
    if not app_key:
        return None
    email = os.environ.get(f"UI_TEST_ACCOUNT_{app_key.upper()}_EMAIL")
    password = os.environ.get(f"UI_TEST_ACCOUNT_{app_key.upper()}_PASSWORD")
    if email and password:
        return {"email": email, "password": password}
    return None
