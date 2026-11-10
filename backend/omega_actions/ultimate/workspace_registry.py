"""Isolated named local workspaces; no arbitrary filesystem paths accepted."""
from pathlib import Path
import re

class WorkspaceError(ValueError):
    pass

class WorkspaceRegistry:
    NAME=re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z')
    def __init__(self,home:Path):
        self.root=Path(home).resolve()/'workspaces'
    def _path(self,name:str)->Path:
        if not isinstance(name,str) or not self.NAME.fullmatch(name):
            raise WorkspaceError('Invalid workspace name')
        return self.root/name
    def create(self,name:str)->Path:
        path=self._path(name)
        self.root.mkdir(parents=True,exist_ok=True)
        try:
            path.mkdir(mode=0o700)
        except FileExistsError as exc:
            raise WorkspaceError('Workspace already exists') from exc
        return path
    def open(self,name:str)->Path:
        path=self._path(name)
        if path.is_symlink() or not path.is_dir():
            raise WorkspaceError('Workspace missing or not a real directory')
        return path
    def list(self)->list[str]:
        if not self.root.is_dir():return []
        return sorted(p.name for p in self.root.iterdir() if self.NAME.fullmatch(p.name) and p.is_dir() and not p.is_symlink())
