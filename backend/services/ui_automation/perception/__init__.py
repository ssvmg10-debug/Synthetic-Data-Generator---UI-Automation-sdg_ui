"""
Perception Module - Enterprise-grade UI understanding

This module provides structural awareness through DOM graph extraction
instead of brittle page type classification.
"""

from .dom_graph import UINode, UIGraph, DOMGraphExtractor

__all__ = ["UINode", "UIGraph", "DOMGraphExtractor"]
