"""
Application Knowledge Engine (AKE).
Real-time page intelligence: detects cookie modals, search bars, login, shadow roots, etc.
"""
from .scanner import get_ake_script, parse_ake_result, selector_list_from_ake

__all__ = ["get_ake_script", "parse_ake_result", "selector_list_from_ake"]
