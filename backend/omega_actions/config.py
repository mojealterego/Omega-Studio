"""Runtime configuration, directories and trust boundaries."""
from dataclasses import dataclass
from pathlib import Path
import os

@dataclass(frozen=True)
class Settings:
    home: Path
    unsafe_native: bool = False
    max_parallel: int = 2
    max_matrix: int = 256
    docker_image: str = 'python:3.13-slim'
    default_engine: str = 'auto'
    @classmethod
    def from_env(cls) -> 'Settings':
        root = Path(os.getenv('OMEGA_ACTIONS_HOME', str(Path.home()/'.omega-actions'))).expanduser().resolve()
        return cls(home=root, unsafe_native=os.getenv('OMEGA_UNSAFE_NATIVE','0') == '1',
                   max_parallel=max(1,min(32,int(os.getenv('OMEGA_MAX_PARALLEL','2')))),
                   default_engine=os.getenv('OMEGA_EXECUTOR','auto'))
    def prepare(self) -> None:
        for name in ('', 'runs', 'artifacts', 'cas'):
            p = self.home/name
            p.mkdir(parents=True, exist_ok=True)
            if os.name != 'nt': p.chmod(0o700)
