# Azure OpenAI Integration Guide

## Overview

The platform uses Azure OpenAI Service for all AI-powered features across the three modules:
- Synthetic Data Generator: Schema analysis and data generation planning
- UI Automation: Test planning, script generation, and self-healing
- API Automation: Test planning, request generation, and validation

## Configuration

### Environment Variables

Add these variables to your `.env` file:

```env
# Azure OpenAI Configuration
AZURE_API_KEY=your_azure_api_key_here
AZURE_ENDPOINT=https://your-endpoint.cognitiveservices.azure.com/
AZURE_DEPLOYMENT=gpt-4.1
AZURE_API_VERSION=2024-02-15-preview
```

### Getting Azure OpenAI Credentials

1. **Azure Portal**: Navigate to your Azure OpenAI resource
2. **Keys and Endpoint**: Copy the following:
   - API Key (Key 1 or Key 2)
   - Endpoint URL
3. **Deployments**: Note your GPT-4 deployment name
4. **API Version**: Use the latest stable version (2024-02-15-preview recommended)

## Usage in Code

### Import the Helper Module

```python
from utils.azure_openai import (
    chat_completion,
    json_completion,
    create_system_message,
    create_user_message,
    create_assistant_message
)
```

### Basic Chat Completion

```python
messages = [
    create_system_message("You are a helpful assistant specialized in test automation."),
    create_user_message("Generate a test plan for a login page.")
]

response = chat_completion(messages, temperature=0.7)
print(response)
```

### JSON Response Format

For structured responses (recommended for agent outputs):

```python
messages = [
    create_system_message(
        "You are a test planning agent. "
        "Respond with valid JSON containing: plan, steps, assertions."
    ),
    create_user_message("Create a test plan for login functionality")
]

# This forces JSON output format
response = json_completion(messages, temperature=0.5)
import json
plan = json.loads(response)
```

### Advanced Options

```python
response = chat_completion(
    messages=messages,
    temperature=0.7,          # 0-2, lower = more deterministic
    max_tokens=2000,          # Limit response length
    response_format={"type": "json_object"}  # Force JSON output
)
```

## AI Agent Integration

### Example: UI Test Planner Agent

```python
from utils.azure_openai import json_completion, create_system_message, create_user_message

def plan_ui_tests(feature_description: str, page_url: str) -> dict:
    """
    Use Azure OpenAI to plan UI tests
    """
    system_prompt = """
    You are an expert QA automation engineer specializing in UI testing.
    Given a feature description and page URL, create a comprehensive test plan.
    
    Respond with JSON:
    {
        "test_cases": [
            {
                "name": "test case name",
                "steps": ["step 1", "step 2"],
                "assertions": ["assertion 1", "assertion 2"],
                "priority": "high|medium|low"
            }
        ],
        "data_requirements": ["field1", "field2"]
    }
    """
    
    user_prompt = f"""
    Feature: {feature_description}
    Page URL: {page_url}
    
    Create a detailed test plan.
    """
    
    messages = [
        create_system_message(system_prompt),
        create_user_message(user_prompt)
    ]
    
    response = json_completion(messages, temperature=0.5)
    return json.loads(response)
```

### Example: Test Script Generator

```python
def generate_playwright_script(test_plan: dict, page_structure: dict) -> str:
    """
    Generate Playwright test script from plan
    """
    system_prompt = """
    You are a Playwright expert. Generate Python test code using pytest and Playwright.
    Follow best practices: use proper waits, assertions, and page objects.
    """
    
    user_prompt = f"""
    Test Plan:
    {json.dumps(test_plan, indent=2)}
    
    Page Structure:
    {json.dumps(page_structure, indent=2)}
    
    Generate complete Playwright test code.
    """
    
    messages = [
        create_system_message(system_prompt),
        create_user_message(user_prompt)
    ]
    
    return chat_completion(messages, temperature=0.3)
```

### Example: Self-Healing Agent

```python
def heal_broken_locator(
    original_locator: str,
    error_message: str,
    page_snapshot: dict
) -> dict:
    """
    AI-powered locator healing
    """
    system_prompt = """
    You are a locator healing expert. When a locator fails, analyze the page
    and suggest alternative locators.
    
    Respond with JSON:
    {
        "suggested_locators": [
            {"type": "css", "value": "...", "confidence": 0.9},
            {"type": "xpath", "value": "...", "confidence": 0.8}
        ],
        "analysis": "explanation of what changed"
    }
    """
    
    user_prompt = f"""
    Failed Locator: {original_locator}
    Error: {error_message}
    
    Current Page Elements:
    {json.dumps(page_snapshot, indent=2)}
    
    Suggest alternative locators.
    """
    
    messages = [
        create_system_message(system_prompt),
        create_user_message(user_prompt)
    ]
    
    response = json_completion(messages, temperature=0.3)
    return json.loads(response)
```

## Best Practices

### 1. Temperature Settings

- **0.0-0.3**: Deterministic, factual responses (code generation, validation)
- **0.4-0.7**: Balanced creativity (test planning, analysis)
- **0.8-2.0**: High creativity (exploratory testing, edge cases)

### 2. Prompt Engineering

**Good Prompts:**
```python
system_prompt = """
You are [specific role].
Your task is to [specific task].

Output format: [specific format with example]

Constraints:
- [constraint 1]
- [constraint 2]

Example:
[show example]
"""
```

**Bad Prompts:**
```python
# Too vague
system_prompt = "Help me test this"

# No output format
user_prompt = "Analyze this page"
```

### 3. Error Handling

```python
from utils.azure_openai import chat_completion

try:
    response = chat_completion(messages)
except Exception as e:
    if "rate_limit" in str(e):
        # Handle rate limiting
        time.sleep(60)
        response = chat_completion(messages)
    elif "context_length" in str(e):
        # Handle token limit
        # Truncate input or split into chunks
        pass
    else:
        # Log and handle other errors
        logger.error(f"Azure OpenAI error: {e}")
        raise
```

### 4. Token Management

```python
def estimate_tokens(text: str) -> int:
    """Rough estimation: 1 token ≈ 4 characters"""
    return len(text) // 4

def truncate_context(context: str, max_tokens: int = 6000) -> str:
    """Keep context within token limits"""
    if estimate_tokens(context) > max_tokens:
        # Truncate to approximate character count
        max_chars = max_tokens * 4
        return context[:max_chars] + "\n[...truncated...]"
    return context
```

### 5. Response Validation

```python
import json

def safe_json_parse(response: str) -> dict:
    """Safely parse JSON response with fallback"""
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code blocks
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0]
            return json.loads(json_str)
        raise ValueError("Invalid JSON response from AI")
```

## Monitoring and Costs

### Track API Usage

```python
from utils.azure_openai import client
import logging

logger = logging.getLogger(__name__)

def log_api_call(prompt_tokens: int, completion_tokens: int, model: str):
    """Log API usage for monitoring"""
    total_tokens = prompt_tokens + completion_tokens
    logger.info(
        f"Azure OpenAI Call - Model: {model}, "
        f"Prompt: {prompt_tokens}, Completion: {completion_tokens}, "
        f"Total: {total_tokens}"
    )
```

### Cost Estimation

GPT-4 Pricing (as of 2024):
- Prompt tokens: $0.01 per 1K tokens
- Completion tokens: $0.03 per 1K tokens

Example: 1000 test generations with 500 prompt + 1500 completion tokens each:
- Cost = 1000 × (0.5K × $0.01 + 1.5K × $0.03) = $50

## Troubleshooting

### Common Issues

1. **"API key not found"**
   - Ensure `.env` file exists in project root
   - Verify `AZURE_API_KEY` is set correctly
   - Check file is not named `.env.txt`

2. **"Deployment not found"**
   - Verify `AZURE_DEPLOYMENT` matches your Azure deployment name
   - Check deployment is in "Succeeded" state in Azure Portal

3. **"Rate limit exceeded"**
   - Implement exponential backoff
   - Consider request queuing
   - Check Azure OpenAI quota limits

4. **"Context length exceeded"**
   - Reduce prompt size
   - Truncate input data
   - Use smaller context window

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# This will show all API calls and responses
from utils import azure_openai
```

## Security Best Practices

1. **Never commit `.env` file** - Add to `.gitignore`
2. **Use environment-specific keys** - Different keys for dev/staging/prod
3. **Rotate keys regularly** - Azure allows two keys for zero-downtime rotation
4. **Monitor usage** - Set up Azure alerts for unusual activity
5. **Limit permissions** - Use least-privilege access in Azure RBAC

## Further Reading

- [Azure OpenAI Service Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [Prompt Engineering Guide](https://platform.openai.com/docs/guides/prompt-engineering)
- [Azure OpenAI Best Practices](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/work-with-code)
