"""OpenAI-compatible chat completion adapter for a locally hosted model or configured API."""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlsplit

class ProviderError(RuntimeError):
    pass

@dataclass(frozen=True)
class ProviderConfig:
    endpoint: str
    model: str
    api_key: str = ""
    timeout_seconds: float = 60.0
    max_output_tokens: int = 4096

    def __post_init__(self) -> None:
        try:
            parsed = urlsplit(self.endpoint)
            port = parsed.port
        except (ValueError, TypeError) as exc:
            raise ProviderError('Invalid endpoint URL') from exc
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ProviderError("Endpoint must use HTTP or HTTPS")
        if parsed.username or parsed.password or parsed.fragment:
            raise ProviderError("Credentials and fragments are not allowed in endpoint URLs")
        if not self.model or len(self.model) > 256:
            raise ProviderError("Invalid model")
        if not 1 <= self.timeout_seconds <= 300 or not 1 <= self.max_output_tokens <= 32768:
            raise ProviderError("Invalid provider limits")
        if parsed.scheme == "http" and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise ProviderError("Unencrypted HTTP is only permitted for loopback providers")

class ChatCompletionProvider:
    """Calls a configured chat-completions endpoint; never executes model output."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    def __call__(self, prompt: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 262144:
            raise ProviderError("Invalid prompt")
        data = json.dumps({
            "model": self.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.config.max_output_tokens,
            "stream": False,
        }).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = "Bearer " + self.config.api_key
        request = urllib.request.Request(self.config.endpoint, data=data, headers=headers, method="POST")
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        # Loopback model traffic must not inherit HTTP(S)_PROXY from the host.
        # Remote HTTPS providers retain the system's normal proxy configuration.
        host = urlsplit(self.config.endpoint).hostname
        handlers = [NoRedirect]
        if host in ("127.0.0.1", "localhost", "::1"):
            handlers.insert(0, urllib.request.ProxyHandler({}))
        opener = urllib.request.build_opener(*handlers)
        try:
            with opener.open(request, timeout=self.config.timeout_seconds) as response:
                if response.status != 200:
                    raise ProviderError("Provider returned non-200 response")
                raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise ProviderError("Provider response too large")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderError("Model provider unavailable") from exc
        try:
            parsed = json.loads(raw)
            message = parsed["choices"][0]["message"]["content"]
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            raise ProviderError("Invalid provider response") from exc
        if not isinstance(message, str) or not message.strip() or len(message) > 262144:
            raise ProviderError("Empty or oversized model response")
        return message
