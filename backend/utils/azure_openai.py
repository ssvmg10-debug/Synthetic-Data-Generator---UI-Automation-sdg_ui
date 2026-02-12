"""
Azure OpenAI Helper Module
Provides unified interface for Azure OpenAI API calls
"""
import os
from dotenv import load_dotenv
from openai import AzureOpenAI
from typing import List, Dict, Any, Optional

# Load environment variables
load_dotenv()

# Azure OpenAI Configuration
AZURE_API_KEY = os.getenv("AZURE_API_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
AZURE_DEPLOYMENT = os.getenv("AZURE_DEPLOYMENT", "gpt-4.1")
AZURE_API_VERSION = os.getenv("AZURE_API_VERSION", "2024-02-15-preview")

# Initialize Azure OpenAI client
client = AzureOpenAI(
    api_key=AZURE_API_KEY,
    api_version=AZURE_API_VERSION,
    azure_endpoint=AZURE_ENDPOINT
)


def get_openai_client() -> AzureOpenAI:
    """
    Get the Azure OpenAI client instance
    
    Returns:
        AzureOpenAI client
    """
    return client


def chat_completion(
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    response_format: Optional[Dict[str, str]] = None
) -> str:
    """
    Send a chat completion request to Azure OpenAI
    
    Args:
        messages: List of message dictionaries with 'role' and 'content'
        temperature: Sampling temperature (0-2)
        max_tokens: Maximum tokens in response
        response_format: Optional response format specification (e.g., {"type": "json_object"})
    
    Returns:
        Response content as string
    """
    try:
        kwargs = {
            "model": AZURE_DEPLOYMENT,
            "messages": messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
            
        if response_format:
            kwargs["response_format"] = response_format
        
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content
    
    except Exception as e:
        raise Exception(f"Azure OpenAI API Error: {str(e)}")


def json_completion(
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: Optional[int] = None
) -> str:
    """
    Send a chat completion request with JSON response format
    
    Args:
        messages: List of message dictionaries with 'role' and 'content'
        temperature: Sampling temperature (0-2)
        max_tokens: Maximum tokens in response
    
    Returns:
        JSON response as string
    """
    return chat_completion(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"}
    )


def create_system_message(content: str) -> Dict[str, str]:
    """Create a system message"""
    return {"role": "system", "content": content}


def create_user_message(content: str) -> Dict[str, str]:
    """Create a user message"""
    return {"role": "user", "content": content}


def create_assistant_message(content: str) -> Dict[str, str]:
    """Create an assistant message"""
    return {"role": "assistant", "content": content}


# Verify configuration on import
def verify_config():
    """Verify Azure OpenAI configuration"""
    missing = []
    if not AZURE_API_KEY:
        missing.append("AZURE_API_KEY")
    if not AZURE_ENDPOINT:
        missing.append("AZURE_ENDPOINT")
    
    if missing:
        raise ValueError(
            f"Missing Azure OpenAI configuration: {', '.join(missing)}\n"
            "Please set these variables in your .env file"
        )

# Verify configuration on module import
try:
    verify_config()
except ValueError as e:
    print(f"Warning: {e}")
