"""Chat Duo HTTP integration tests with two independent simulated model responses."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from omega_actions.ultimate.router import create_ultimate_router

class FakeResponse:
    status = 200
    def __init__(self, text):
        self.text = text
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, limit):
        return json.dumps({"choices": [{"message": {"content": self.text}}]}).encode()

class DuoAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        app = FastAPI()
        app.include_router(create_ultimate_router(Path(self.tmp.name)))
        self.client = TestClient(app)
        self.endpoint = "/api/ultimate/chat/duo"

    def test_unconfigured_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            response = self.client.post(self.endpoint, json={"instruction": "Write a function"})
        self.assertEqual(response.status_code, 503)

    def test_two_model_calls_and_independent_review(self):
        env = {
            "OMEGA_DUO_AUTHOR_ENDPOINT": "http://localhost:8081/v1/chat/completions",
            "OMEGA_DUO_REVIEWER_ENDPOINT": "http://localhost:8082/v1/chat/completions",
            "OMEGA_DUO_AUTHOR_MODEL": "author",
            "OMEGA_DUO_REVIEWER_MODEL": "reviewer",
        }
        seen = []
        def answer(request, timeout):
            data = json.loads(request.data)
            seen.append(data)
            if len(seen) == 1:
                return FakeResponse("def add(a, b): return a + b")
            return FakeResponse("APPROVE: tests recommended")
        with patch.dict(os.environ, env, clear=True), patch(
                "urllib.request.OpenerDirector.open", side_effect=answer):
            response = self.client.post(self.endpoint, json={"instruction": "Implement addition"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["approved"])
        self.assertFalse(response.json()["executed"])
        self.assertEqual([x["model"] for x in seen], ["author", "reviewer"])
        self.assertIn("def add", seen[1]["messages"][0]["content"])

    def test_review_rejection(self):
        env = {
            "OMEGA_DUO_AUTHOR_ENDPOINT": "http://localhost:8081/v1/chat/completions",
            "OMEGA_DUO_REVIEWER_ENDPOINT": "http://localhost:8082/v1/chat/completions",
            "OMEGA_DUO_AUTHOR_MODEL": "author",
            "OMEGA_DUO_REVIEWER_MODEL": "reviewer",
        }
        with patch.dict(os.environ, env, clear=True), patch(
                "urllib.request.OpenerDirector.open", side_effect=[
                    FakeResponse("unsafe code"), FakeResponse("REJECT: unsafe")]):
            response = self.client.post(self.endpoint, json={"instruction": "Review code"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["approved"])
