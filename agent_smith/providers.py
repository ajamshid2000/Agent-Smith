"""
LLM Provider Interface

This module handles communication with language models.

KEY DESIGN DECISION: OpenAI-compatible API
- Works with OpenAI, Claude, Llama, Mistral, etc.
- All use the same /v1/chat/completions endpoint format
- Easy to switch providers by just changing URL and model name

API KEY MANAGEMENT:
- Supports multiple keys (for rotating if one fails)
- Reads from environment variables automatically
- Never embeds credentials in code
"""

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Completion:
    """
    Response from LLM provider.
    
    WHY DATACLASS?
    - Simple container for related data
    - Easier to pass around than dict
    - Type-safe
    
    Attributes:
        text: The actual LLM response (code, reasoning, etc.)
        input_tokens: Tokens in the prompt (determines cost)
        output_tokens: Tokens in the response (determines cost)
        request_time_ms: How long the API call took (performance)
        retries: How many times we had to retry (reliability indicator)
    """
    text: str
    input_tokens: int
    output_tokens: int
    request_time_ms: float
    retries: int


def load_env_file(path: str = ".env") -> None:
    """
    Load KEY=VALUE entries from a .env file into environment.
    
    WHY A .env FILE?
    - Keeps sensitive credentials out of version control
    - .gitignore can exclude .env
    - Easy to use different keys per machine
    - Standard practice in web development
    
    Format:
        OPENAI_API_KEY=sk-abc123
        AGENT_SMITH_API_KEYS=key1,key2,key3
        # Comments are allowed
    """
    env_path = Path(path)
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip("\"'")
        if name:
            os.environ.setdefault(name, value)  # Don't override if already set


class OpenAIProvider:
    """
    LLM client for OpenAI-compatible APIs.
    
    WHY THIS CLASS?
    - Abstracts API communication details
    - Handles retries and key rotation
    - Measures performance (tokens, time)
    - Can be replaced with other providers if needed
    
    FEATURES:
    - API key rotation: if one key fails, try the next one
    - Token counting: tracks input/output for cost calculation
    - Request timing: measures API latency
    - Timeout protection: 120-second timeout prevents hanging
    - Support for different providers: OpenAI, Claude, local models, etc.
    """
    
    def __init__(self, model_name: str, provider_url: str, api_keys: list[str] | None = None):
        """
        Create an OpenAI-compatible client with optional explicit API keys.
        
        Args:
            model_name: Model identifier (e.g., "gpt-4-turbo", "claude-3.5-sonnet")
            provider_url: API endpoint (e.g., "https://api.openai.com/v1")
            api_keys: Optional list of keys to try in order
        """
        self.model_name = model_name
        self.provider_url = provider_url.rstrip("/")
        self.api_keys = api_keys or self._keys_from_environment()
        self._key_index = 0  # Track which key we're currently using

    def _keys_from_environment(self) -> list[str]:
        """
        Collect API keys from environment variables.
        
        SEARCH ORDER:
        1. AGENT_SMITH_API_KEYS (comma-separated list)
        2. Any variable containing "API_KEY" (e.g., OPENAI_API_KEY, ANTHROPIC_API_KEY)
        
        WHY MULTIPLE SOURCES?
        - AGENT_SMITH_API_KEYS: explicit list for this agent
        - Provider-specific keys: generic environment setup
        - Flexibility: works with different CI/CD systems and local setups
        """
        values = os.getenv("AGENT_SMITH_API_KEYS", "")
        keys = [value.strip() for value in values.split(",") if value.strip()]
        keys.extend(value for name, value in os.environ.items() if "API_KEY" in name and value not in keys)
        return keys

    def complete(self, system_prompt: str, user_prompt: str, max_tokens: int) -> Completion:
        """
        Generate one completion from the LLM.
        
        PROCESS:
        1. Build request JSON following OpenAI API format
        2. Try first key, if it fails try next key, etc.
        3. Parse response and extract tokens
        4. Return completion with metrics
        
        Args:
            system_prompt: System context (e.g., "You are Agent Smith")
            user_prompt: User's question/task
            max_tokens: Maximum tokens to generate (controls response length)
            
        Returns:
            Completion with response text and metrics
            
        Raises:
            RuntimeError: If all API keys fail
        """
        if not self.api_keys:
            raise RuntimeError("No API key configured; set AGENT_SMITH_API_KEYS or a provider API_KEY variable")
        
        # BUILD REQUEST in OpenAI format
        request_payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_completion_tokens": max_tokens
        }
        
        # PROVIDER-SPECIFIC ADJUSTMENT
        # OpenAI uses stop sequences, other providers might not support it
        if "api.openai.com" not in self.provider_url:
            request_payload["stop"] = ["<end_code>"]  # Stop generation at markers
        
        payload = json.dumps(request_payload).encode()
        retries = 0
        started = time.perf_counter()
        
        # RETRY LOOP: Try each key until one succeeds
        while retries <= len(self.api_keys):
            key = self.api_keys[self._key_index % len(self.api_keys)]
            self._key_index += 1
            
            # BUILD HTTP REQUEST
            request = urllib.request.Request(
                self.provider_url + "/chat/completions",
                payload,
                {
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json"
                }
            )
            
            try:
                # SEND REQUEST with 120-second timeout
                with urllib.request.urlopen(request, timeout=120) as response:
                    data = json.load(response)
                
                # PARSE RESPONSE
                choice = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                
                # RETURN SUCCESS
                return Completion(
                    choice,
                    int(usage.get("prompt_tokens", 0)),
                    int(usage.get("completion_tokens", 0)),
                    (time.perf_counter() - started) * 1000,  # Convert to ms
                    retries
                )
                
            except urllib.error.HTTPError as error:
                # API ERROR (wrong key, rate limit, etc.)
                detail = error.read().decode("utf-8", errors="replace").strip()
                retries += 1
                if retries > len(self.api_keys):
                    raise RuntimeError(f"LLM request failed after token rotation: HTTP {error.code}: {detail}") from error
                
            except (urllib.error.URLError, KeyError, IndexError, ValueError) as error:
                # NETWORK ERROR (connection failed, malformed response, etc.)
                retries += 1
                if retries > len(self.api_keys):
                    raise RuntimeError(f"LLM request failed after token rotation: {error}") from error