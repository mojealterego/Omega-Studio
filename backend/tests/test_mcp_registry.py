import json
import tempfile
import unittest
from pathlib import Path
from omega_actions.ultimate.mcp_registry import MCPRegistry, MCPServer, MCPRegistryError

class MCPRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.registry = MCPRegistry(Path(self.tmp.name))

    def test_stdio_roundtrip(self):
        server = MCPServer("local", "stdio", ("python", "-m", "my_mcp"))
        self.registry.put(server)
        self.assertEqual(self.registry.list(), [server])

    def test_http_roundtrip(self):
        server = MCPServer("remote", "streamable-http", url="https://example.org/mcp")
        self.registry.put(server)
        self.assertEqual(self.registry.list(), [server])

    def test_replace_and_delete(self):
        self.registry.put(MCPServer("local", "stdio", ("python", "a.py")))
        self.registry.put(MCPServer("local", "stdio", ("python", "b.py")))
        self.assertEqual(self.registry.list()[0].command[-1], "b.py")
        self.assertTrue(self.registry.delete("local"))
        self.assertFalse(self.registry.delete("local"))
        self.assertEqual(self.registry.list(), [])

    def test_insecure_url_rejected(self):
        for url in ("http://example.org/mcp", "https://user:pass@example.org/mcp", "https://example.org/mcp#fragment"):
            with self.subTest(url=url), self.assertRaises(MCPRegistryError):
                MCPServer("remote", "streamable-http", url=url)

    def test_private_network_endpoints_rejected(self):
        blocked = (
            "https://localhost/mcp",
            "https://127.0.0.1/mcp",
            "https://10.0.0.2/mcp",
            "https://192.168.1.1/mcp",
            "https://169.254.169.254/latest/meta-data/",
            "https://[::1]/mcp",
            "https://example.local/mcp",
            "https://example.com:8443/mcp",
            "https://example.com:bad/mcp",
        )
        for url in blocked:
            with self.subTest(url=url), self.assertRaises(MCPRegistryError):
                MCPServer("remote", "streamable-http", url=url)

    def test_public_https_endpoint_accepted(self):
        server = MCPServer("remote", "streamable-http", url="https://mcp.example.com:443/mcp")
        self.assertEqual(server.transport, "streamable-http")

    def test_invalid_command_rejected(self):
        with self.assertRaises(MCPRegistryError):
            MCPServer("bad", "stdio", ("python", "bad\x00arg"))

    def test_invalid_json_rejected(self):
        self.registry.path.parent.mkdir(parents=True)
        self.registry.path.write_text("{invalid", encoding="utf-8")
        with self.assertRaises(MCPRegistryError):
            self.registry.list()

    def test_symlink_rejected(self):
        self.registry.path.parent.mkdir(parents=True)
        target = Path(self.tmp.name) / "outside"
        target.write_text("[]")
        self.registry.path.symlink_to(target)
        with self.assertRaises(MCPRegistryError):
            self.registry.put(MCPServer("safe", "stdio", ("python",)))
        self.assertEqual(target.read_text(), "[]")
