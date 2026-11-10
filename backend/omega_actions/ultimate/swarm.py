"""Bounded agent coordination with graph diffusion heuristic and explicit verification."""
from __future__ import annotations
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from threading import Lock
from typing import Callable, Iterable, TypeVar

T = TypeVar('T')
R = TypeVar('R')


class SwarmError(RuntimeError):
    pass


class LoadBalancer:
    """Conservative graph diffusion: sum of loads is invariant at each step."""
    def __init__(self, capacities: list[float], links: list[tuple[int, int]]):
        if not capacities or any(c <= 0 for c in capacities):
            raise ValueError('Positive worker capacities required')
        self.capacities = tuple(float(c) for c in capacities)
        self.links = tuple(links)
        for a, b in links:
            if a == b or min(a, b) < 0 or max(a, b) >= len(capacities):
                raise ValueError('Invalid graph edge')

    def diffuse(self, loads: list[float], *, rate: float = 0.1, steps: int = 10) -> list[float]:
        if len(loads) != len(self.capacities) or any(x < 0 for x in loads):
            raise ValueError('Invalid worker loads')
        if not 0 < rate <= 0.5 or not 0 <= steps <= 100_000:
            raise ValueError('Invalid diffusion configuration')
        result = [float(x) for x in loads]
        for _ in range(steps):
            for a, b in self.links:
                pressure = result[a]/self.capacities[a] - result[b]/self.capacities[b]
                transfer = rate * pressure
                if transfer > 0:
                    transfer = min(transfer, result[a])
                else:
                    transfer = -min(-transfer, result[b])
                result[a] -= transfer
                result[b] += transfer
            if min(result) < -1e-9:
                raise AssertionError('Diffusion violated nonnegative load invariant')
        if abs(sum(result) - sum(loads)) > max(1e-7, sum(loads)*1e-10):
            raise AssertionError('Diffusion violated conservation invariant')
        return result


class SwarmCoordinator:
    """Bounded in-flight work; no autonomous network calls or repository mutation."""
    def __init__(self, max_workers: int = 4, max_pending: int = 16):
        if not 1 <= max_workers <= 64 or not max_workers <= max_pending <= 4096:
            raise ValueError('Invalid worker or queue limits')
        self.max_workers = max_workers
        self.max_pending = max_pending
        self._executor: ThreadPoolExecutor | None = None
        self._lock = Lock()
        self._active = 0
        self.peak_active = 0

    def __enter__(self):
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix='omega-swarm')
        return self

    def __exit__(self, *_):
        if self._executor:
            self._executor.shutdown(wait=True, cancel_futures=True)
            self._executor = None

    def _run(self, fn: Callable[[T], R], item: T) -> R:
        with self._lock:
            self._active += 1
            self.peak_active = max(self.peak_active, self._active)
        try:
            return fn(item)
        finally:
            with self._lock:
                self._active -= 1

    def map(self, fn: Callable[[T], R], items: Iterable[T]) -> list[R]:
        if self._executor is None:
            raise SwarmError('Coordinator must be used as a context manager')
        iterator = iter(items)
        pending = {}
        results: dict[int, R] = {}
        next_index = 0
        exhausted = False
        while not exhausted or pending:
            while not exhausted and len(pending) < self.max_pending:
                try:
                    item = next(iterator)
                except StopIteration:
                    exhausted = True
                    break
                future = self._executor.submit(self._run, fn, item)
                pending[future] = next_index
                next_index += 1
            if not pending:
                continue
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                index = pending.pop(future)
                try:
                    results[index] = future.result()
                except Exception:
                    for remaining in pending:
                        remaining.cancel()
                    raise
        return [results[index] for index in range(next_index)]


class DuoCoordinator:
    """Generator/verifier cycle with hard attempt budget and no silent acceptance."""
    def __init__(self, max_rounds: int = 3):
        if not 1 <= max_rounds <= 32:
            raise ValueError('Invalid verification round budget')
        self.max_rounds = max_rounds

    def run(self, generator: Callable[[T, int], R], verifier: Callable[[R], bool], request: T) -> R:
        for attempt in range(1, self.max_rounds + 1):
            candidate = generator(request, attempt)
            if verifier(candidate):
                return candidate
        raise SwarmError('Generator output rejected by verifier within bounded attempts')
