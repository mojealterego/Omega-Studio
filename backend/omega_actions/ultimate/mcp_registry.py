"""Per-installation MCP server configuration registry. Configuration only; no subprocess execution."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
import os
import re
import tempfile

_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_ALLOWED_TRANSPORTS = frozenset({"stdio", "streamable-http"})

class MCPRegistryError(ValueError):
    pass

@dataclass(frozen=True)
class MCPServer:
    name: str
    transport: str
    command: tuple[str, ...] = ()
    url: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not _NAME.fullmatch(self.name):
            raise MCPRegistryError("Invalid server name")
        if self.transport not in _ALLOWED_TRANSPORTS:
            raise MCPRegistryError("Unsupported MCP transport")
        if self.transport == "stdio":
            if not isinstance(self.command, tuple) or not self.command or len(self.command) > 32:
                raise MCPRegistryError("stdio requires bounded command arguments")
            if any(not isinstance(arg, str) or not arg or len(arg) > 4096 or "\x00" in arg for arg in self.command):
                raise MCPRegistryError("Invalid command arguments")
            if self.url:
                raise MCPRegistryError("stdio cannot define URL")
        else:
            from urllib.parse import urlsplit
            parsed = urlsplit(self.url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
                raise MCPRegistryError("HTTP MCP requires HTTPS URL without credentials or fragment")
            if self.command:
                raise MCPRegistryError("HTTP MCP cannot define command")

class MCPRegistry:
    def __init__(self, home: Path) -> None:
        self.path = Path(home).resolve() / "ultimate" / "mcp-servers.json"

    def list(self) -> list[MCPServer]:
        if not self.path.exists():
            return []
        if self.path.is_symlink():
            raise MCPRegistryError("Registry symlink denied")
        try:
            raw = self.path.read_bytes()
            if len(raw) > 1024 * 1024:
                raise MCPRegistryError("Registry exceeds size limit")
            data = json.loads(raw)
            if not isinstance(data, list) or len(data) > 128:
                raise MCPRegistryError("Invalid registry format")
            servers = [MCPServer(
                name=item["name"], transport=item["transport"],
                command=tuple(item.get("command", [])), url=item.get("url", "")
            ) for item in data]
            if len({server.name for server in servers}) != len(servers):
                raise MCPRegistryError("Duplicate server name")
            return sorted(servers, key=lambda server: server.name)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise MCPRegistryError("Cannot read MCP registry") from exc

    def put(self, server: MCPServer) -> None:
        servers = {entry.name: entry for entry in self.list()}
        if server.name not in servers and len(servers) >= 128:
            raise MCPRegistryError("MCP registry capacity exceeded")
        servers[server.name] = server
        self._save(sorted(servers.values(), key=lambda entry: entry.name))

    def delete(self, name: str) -> bool:
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise MCPRegistryError("Invalid server name")
        servers = self.list()
        remaining = [server for server in servers if server.name != name]
        if len(remaining) == len(servers):
            return False
        self._save(remaining)
        return True

    def _save(self, servers: list[MCPServer]) -> None:
        from dataclasses import asdict
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise MCPRegistryError("Registry symlink denied")
        payload = json.dumps([asdict(server) for server in servers], sort_keys=True, ensure_ascii=False).encode()
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix=".mcp-", delete=False) as stream:
                temporary = Path(stream.name)
                os.chmod(temporary, 0o600)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
