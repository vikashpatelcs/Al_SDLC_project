"""
Offline LLM Gateway with Integrated Pre-Flight PII Masking.
Enforces strict offline-only policy: refuses any non-local base URL.
Routes requests to local Ollama via OpenAI-compatible endpoints.
"""
import time
import urllib.parse
from typing import Dict, List, Optional, Any, Tuple
import httpx

from backend.app.config import settings
from backend.app.core.security.masking import pii_masker, ReversibleVault
from backend.app.core.security.injection import injection_scanner


class NonLocalURLError(ValueError):
    """Raised when an outbound LLM request targets a non-local address."""
    pass


def is_local_url(url: str) -> bool:
    """
    Validate that base URL targets localhost or loopback address only.
    Rejects any cloud, hosted, or public internet endpoints.
    """
    if not url:
        return False

    parsed = urllib.parse.urlparse(url)
    hostname = (parsed.hostname or "").lower()

    # Allowed local hosts
    if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return True

    # Reject known online LLM providers explicitly
    disallowed_domains = [
        "openai.com", "anthropic.com", "cohere.com", "together.ai",
        "groq.com", "mistral.ai", "deepseek.com", "huggingface.co"
    ]
    if any(domain in hostname for domain in disallowed_domains):
        return False

    return False


class GatewayResponse:
    def __init__(
        self,
        content: str,
        model_version: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        vault: ReversibleVault,
    ):
        self.content = content
        self.model_version = model_version
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens
        self.latency_ms = latency_ms
        self.vault = vault


class LLMGateway:
    """
    Central, secure gateway for all LLM calls across all agents.
    Guarantees:
      1. Rejection of non-local URLs (Offline LLM policy).
      2. Pre-flight PII masking inside the gateway (cannot be bypassed).
      3. Token tracking, timeout handling, and latency profiling.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: float = 60.0,
    ):
        self.base_url = (base_url or "http://127.0.0.1:11434").rstrip("/")
        self.model_name = model_name or "qwen2.5:3b"
        self.timeout_seconds = timeout_seconds

        # Enforce offline policy on initialization
        if not is_local_url(self.base_url):
            raise NonLocalURLError(
                f"LLM Gateway strictly rejects non-local URL: '{self.base_url}'. "
                "Master Plan policy mandates offline open-weights models only."
            )

    def chat_complete(
        self,
        messages: List[Dict[str, str]],
        vault: Optional[ReversibleVault] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> GatewayResponse:
        """
        Execute chat completion through local Ollama OpenAI-compatible endpoint.
        Automatically masks all messages before transmission.
        """
        if vault is None:
            vault = ReversibleVault()

        # Step 1: Pre-flight PII Masking on all input messages
        masked_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            masked_content, _ = pii_masker.mask(content, vault)
            masked_messages.append({"role": role, "content": masked_content})

        # Step 2: Prepare payload for Ollama OpenAI-compatible /v1/chat/completions endpoint
        endpoint = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": masked_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        # Step 3: Dispatch request
        start_time = time.time()
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                res = client.post(endpoint, json=payload)
                res.raise_for_status()
                data = res.json()
        except httpx.HTTPError as e:
            raise RuntimeError(f"Ollama local inference failed at {endpoint}: {e}")

        latency_ms = (time.time() - start_time) * 1000.0

        # Extract reply & token counts
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", len(str(messages)) // 4)
        completion_tokens = usage.get("completion_tokens", len(content) // 4)

        return GatewayResponse(
            content=content,
            model_version=self.model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            vault=vault,
        )

    def complete_prompt(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        vault: Optional[ReversibleVault] = None,
        temperature: float = 0.1,
    ) -> GatewayResponse:
        """Helper to invoke single turn prompt with optional system message."""
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        return self.chat_complete(messages=messages, vault=vault, temperature=temperature)


llm_gateway = LLMGateway()
