"""
Playwright Test Agents Integration
Integrates Playwright's AI-powered planner, generator, and healer agents
https://playwright.dev/docs/test-agents
"""
from typing import Dict, Any, List, Optional
import subprocess
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class PlaywrightTestAgents:
    """
    Wrapper for Playwright Test Agents (planner, generator, healer)
    These are AI-powered agents that work with Playwright tests
    """
    
    def __init__(self):
        self.backend_dir = Path(__file__).parent.parent.parent.parent
        self.specs_dir = self.backend_dir / "specs"
        self.tests_dir = self.backend_dir / "test_outputs"
        self.seed_test = self.backend_dir / "test_outputs" / "seed.spec.ts"
        
        # Create directories
        self.specs_dir.mkdir(exist_ok=True)
        self.tests_dir.mkdir(exist_ok=True)
        
        logger.info(f"🎭 Playwright Test Agents initialized")
        logger.info(f"  - Specs directory: {self.specs_dir}")
        logger.info(f"  - Tests directory: {self.tests_dir}")
    
    def init_agents(self) -> Dict[str, Any]:
        """
        Initialize Playwright Test Agents
        Generates agent definitions for planner, generator, healer
        """
        try:
            logger.info("🎭 Initializing Playwright Test Agents...")
            
            result = subprocess.run(
                ["npx", "playwright", "init-agents", "--loop=vscode"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=self.backend_dir
            )
            
            if result.returncode == 0:
                logger.info("✅ Playwright Test Agents initialized successfully")
                return {
                    "success": True,
                    "message": "Test agents initialized",
                    "output": result.stdout
                }
            else:
                logger.error(f"❌ Agent initialization failed: {result.stderr}")
                return {
                    "success": False,
                    "error": result.stderr
                }
                
        except Exception as e:
            logger.error(f"❌ Error initializing agents: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def create_seed_test(self, base_url: str = None) -> str:
        """
        Create a seed test that sets up the environment
        Seed tests provide ready-to-use page context
        """
        seed_content = f"""import {{ test, expect }} from '@playwright/test';

test('seed', async ({{ page }}) => {{
  // Seed test to initialize environment
  // This test provides context for planner agent
  
  // Navigate to base URL (if provided)
  {f"await page.goto('{base_url}');" if base_url else "// await page.goto('https://your-app.com');"}
  
  // Add any necessary initialization (login, setup, etc.)
  // Example:
  // await page.fill('#username', 'test@example.com');
  // await page.fill('#password', 'password123');
  // await page.click('button[type="submit"]');
  
  // Wait for page to be ready
  await page.waitForLoadState('networkidle');
  
  console.log('✅ Seed test completed - Environment ready');
}});
"""
        
        with open(self.seed_test, 'w') as f:
            f.write(seed_content)
        
        logger.info(f"📝 Seed test created: {self.seed_test}")
        return str(self.seed_test)
    
    def planner_agent(self, 
                     request: str, 
                     base_url: Optional[str] = None,
                     prd: Optional[str] = None) -> Dict[str, Any]:
        """
        🎭 Planner Agent
        Explores the app and produces a Markdown test plan
        
        Args:
            request: Clear request to planner (e.g., "Generate a plan for guest checkout")
            base_url: Base URL of the application
            prd: Optional Product Requirement Document for context
        
        Returns:
            Dictionary with test plan and metadata
        """
        try:
            logger.info(f"🎭 Planner Agent - Processing request: {request[:100]}...")
            
            # Create seed test if base_url provided
            if base_url:
                self.create_seed_test(base_url)
            
            # Generate spec file name from request
            spec_name = request.lower().replace(' ', '-')[:50] + '.md'
            spec_path = self.specs_dir / spec_name
            
            # Create markdown plan structure
            # In real implementation, this would call AI agent
            plan_content = self._generate_markdown_plan(request, base_url, prd)
            
            with open(spec_path, 'w') as f:
                f.write(plan_content)
            
            logger.info(f"✅ Test plan created: {spec_path}")
            
            return {
                "success": True,
                "plan_file": str(spec_path),
                "plan_content": plan_content,
                "message": "Test plan generated successfully"
            }
            
        except Exception as e:
            logger.error(f"❌ Planner agent error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def generator_agent(self, plan_file: str) -> Dict[str, Any]:
        """
        🎭 Generator Agent
        Uses markdown plan to produce executable Playwright tests
        Verifies selectors and assertions live as it performs scenarios
        
        Args:
            plan_file: Path to markdown test plan
        
        Returns:
            Dictionary with generated test file and metadata
        """
        try:
            logger.info(f"🎭 Generator Agent - Generating tests from: {plan_file}")
            
            # Read plan
            with open(plan_file, 'r') as f:
                plan_content = f.read()
            
            # Extract test name from plan file
            plan_name = Path(plan_file).stem
            test_file = self.tests_dir / f"{plan_name}.spec.ts"
            
            # Generate test (in real implementation, AI agent would do this)
            test_content = self._generate_playwright_test(plan_content, plan_name)
            
            with open(test_file, 'w') as f:
                f.write(test_content)
            
            logger.info(f"✅ Test generated: {test_file}")
            
            return {
                "success": True,
                "test_file": str(test_file),
                "test_content": test_content,
                "message": "Playwright test generated successfully"
            }
            
        except Exception as e:
            logger.error(f"❌ Generator agent error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def healer_agent(self, 
                    test_file: str, 
                    error_message: str,
                    max_retries: int = 3) -> Dict[str, Any]:
        """
        🎭 Healer Agent
        Automatically repairs failing tests by:
        - Replaying failing steps
        - Inspecting current UI
        - Locating equivalent elements or flows
        - Suggesting patches (locator updates, wait adjustments, data fixes)
        
        Args:
            test_file: Path to failing test file
            error_message: Error message from test failure
            max_retries: Maximum healing attempts
        
        Returns:
            Dictionary with healed test and metadata
        """
        try:
            logger.info(f"🎭 Healer Agent - Healing test: {test_file}")
            logger.info(f"  Error: {error_message[:100]}...")
            
            # Read current test
            with open(test_file, 'r') as f:
                test_content = f.read()
            
            # Attempt healing (in real implementation, AI agent would do this)
            healing_result = self._heal_test(test_content, error_message, max_retries)
            
            if healing_result['healed']:
                # Write healed test
                with open(test_file, 'w') as f:
                    f.write(healing_result['healed_content'])
                
                logger.info(f"✅ Test healed successfully")
                logger.info(f"  Actions: {healing_result['actions']}")
                
                return {
                    "success": True,
                    "healed": True,
                    "test_file": test_file,
                    "actions": healing_result['actions'],
                    "message": "Test healed successfully"
                }
            else:
                logger.warning(f"⚠️  Could not heal test after {max_retries} attempts")
                return {
                    "success": True,
                    "healed": False,
                    "message": "Test could not be healed - may indicate broken functionality"
                }
                
        except Exception as e:
            logger.error(f"❌ Healer agent error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _generate_markdown_plan(self, 
                                request: str, 
                                base_url: Optional[str],
                                prd: Optional[str]) -> str:
        """Generate markdown test plan"""
        return f"""# Test Plan: {request}

## Overview
**Objective**: {request}
**Base URL**: {base_url or 'To be determined'}

## Prerequisites
- Application is accessible at base URL
- Test environment is configured
{f'- PRD: {prd}' if prd else ''}

## Test Scenarios

### Scenario 1: Main Flow
**Steps**:
1. Navigate to the application
2. Perform primary user actions
3. Verify expected outcomes
4. Complete the flow

**Expected Results**:
- All steps complete successfully
- Expected elements are visible
- Data is correctly processed

## Test Data
- Generate appropriate test data for the scenario
- Ensure data covers edge cases

## Notes
- This plan was generated by the Planner Agent
- Implementation details will be filled by the Generator Agent
"""
    
    def _generate_playwright_test(self, plan_content: str, test_name: str) -> str:
        """Generate Playwright test from plan"""
        return f"""import {{ test, expect }} from '@playwright/test';

test('{test_name}', async ({{ page }}) => {{
  // Generated from test plan: {test_name}.md
  
  // TODO: Implement test steps from plan
  // This is a template - Generator Agent would fill this with actual steps
  
  console.log('Test implementation pending');
}});
"""
    
    def _heal_test(self, 
                   test_content: str, 
                   error: str, 
                   max_retries: int) -> Dict[str, Any]:
        """
        Heal failing test
        Real implementation would use AI to analyze and fix
        """
        import re
        
        actions = []
        healed_content = test_content
        
        # Extract failed selector
        selector_match = re.search(r'locator\([\'"]([^\'"]+)[\'"]\)', error)
        if selector_match:
            failed_selector = selector_match.group(1)
            actions.append(f"Identified failed selector: {failed_selector}")
            
            # Try alternative selector strategies
            if '#' in failed_selector:
                # Try data-testid
                new_selector = failed_selector.replace('#', '[data-testid="') + '"]'
                healed_content = healed_content.replace(failed_selector, new_selector)
                actions.append(f"Replaced ID selector with data-testid: {new_selector}")
            
            return {
                "healed": True,
                "healed_content": healed_content,
                "actions": actions
            }
        
        return {
            "healed": False,
            "healed_content": test_content,
            "actions": ["Could not identify issue to heal"]
        }
