"""MCP registry HTTP integration contract tests."""
import tempfile
import unittest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from omega_actions.ultimate.router import create_ultimate_router

class MCPAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        app = FastAPI()
        app.include_router(create_ultimate_router(Path(self.temp.name)))
        self.client = TestClient(app)

    def test_put_list_delete(self):
        body = {"name": "test", "transport": "stdio", "command": ["python", "-m", "server"]}
        response = self.client.put("/api/ultimate/mcp/servers/test", json=body)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["executed"])
        listed = self.client.get("/api/ultimate/mcp/servers")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["items"][0]["name"], "test")
        self.assertEqual(self.client.delete("/api/ultimate/mcp/servers/test").status_code, 200)
        self.assertEqual(self.client.get("/api/ultimate/mcp/servers").json()["items"], [])

    def test_identity_mismatch(self):
        response = self.client.put("/api/ultimate/mcp/servers/a", json={
            "name": "b", "transport": "stdio", "command": ["python"]})
        self.assertEqual(response.status_code, 422)

    def test_http_without_tls_denied(self):
        response = self.client.put("/api/ultimate/mcp/servers/a", json={
            "name": "a", "transport": "streamable-http", "url": "http://example.com/mcp"})
        self.assertEqual(response.status_code, 422)

    def test_unknown_server(self):
        self.assertEqual(self.client.delete("/api/ultimate/mcp/servers/missing").status_code, 404)
