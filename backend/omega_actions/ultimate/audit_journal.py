"""Append-only, hash-chained audit journal for OMEGA agent decisions.

The journal records decisions; it never executes arbitrary tool calls.
"""
from __future__ import annotations
import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any

class AuditIntegrityError(ValueError):
    pass

class AuditJournal:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.RLock()

    @staticmethod
    def _canonical(value: dict[str, Any]) -> bytes:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                          allow_nan=False).encode("utf-8")

    def verify(self) -> tuple[int, str]:
        with self._lock:
            prev = "0" * 64
            count = 0
            if not self.path.exists():
                return count, prev
            with self.path.open("rb") as stream:
                for line in stream:
                    if not line.endswith(b"\n"):
                        raise AuditIntegrityError("truncated journal record")
                    try:
                        item = json.loads(line)
                        if not isinstance(item, dict) or set(item) != {"seq", "prev", "event", "digest"}:
                            raise ValueError("invalid schema")
                        if item["seq"] != count + 1 or item["prev"] != prev:
                            raise ValueError("broken chain")
                        payload = {key: item[key] for key in ("seq", "prev", "event")}
                        digest = hashlib.sha256(self._canonical(payload)).hexdigest()
                        if item["digest"] != digest:
                            raise ValueError("digest mismatch")
                    except (ValueError, TypeError, UnicodeError, KeyError) as exc:
                        raise AuditIntegrityError("journal integrity failure") from exc
                    count += 1
                    prev = digest
            return count, prev

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(event, dict):
            raise TypeError("event must be a dictionary")
        # Normalize and validate before touching disk.
        clean = json.loads(self._canonical(event))
        with self._lock:
            count, prev = self.verify()
            payload = {"seq": count + 1, "prev": prev, "event": clean}
            record = {**payload, "digest": hashlib.sha256(self._canonical(payload)).hexdigest()}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
            fd = os.open(self.path, flags, 0o600)
            try:
                with os.fdopen(fd, "ab") as stream:
                    stream.write(self._canonical(record) + b"\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            except BaseException:
                raise
            return record
