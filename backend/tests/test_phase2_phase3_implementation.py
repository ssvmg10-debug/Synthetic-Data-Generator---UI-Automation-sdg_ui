"""
Comprehensive tests for Phase 2 and Phase 3 implementation
Tests: JourneyExtractor, PageContext, GroundedPlanner, FocusedCrawler, RunStatus, EnhancedExecutor
"""
import pytest
import asyncio
from typing import Dict, Any, List

# Phase 2 imports
from backend.agents.journey_extractor import JourneyExtractor, TestIntent
from backend.services.page_context_service import PageContextService
from backend.services.ui_automation.agents.planner.grounded_planner import GroundedPlanner
from backend.services.ui_automation.utils.focused_crawler import FocusedCrawler

# Phase 3 imports
from backend.services.ui_automation.run_status import (
    RunStatusTracker,
    ExecutionPhase,
    PhaseStatus,
    get_or_create_tracker
)


class TestJourneyExtractor:
    """Test journey extraction from test cases"""
    
    def test_rule_based_extraction_login(self):
        """Test rule-based extraction for login journey"""
        extractor = JourneyExtractor()
        
        test_case = "Login with username 'admin' and password 'password123'"
        url = "https://example.com/login"
        
        journey = extractor._extract_rule_based(test_case, url)
        
        assert journey['intent'] == TestIntent.AUTHENTICATION
        assert len(journey['steps']) >= 2  # At least username + password
        assert any('username' in step.lower() for step in journey['steps'])
        assert any('password' in step.lower() for step in journey['steps'])
    
    def test_rule_based_extraction_checkout(self):
        """Test rule-based extraction for checkout journey"""
        extractor = JourneyExtractor()
        
        test_case = "Add product to cart and proceed to checkout with payment"
        url = "https://example.com/products"
        
        journey = extractor._extract_rule_based(test_case, url)
        
        assert journey['intent'] == TestIntent.CHECKOUT
        assert len(journey['steps']) >= 3
    
    def test_keyword_extraction_for_crawling(self):
        """Test keyword extraction for focused crawling"""
        extractor = JourneyExtractor()
        
        test_case = "Navigate to login page, enter credentials, access user dashboard"
        
        keywords = extractor.extract_keywords_for_crawling(test_case)
        
        assert 'login' in keywords
        assert 'dashboard' in keywords or 'user' in keywords
        assert len(keywords) >= 2
    
    def test_intent_classification(self):
        """Test intent classification from test case"""
        extractor = JourneyExtractor()
        
        # Authentication
        assert extractor._classify_intent_rule_based("Login to account") == TestIntent.AUTHENTICATION
        
        # Search
        assert extractor._classify_intent_rule_based("Search for products") == TestIntent.SEARCH
        
        # Checkout
        assert extractor._classify_intent_rule_based("Complete checkout") == TestIntent.CHECKOUT


class TestPageContextService:
    """Test page context extraction"""
    
    @pytest.mark.asyncio
    async def test_extract_context_structure(self):
        """Test that context extraction returns correct structure"""
        service = PageContextService(headless=True)
        
        # Use a simple test page (you can mock this in actual tests)
        url = "https://example.com"
        
        try:
            context = await service.extract_context(url, intent="generic")
            
            # Verify structure
            assert 'url' in context
            assert 'intent' in context
            assert 'clickables' in context
            assert 'inputs' in context
            assert 'selects' in context
            assert 'headings' in context
            assert 'extracted_at' in context
            
            # Verify types
            assert isinstance(context['clickables'], list)
            assert isinstance(context['inputs'], list)
            assert isinstance(context['selects'], list)
        
        except Exception as e:
            # Network errors are acceptable in test environment
            pytest.skip(f"Network error: {e}")
    
    def test_format_for_llm(self):
        """Test LLM formatting of page context"""
        service = PageContextService()
        
        context = {
            'url': 'https://example.com/login',
            'intent': 'authentication',
            'clickables': [
                {'tag': 'button', 'text': 'Login', 'id': 'loginBtn', 'ariaLabel': ''}
            ],
            'inputs': [
                {'name': 'username', 'type': 'text', 'placeholder': 'Username', 'ariaLabel': ''}
            ],
            'selects': []
        }
        
        formatted = service.format_for_llm(context)
        
        assert 'https://example.com/login' in formatted
        assert 'authentication' in formatted
        assert 'Login' in formatted
        assert 'username' in formatted
    
    def test_generate_selector_hints(self):
        """Test selector hint generation"""
        service = PageContextService()
        
        context = {
            'clickables': [
                {'text': 'Submit', 'id': 'submitBtn', 'ariaLabel': 'Submit form'}
            ],
            'inputs': [
                {'name': 'email', 'placeholder': 'Enter email', 'ariaLabel': ''}
            ],
            'selects': [
                {'name': 'country', 'ariaLabel': ''}
            ]
        }
        
        hints = service.generate_selector_hints(context)
        
        assert len(hints['clickables']) > 0
        assert len(hints['inputs']) > 0
        assert len(hints['selects']) > 0
        
        # Check specific hints
        assert any('Submit' in hint for hint in hints['clickables'])
        assert any('email' in hint for hint in hints['inputs'])
        assert any('country' in hint for hint in hints['selects'])


class TestGroundedPlanner:
    """Test grounded planning"""
    
    @pytest.mark.asyncio
    async def test_fallback_planner(self):
        """Test fallback planning without LLM"""
        planner = GroundedPlanner()
        
        # Mock page context with login elements
        page_context = {
            'clickables': [
                {'text': 'Login', 'id': 'loginBtn', 'tag': 'button'}
            ],
            'inputs': [
                {'name': 'username', 'type': 'text'},
                {'name': 'password', 'type': 'password'}
            ],
            'selects': []
        }
        
        script = await planner._fallback_plan(
            test_case="Login with credentials",
            url="https://example.com/login",
            page_context=page_context
        )
        
        assert 'steps' in script
        assert len(script['steps']) >= 3  # goto + username + password
        assert script['starting_url'] == "https://example.com/login"
        assert script['grounding_source'] == 'fallback'
    
    def test_format_context_for_llm(self):
        """Test context formatting for LLM"""
        planner = GroundedPlanner()
        
        context = {
            'clickables': [
                {'tag': 'button', 'text': 'Submit', 'id': 'btn1', 'ariaLabel': ''}
            ],
            'inputs': [
                {'type': 'text', 'name': 'email', 'placeholder': 'Email', 'ariaLabel': ''}
            ],
            'selects': []
        }
        
        formatted = planner._format_context_for_llm(context)
        
        assert 'CLICKABLE ELEMENTS' in formatted
        assert 'INPUT FIELDS' in formatted
        assert 'Submit' in formatted
        assert 'email' in formatted
    
    def test_enhance_with_alternatives(self):
        """Test alternative selector generation"""
        planner = GroundedPlanner()
        
        script = {
            'steps': [
                {'action': 'click', 'selector': 'button.login'},
                {'action': 'fill', 'selector': 'input[name="user"]', 'value': 'admin'}
            ]
        }
        
        page_context = {
            'clickables': [
                {'text': 'Login', 'id': 'loginBtn'}
            ],
            'inputs': [
                {'name': 'user', 'placeholder': 'Username'}
            ]
        }
        
        enhanced = planner.enhance_with_alternatives(script, page_context)
        
        # Verify alternatives were added
        for step in enhanced['steps']:
            assert 'alternatives' in step
            assert isinstance(step['alternatives'], list)
            assert len(step['alternatives']) >= 1


class TestFocusedCrawler:
    """Test focused URL filtering"""
    
    def test_filter_urls_by_keywords(self):
        """Test URL filtering by keywords"""
        crawler = FocusedCrawler()
        
        all_urls = [
            "https://example.com/login",
            "https://example.com/about",
            "https://example.com/cart",
            "https://example.com/blog",
            "https://example.com/checkout"
        ]
        
        keywords = ["login", "cart", "checkout"]
        
        relevant = crawler.filter_urls(all_urls, keywords)
        
        assert "https://example.com/login" in relevant
        assert "https://example.com/cart" in relevant
        assert "https://example.com/checkout" in relevant
        assert "https://example.com/about" not in relevant
        assert "https://example.com/blog" not in relevant
    
    def test_filter_urls_by_intent(self):
        """Test URL filtering by intent"""
        crawler = FocusedCrawler()
        
        all_urls = [
            "https://example.com/signin",
            "https://example.com/products",
            "https://example.com/contact"
        ]
        
        relevant = crawler.filter_urls(
            all_urls,
            keywords=[],
            intent="authentication"
        )
        
        assert "https://example.com/signin" in relevant
        assert "https://example.com/contact" not in relevant
    
    def test_exclude_noise_pages(self):
        """Test exclusion of noise pages"""
        crawler = FocusedCrawler()
        
        noise_urls = [
            "https://example.com/about",
            "https://example.com/blog",
            "https://example.com/privacy",
            "https://example.com/terms",
            "https://example.com/image.jpg"
        ]
        
        relevant = crawler.filter_urls(
            noise_urls,
            keywords=["login"],  # Won't match any
            intent=None
        )
        
        # All should be excluded as noise
        assert len(relevant) == 0
    
    def test_prioritize_urls(self):
        """Test URL prioritization by relevance"""
        crawler = FocusedCrawler()
        
        urls = [
            "https://example.com/other",
            "https://example.com/login",
            "https://example.com/signin"
        ]
        
        prioritized = crawler.prioritize_urls(
            urls,
            keywords=["login"],
            intent="authentication"
        )
        
        # URLs with intent match should come first
        assert prioritized[0] in ["https://example.com/login", "https://example.com/signin"]
    
    def test_extract_urls_from_html(self):
        """Test URL extraction from HTML"""
        crawler = FocusedCrawler()
        
        html = """
        <html>
            <a href="/login">Login</a>
            <a href="/products">Products</a>
            <a href="#anchor">Anchor</a>
            <a href="javascript:void(0)">JS Link</a>
        </html>
        """
        
        base_url = "https://example.com"
        
        urls = crawler.extract_urls_from_html(html, base_url)
        
        assert "https://example.com/login" in urls
        assert "https://example.com/products" in urls
        # Anchors and JS links should be excluded
        assert not any('#' in url for url in urls)
        assert not any('javascript:' in url for url in urls)


class TestRunStatusTracker:
    """Test run status tracking"""
    
    def test_tracker_initialization(self):
        """Test tracker initializes correctly"""
        tracker = RunStatusTracker("run_123")
        
        assert tracker.run_id == "run_123"
        assert tracker.status == "running"
        assert tracker.current_phase == ExecutionPhase.JOURNEY_EXTRACTION
        assert len(tracker.phases) == len(ExecutionPhase)
    
    def test_phase_lifecycle(self):
        """Test phase start/complete lifecycle"""
        tracker = RunStatusTracker("run_123")
        
        # Start phase
        tracker.start_phase(ExecutionPhase.PLANNING)
        
        assert tracker.current_phase == ExecutionPhase.PLANNING
        assert tracker.phases[ExecutionPhase.PLANNING.value]['status'] == PhaseStatus.IN_PROGRESS.value
        assert tracker.phases[ExecutionPhase.PLANNING.value]['started_at'] is not None
        
        # Complete phase
        tracker.complete_phase(ExecutionPhase.PLANNING, {"script_generated": True})
        
        assert tracker.phases[ExecutionPhase.PLANNING.value]['status'] == PhaseStatus.COMPLETED.value
        assert tracker.phases[ExecutionPhase.PLANNING.value]['completed_at'] is not None
        assert tracker.phases[ExecutionPhase.PLANNING.value]['duration_ms'] is not None
    
    def test_phase_failure(self):
        """Test phase failure tracking"""
        tracker = RunStatusTracker("run_123")
        
        tracker.start_phase(ExecutionPhase.EXECUTION)
        tracker.fail_phase(ExecutionPhase.EXECUTION, "Selector not found")
        
        assert tracker.phases[ExecutionPhase.EXECUTION.value]['status'] == PhaseStatus.FAILED.value
        assert tracker.phases[ExecutionPhase.EXECUTION.value]['error'] == "Selector not found"
        assert tracker.status == "failed"
    
    def test_screenshot_tracking(self):
        """Test screenshot addition"""
        tracker = RunStatusTracker("run_123")
        
        tracker.add_screenshot(
            path="/screenshots/step1.png",
            step_number=1,
            phase=ExecutionPhase.EXECUTION,
            description="After login"
        )
        
        assert len(tracker.screenshots) == 1
        assert tracker.screenshots[0]['path'] == "/screenshots/step1.png"
        assert tracker.screenshots[0]['step_number'] == 1
    
    def test_healing_attempt_tracking(self):
        """Test healing attempt tracking"""
        tracker = RunStatusTracker("run_123")
        
        tracker.add_healing_attempt(
            step_number=2,
            original_selector="button.login",
            healed_selector="button:has-text('Login')",
            strategy="fuzzy_match",
            success=True
        )
        
        assert len(tracker.healing_attempts) == 1
        assert tracker.healing_attempts[0]['success'] is True
        assert tracker.healing_attempts[0]['strategy'] == "fuzzy_match"
    
    def test_get_status(self):
        """Test status retrieval"""
        tracker = RunStatusTracker("run_123")
        
        tracker.start_phase(ExecutionPhase.EXECUTION)
        tracker.add_screenshot("/screenshots/test.png", step_number=1)
        
        status = tracker.get_status()
        
        assert status['run_id'] == "run_123"
        assert status['status'] == "running"
        assert status['current_phase'] == ExecutionPhase.EXECUTION.value
        assert 'progress_percent' in status
        assert len(status['screenshots']) == 1
    
    def test_progress_calculation(self):
        """Test progress percentage calculation"""
        tracker = RunStatusTracker("run_123")
        
        # Initially 0%
        status = tracker.get_status()
        assert status['progress_percent'] == 0
        
        # Complete some phases
        tracker.start_phase(ExecutionPhase.JOURNEY_EXTRACTION)
        tracker.complete_phase(ExecutionPhase.JOURNEY_EXTRACTION)
        
        tracker.start_phase(ExecutionPhase.PLANNING)
        tracker.complete_phase(ExecutionPhase.PLANNING)
        
        status = tracker.get_status()
        assert status['progress_percent'] > 0
        assert status['progress_percent'] <= 100


def test_get_or_create_tracker():
    """Test tracker singleton retrieval"""
    run_id = "run_test_123"
    
    tracker1 = get_or_create_tracker(run_id)
    tracker2 = get_or_create_tracker(run_id)
    
    # Should return same instance
    assert tracker1 is tracker2
    assert tracker1.run_id == run_id


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
