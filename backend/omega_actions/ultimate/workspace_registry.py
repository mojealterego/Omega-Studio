"""POSIX workspace registry with no-follow directory-descriptor isolation.

The legacy create/open API returns Paths for compatibility. Callers performing
security-sensitive file I/O should instead hold ``open_fd`` throughout the I/O
operation and use ``dir_fd``-relative operations with ``O_NOFOLLOW``.
"""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import re
import stat
from typing import Iterator


class WorkspaceError(ValueError):
    """Invalid name or unsafe/missing workspace."""


class WorkspaceRegistry:
    NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
    _FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)

    def __init__(self, home: Path):
        if os.name != "posix":
            raise WorkspaceError("Workspace isolation requires POSIX dir_fd semantics")
        self.root = Path(home).resolve() / "workspaces"

    def _path(self, name: str) -> Path:
        if not isinstance(name, str) or not self.NAME.fullmatch(name):
            raise WorkspaceError("Invalid workspace name")
        return self.root / name

    @contextmanager
    def _root_fd(self, *, create: bool) -> Iterator[int]:
        """Pin trusted root inode; never follow a workspaces symlink."""
        if create:
            self.root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        parent_fd: int | None = None
        root_fd: int | None = None
        try:
            try:
                parent_fd = os.open(self.root.parent, self._FLAGS)
                if create:
                    try:
                        os.mkdir("workspaces", mode=0o700, dir_fd=parent_fd)
                    except FileExistsError:
                        pass
                root_fd = os.open("workspaces", self._FLAGS, dir_fd=parent_fd)
                info = os.fstat(root_fd)
                if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
                    raise WorkspaceError("Workspace root ownership or type invalid")
                if stat.S_IMODE(info.st_mode) != 0o700:
                    os.fchmod(root_fd, 0o700)
            except FileNotFoundError:
                raise
            except OSError as exc:
                raise WorkspaceError("Workspace root is missing or unsafe") from exc
            yield root_fd
        finally:
            if root_fd is not None:
                os.close(root_fd)
            if parent_fd is not None:
                os.close(parent_fd)

    @contextmanager
    def open_fd(self, name: str) -> Iterator[int]:
        """Provide a stable, securely opened workspace directory descriptor."""
        self._path(name)
        with self._root_fd(create=False) as root_fd:
            try:
                fd = os.open(name, self._FLAGS, dir_fd=root_fd)
            except OSError as exc:
                raise WorkspaceError("Workspace missing or not a real directory") from exc
            try:
                info = os.fstat(fd)
                if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
                    raise WorkspaceError("Workspace ownership or type invalid")
                yield fd
            finally:
                os.close(fd)

    def create(self, name: str) -> Path:
        path = self._path(name)
        with self._root_fd(create=True) as root_fd:
            try:
                os.mkdir(name, mode=0o700, dir_fd=root_fd)
            except FileExistsError as exc:
                raise WorkspaceError("Workspace already exists") from exc
            except OSError as exc:
                raise WorkspaceError("Cannot create workspace") from exc
            # Check the exact inode under the pinned root (no path re-resolution).
            try:
                fd = os.open(name, self._FLAGS, dir_fd=root_fd)
                try:
                    info = os.fstat(fd)
                    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
                        raise WorkspaceError("New workspace has invalid ownership or type")
                finally:
                    os.close(fd)
            except OSError as exc:
                raise WorkspaceError("New workspace could not be verified") from exc
        return path

    def open(self, name: str) -> Path:
        path = self._path(name)
        with self.open_fd(name):
            pass
        return path

    def list(self) -> list[str]:
        try:
            with self._root_fd(create=False) as root_fd:
                names = []
                for name in os.listdir(root_fd):
                    if not self.NAME.fullmatch(name):
                        continue
                    try:
                        info = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
                    except FileNotFoundError:
                        continue
                    if stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid():
                        names.append(name)
                return sorted(names)
        except FileNotFoundError:
            return []
