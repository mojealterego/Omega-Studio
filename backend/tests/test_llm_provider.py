"""Contract tests for the Chat Duo model transport."""
import io
import json
import unittest
from unittest.mock import patch
from omega_actions.ultimate.llm_provider import ChatCompletionProvider, ProviderConfig, ProviderError

class FakeResponse:
    status = 200
    def __init__(self, payload):
        self.stream = io.BytesIO(json.dumps(payload).encode())
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, count):
        return self.stream.read(count)

class ProviderTests(unittest.TestCase):
    def test_local_provider_returns_model_text(self):
        provider = ChatCompletionProvider(ProviderConfig(
            "http://127.0.0.1:8081/v1/chat/completions", "local-model"))
        with patch("urllib.request.OpenerDirector.open", return_value=FakeResponse(
                {"choices": [{"message": {"content": "APPROVE: valid"}}]})) as mocked:
            self.assertEqual(provider("Review this patch"), "APPROVE: valid")
        request = mocked.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["model"], "local-model")
        self.assertEqual(payload["messages"][0]["content"], "Review this patch")

    def test_remote_plain_http_rejected(self):
        with self.assertRaises(ProviderError):
            ProviderConfig("http://example.org/v1/chat/completions", "model")

    def test_missing_response_rejected(self):
        provider = ChatCompletionProvider(ProviderConfig(
            "http://localhost:8081/v1/chat/completions", "model"))
        with patch("urllib.request.OpenerDirector.open", return_value=FakeResponse({"choices": []})):
            with self.assertRaises(ProviderError):
                provider("prompt")

    def test_oversized_prompt_rejected(self):
        provider = ChatCompletionProvider(ProviderConfig(
            "http://localhost:8081/v1/chat/completions", "model"))
        with self.assertRaises(ProviderError):
            provider("x" * 262145)

    def test_loopback_provider_disables_environment_proxy(self):
        provider = ChatCompletionProvider(ProviderConfig(
            "http://127.0.0.1:8081/v1/chat/completions", "model"))
        with patch("urllib.request.build_opener", wraps=__import__("urllib.request", fromlist=["build_opener"]).build_opener) as build:
            with patch("urllib.request.OpenerDirector.open", return_value=FakeResponse(
                    {"choices": [{"message": {"content": "ok"}}]})):
                self.assertEqual(provider("prompt"), "ok")
        proxy_handlers = [handler for handler in build.call_args.args
                          if isinstance(handler, __import__("urllib.request", fromlist=["ProxyHandler"]).ProxyHandler)]
        self.assertEqual(len(proxy_handlers), 1)
        self.assertEqual(proxy_handlers[0].proxies, {})

    def test_malformed_response_structure_is_normalized(self):
        provider = ChatCompletionProvider(ProviderConfig(
            "http://127.0.0.1:8081/v1/chat/completions", "model"))
        for payload in ([], {"choices": [None]}, {"choices": [{"message": None}]}):
            with self.subTest(payload=payload):
                with patch("urllib.request.OpenerDirector.open",
                           return_value=FakeResponse(payload)):
                    with self.assertRaises(ProviderError):
                        provider("prompt")

    def test_nonfinite_limits_are_rejected(self):
        for timeout in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ProviderError):
                    ProviderConfig("http://localhost:8081/v1/chat/completions",
                                   "model", timeout_seconds=timeout)

    def test_invalid_endpoint_type_is_normalized(self):
        for endpoint in (None, 42, [], "http://localhost:invalid/v1/chat/completions"):
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(ProviderError):
                    ProviderConfig(endpoint, "model")

    def test_network_failure_is_normalized(self):
        provider = ChatCompletionProvider(ProviderConfig(
            "https://api.example.org/v1/chat/completions", "model"))
        with patch("urllib.request.OpenerDirector.open", side_effect=OSError("offline")):
            with self.assertRaises(ProviderError):
                provider("prompt")
