"""
UI Test Validator Agent
Validates selectors and test structure
"""
from typing import Dict, Any, List

class ValidatorAgent:
    def validate(self, structured_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Validate structured test plan"""
        issues = []
        warnings = []
        
        # Check if URL is valid
        url = structured_plan.get('url', '')
        if not url or not url.startswith('http'):
            issues.append("Invalid or missing URL")
        
        # Check steps
        steps = structured_plan.get('steps', [])
        if not steps:
            issues.append("No test steps found")
        
        # Validate each step
        for step in steps:
            action = step.get('action')
            step_num = step.get('step', 0)
            
            if action in ['click', 'type', 'select', 'verify']:
                selector = step.get('selector', '')
                if not selector or selector == 'unknown':
                    warnings.append(f"Step {step_num}: Missing or invalid selector for {action} action")
                
                # Check for common selector issues
                if selector:
                    if selector.count('[') != selector.count(']'):
                        issues.append(f"Step {step_num}: Malformed selector '{selector}'")
                    
                    if selector.startswith('button:has-text') or selector.startswith('a:has-text'):
                        # Valid Playwright selector, but warn about text changes
                        warnings.append(f"Step {step_num}: Text-based selector may break if UI text changes")
            
            if action == 'type':
                value = step.get('value', '')
                if not value:
                    warnings.append(f"Step {step_num}: Empty value for type action")
            
            if action == 'verify':
                expected = step.get('expected', '')
                if not expected:
                    warnings.append(f"Step {step_num}: No expected value specified for verification")
        
        is_valid = len(issues) == 0
        
        return {
            "is_valid": is_valid,
            "issues": issues,
            "warnings": warnings,
            "total_steps": len(steps),
            "validated_steps": len([s for s in steps if s.get('action') not in ['comment']])
        }
    
    def suggest_improvements(self, structured_plan: Dict[str, Any]) -> List[str]:
        """Suggest improvements to the test plan"""
        suggestions = []
        steps = structured_plan.get('steps', [])
        
        # Check for explicit waits
        has_waits = any(step.get('action') == 'wait' for step in steps)
        if not has_waits:
            suggestions.append("Consider adding explicit waits for dynamic content")
        
        # Check for verifications
        has_verify = any(step.get('action') == 'verify' for step in steps)
        if not has_verify:
            suggestions.append("Add verification steps to validate expected behavior")
        
        # Check for proper test structure
        if len(steps) > 20:
            suggestions.append("Consider breaking down into smaller, focused tests")
        
        return suggestions
