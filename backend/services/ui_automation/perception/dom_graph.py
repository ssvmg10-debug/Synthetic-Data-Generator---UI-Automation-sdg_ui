"""
DOM Graph Extractor - Structural UI Perception

Replaces brittle PageType classification with full DOM graph awareness.
Extracts every visible interactive element with complete structural context.

Enterprise-grade perception layer for UI automation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from playwright.async_api import Page, ElementHandle
import logging
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class UINode:
    """
    Represents a single UI element in the DOM graph.
    
    Contains all information needed for intent matching and structural healing.
    """
    id: str  # Unique node identifier
    tag: str  # HTML tag name
    role: Optional[str] = None  # ARIA role
    text: str = ""  # Visible text content
    attributes: Dict[str, str] = field(default_factory=dict)  # All attributes
    xpath: str = ""  # XPath selector
    css_selector: str = ""  # CSS selector
    bounding_box: Dict[str, float] = field(default_factory=dict)  # {x, y, width, height}
    is_visible: bool = False  # Visibility state
    is_clickable: bool = False  # Interactivity state
    is_enabled: bool = True  # Enabled/disabled state
    parent_id: Optional[str] = None  # Parent node ID
    children_ids: List[str] = field(default_factory=list)  # Child node IDs
    dom_depth: int = 0  # Depth in DOM tree
    aria_label: Optional[str] = None  # Accessibility label
    placeholder: Optional[str] = None  # Input placeholder
    href: Optional[str] = None  # Link href
    data_testid: Optional[str] = None  # Test ID attribute
    
    def __hash__(self):
        """Hash for set operations."""
        return hash(self.id)
    
    def to_snapshot(self) -> dict:
        """
        Convert to snapshot for structural healing.
        Used to compare with future DOM states.
        """
        return {
            "tag": self.tag,
            "role": self.role,
            "text": self.text,
            "attributes": self.attributes,
            "dom_depth": self.dom_depth,
            "aria_label": self.aria_label,
            "placeholder": self.placeholder,
            "parent_id": self.parent_id,
            "is_clickable": self.is_clickable,
            "is_enabled": self.is_enabled
        }


@dataclass
class UIGraph:
    """
    Complete structural representation of the page's interactive UI.
    
    Provides graph-based reasoning instead of flat page type classification.
    """
    nodes: Dict[str, UINode] = field(default_factory=dict)  # Node ID -> UINode
    edges: List[Tuple[str, str]] = field(default_factory=list)  # (parent_id, child_id)
    url: str = ""
    timestamp: float = 0.0
    
    def get_clickable_nodes(self) -> List[UINode]:
        """Get all clickable nodes."""
        return [n for n in self.nodes.values() if n.is_clickable and n.is_visible]
    
    def get_by_role(self, role: str) -> List[UINode]:
        """Get all nodes with specific ARIA role."""
        return [n for n in self.nodes.values() if n.role == role and n.is_visible]
    
    def get_by_text(self, text: str, case_insensitive: bool = True) -> List[UINode]:
        """Get nodes containing text."""
        if case_insensitive:
            text = text.lower()
            return [n for n in self.nodes.values() 
                    if text in n.text.lower() and n.is_visible]
        return [n for n in self.nodes.values() 
                if text in n.text and n.is_visible]
    
    def get_children(self, node_id: str) -> List[UINode]:
        """Get child nodes."""
        node = self.nodes.get(node_id)
        if not node:
            return []
        return [self.nodes[cid] for cid in node.children_ids if cid in self.nodes]
    
    def get_parent(self, node_id: str) -> Optional[UINode]:
        """Get parent node."""
        node = self.nodes.get(node_id)
        if not node or not node.parent_id:
            return None
        return self.nodes.get(node.parent_id)
    
    def get_node_context(self, node_id: str, depth: int = 2) -> Dict[str, any]:
        """
        Get contextual information around a node.
        Used for structural similarity matching.
        """
        node = self.nodes.get(node_id)
        if not node:
            return {}
        
        context = {
            "node": node.to_snapshot(),
            "siblings": [],
            "ancestors": [],
            "descendants": []
        }
        
        # Get siblings
        if node.parent_id:
            parent = self.get_parent(node_id)
            if parent:
                context["siblings"] = [
                    self.nodes[cid].to_snapshot() 
                    for cid in parent.children_ids 
                    if cid != node_id and cid in self.nodes
                ]
        
        # Get ancestors
        current = node
        for _ in range(depth):
            if not current.parent_id:
                break
            parent = self.get_parent(current.id)
            if parent:
                context["ancestors"].append(parent.to_snapshot())
                current = parent
        
        # Get descendants
        def collect_descendants(nid, current_depth):
            if current_depth >= depth:
                return
            for child_id in self.nodes[nid].children_ids:
                if child_id in self.nodes:
                    context["descendants"].append(self.nodes[child_id].to_snapshot())
                    collect_descendants(child_id, current_depth + 1)
        
        collect_descendants(node_id, 0)
        
        return context


class DOMGraphExtractor:
    """
    Enterprise-grade DOM graph extractor.
    
    Extracts full structural representation of UI instead of brittle page types.
    """
    
    # Interactive tags to extract
    INTERACTIVE_TAGS = {
        "a", "button", "input", "select", "textarea", 
        "form", "label", "option", "img"
    }
    
    # Tags to include even if not clickable (structural context)
    STRUCTURAL_TAGS = {
        "nav", "header", "footer", "main", "section", 
        "article", "aside", "div", "span"
    }
    
    def __init__(self):
        self.node_counter = 0
    
    async def extract(self, page: Page) -> UIGraph:
        """
        Extract complete UI graph from page.
        
        Returns:
            UIGraph with all visible interactive elements and their relationships.
        """
        logger.info(f"🔍 Extracting DOM graph from {page.url[:60]}")
        
        graph = UIGraph(url=page.url)
        
        try:
            # Get all potentially interactive elements
            # Use broader selector to capture structure
            elements = await page.query_selector_all(
                "a, button, input, select, textarea, form, "
                "nav, header, [role], [aria-label], "
                "[data-testid], [class*='button'], [class*='btn'], "
                "[class*='link'], [class*='menu'], [class*='cart'], "
                "[class*='checkout'], [class*='product'], [class*='search']"
            )
            
            logger.info(f"Found {len(elements)} potential UI elements")
            
            # Extract node information
            processed = 0
            for elem in elements[:500]:  # Limit to first 500 to avoid overwhelming
                try:
                    node = await self._extract_node(page, elem)
                    if node and (node.is_visible or node.is_clickable):
                        graph.nodes[node.id] = node
                        processed += 1
                except Exception as e:
                    logger.debug(f"Failed to extract element: {e}")
                    continue
            
            logger.info(f"✅ Extracted {processed} UI nodes")
            
            # Build edges (parent-child relationships)
            await self._build_edges(graph)
            
            logger.info(f"✅ Built {len(graph.edges)} edges in DOM graph")
            
            return graph
            
        except Exception as e:
            logger.error(f"❌ DOM graph extraction failed: {e}")
            return graph
    
    async def _extract_node(self, page: Page, elem: ElementHandle) -> Optional[UINode]:
        """Extract UINode from element."""
        try:
            # Get basic properties
            tag = await elem.evaluate("el => el.tagName.toLowerCase()")
            
            # Check visibility first (optimization)
            is_visible = await elem.is_visible()
            
            # Get bounding box
            bbox = {}
            try:
                box = await elem.bounding_box()
                if box:
                    bbox = {
                        "x": box["x"],
                        "y": box["y"],
                        "width": box["width"],
                        "height": box["height"]
                    }
            except:
                pass
            
            # Get text content
            text = ""
            try:
                text = await elem.inner_text(timeout=1000)
                text = text.strip()[:200]  # Limit length
            except:
                try:
                    text = await elem.text_content(timeout=1000)
                    text = (text or "").strip()[:200]
                except:
                    pass
            
            # Get attributes
            attributes = {}
            try:
                attributes = await elem.evaluate("""
                    el => {
                        const attrs = {};
                        for (let attr of el.attributes) {
                            attrs[attr.name] = attr.value;
                        }
                        return attrs;
                    }
                """)
            except:
                pass
            
            # Get ARIA role
            role = None
            try:
                role = await elem.get_attribute("role") or attributes.get("role")
            except:
                pass
            
            # Check clickability
            is_clickable = False
            is_enabled = True
            try:
                is_clickable = await elem.is_enabled() and tag in self.INTERACTIVE_TAGS
                is_enabled = await elem.is_enabled()
            except:
                is_clickable = tag in self.INTERACTIVE_TAGS
            
            # Get accessibility label
            aria_label = None
            try:
                aria_label = await elem.get_attribute("aria-label") or attributes.get("aria-label")
            except:
                pass
            
            # Get placeholder
            placeholder = None
            if tag == "input":
                try:
                    placeholder = await elem.get_attribute("placeholder") or attributes.get("placeholder")
                except:
                    pass
            
            # Get href
            href = None
            if tag == "a":
                try:
                    href = await elem.get_attribute("href") or attributes.get("href")
                except:
                    pass
            
            # Get test ID
            data_testid = None
            try:
                data_testid = await elem.get_attribute("data-testid") or attributes.get("data-testid")
            except:
                pass
            
            # Generate unique ID
            node_id = self._generate_node_id(tag, text, attributes)
            
            # Create node
            node = UINode(
                id=node_id,
                tag=tag,
                role=role,
                text=text,
                attributes=attributes,
                is_visible=is_visible,
                is_clickable=is_clickable,
                is_enabled=is_enabled,
                bounding_box=bbox,
                aria_label=aria_label,
                placeholder=placeholder,
                href=href,
                data_testid=data_testid
            )
            
            return node
            
        except Exception as e:
            logger.debug(f"Node extraction error: {e}")
            return None
    
    def _generate_node_id(self, tag: str, text: str, attributes: dict) -> str:
        """Generate unique node ID."""
        # Use tag + text + key attributes for stable ID
        id_str = f"{tag}:{text[:50]}"
        if "id" in attributes:
            id_str += f":id={attributes['id']}"
        if "class" in attributes:
            id_str += f":class={attributes['class'][:50]}"
        
        # Hash for uniqueness
        return hashlib.md5(id_str.encode()).hexdigest()[:12]
    
    async def _build_edges(self, graph: UIGraph):
        """Build parent-child edges in graph."""
        # For now, we'll infer edges from DOM structure hints
        # In production, we'd track actual parent relationships during extraction
        
        # Group by similar attributes to infer relationships
        for node in graph.nodes.values():
            # Find potential parents by DOM structure hints
            if "parent" in node.attributes:
                parent_id = node.attributes["parent"]
                if parent_id in graph.nodes:
                    node.parent_id = parent_id
                    graph.nodes[parent_id].children_ids.append(node.id)
                    graph.edges.append((parent_id, node.id))
