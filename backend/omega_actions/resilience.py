"""Bounded adaptive fault control with injectable monotonic time and deterministic jitter."""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
import math
import random
import threading
import time
from typing import Callable


class CircuitOpen(RuntimeError):
    """The target has exceeded its failure budget or half-open probe limit."""


class AdaptiveCircuitBreaker:
    """Thread-safe CLOSED/OPEN/HALF_OPEN breaker; a single half-open probe at a time."""
    def __init__(self, failure_threshold: int = 3, recovery_seconds: float = 5.0,
                 clock: Callable[[], float] = time.monotonic):
        if failure_threshold < 1 or not math.isfinite(recovery_seconds) or recovery_seconds <= 0:
            raise ValueError('Invalid circuit breaker configuration')
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self.clock = clock
        self._lock = threading.Lock()
        self._state = 'closed'
        self._failures = 0
        self._opened_at = float('-inf')
        self._probe_inflight = False

    def allow(self) -> None:
        with self._lock:
            if self._state == 'open':
                if self.clock() - self._opened_at < self.recovery_seconds:
                    raise CircuitOpen('Circuit recovery interval not elapsed')
                self._state = 'half_open'
            if self._state == 'half_open':
                if self._probe_inflight:
                    raise CircuitOpen('Half-open probe already in flight')
                self._probe_inflight = True

    def record_success(self) -> None:
        with self._lock:
            self._state = 'closed'
            self._failures = 0
            self._probe_inflight = False

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._state == 'half_open' or self._failures >= self.failure_threshold:
                self._state = 'open'
                self._opened_at = self.clock()
            self._probe_inflight = False

    def snapshot(self) -> dict:
        with self._lock:
            return {'state': self._state, 'consecutive_failures': self._failures,
                    'half_open_probe_inflight': self._probe_inflight,
                    'recovery_seconds': self.recovery_seconds}


@dataclass(frozen=True)
class RetryPolicy:
    """At most max_attempts total attempts, with deterministic seedable full-ish jitter."""
    max_attempts: int = 4
    base_seconds: float = 0.2
    max_seconds: float = 5.0
    jitter_ratio: float = 0.2

    def __post_init__(self):
        if not 1 <= self.max_attempts <= 100:
            raise ValueError('max_attempts must be between 1 and 100')
        if (not math.isfinite(self.base_seconds) or self.base_seconds <= 0 or
                not math.isfinite(self.max_seconds) or self.max_seconds < self.base_seconds or
                not math.isfinite(self.jitter_ratio) or not 0 <= self.jitter_ratio <= 1):
            raise ValueError('Invalid retry backoff parameters')

    def delays(self, *, seed: int) -> list[float]:
        rng = random.Random(seed)
        return [min(self.max_seconds,
                    min(self.max_seconds, self.base_seconds * (2.0 ** min(i, 40))) *
                    (1.0 - self.jitter_ratio / 2.0 + self.jitter_ratio * rng.random()))
                for i in range(self.max_attempts - 1)]


class LatencyTelemetry:
    """Bounded sliding window; percentiles describe observed samples, not hard RT guarantees."""
    BUCKETS = (1, 5, 10, 25, 50, 100, 250, 500, 1000, 5000)

    def __init__(self, capacity: int = 4096, max_metrics: int = 128):
        if not 1 <= capacity <= 1_000_000 or not 1 <= max_metrics <= 100_000:
            raise ValueError('Invalid telemetry capacity or cardinality')
        self._capacity = capacity
        self._max_metrics = max_metrics
        self._lock = threading.Lock()
        self._windows: dict[str, deque[float]] = {}
        self._totals: dict[str, int] = {}

    def observe(self, metric: str, elapsed_ms: float) -> None:
        if not metric or len(metric) > 128 or not math.isfinite(elapsed_ms) or elapsed_ms < 0:
            raise ValueError('Invalid latency sample')
        with self._lock:
            if metric not in self._windows and len(self._windows) >= self._max_metrics:
                raise ValueError('Telemetry metric cardinality limit exceeded')
            window = self._windows.setdefault(metric, deque(maxlen=self._capacity))
            window.append(float(elapsed_ms))
            self._totals[metric] = self._totals.get(metric, 0) + 1

    def snapshot(self, metric: str) -> dict:
        with self._lock:
            samples = sorted(self._windows.get(metric, ()))
            total = self._totals.get(metric, 0)
        result = {'metric': metric, 'count_total': total, 'count_window': len(samples),
                  'min_ms': None, 'max_ms': None, 'p50_ms': None, 'p95_ms': None,
                  'p99_ms': None, 'bucket_counts': {f'<={b}ms': 0 for b in self.BUCKETS}}
        if samples:
            result.update(min_ms=samples[0], max_ms=samples[-1])
            for p in (50, 95, 99):
                result[f'p{p}_ms'] = samples[math.ceil(len(samples) * p / 100) - 1]
            for bucket in self.BUCKETS:
                result['bucket_counts'][f'<={bucket}ms'] = sum(x <= bucket for x in samples)
        return result
