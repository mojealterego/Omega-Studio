"""Discrete-event simulation of external dependencies, with explicit evidence boundaries."""
from __future__ import annotations
import heapq
import random
from collections import deque
from .resilience import AdaptiveCircuitBreaker, CircuitOpen, RetryPolicy, LatencyTelemetry


def simulate_architecture(*, seed: int = 20261110, jobs: int = 500,
                          worker_count: int = 4, network_failure_rate: float = 0.15) -> dict:
    """Simulate GitHub API/HF transfer/AI calls and Android process restarts.

    Each virtual operation has bounded attempts, deterministic service times and
    crash/retry transitions. No network, Android device or external service is touched.
    """
    if not 1 <= jobs <= 100_000 or not 1 <= worker_count <= 256 or not 0 <= network_failure_rate <= 1:
        raise ValueError('Invalid simulation parameters')
    rng = random.Random(seed)
    policy = RetryPolicy(max_attempts=4, base_seconds=0.005, max_seconds=0.1, jitter_ratio=0.2)
    delays = [policy.delays(seed=seed ^ (j * 7919)) for j in range(jobs)]
    clock = [0.0]
    breaker = AdaptiveCircuitBreaker(failure_threshold=4, recovery_seconds=0.05, clock=lambda: clock[0])
    telemetry = LatencyTelemetry(capacity=min(jobs, 10000))
    event_queue: list[tuple[float, int, str, int]] = []
    serial = 0

    def schedule(when: float, event: str, job_id: int) -> None:
        nonlocal serial
        serial += 1
        heapq.heappush(event_queue, (when, serial, event, job_id))

    for j in range(jobs):
        schedule(0.0, 'start', j)
    active = 0
    waiting = deque()
    max_active = 0
    attempts = [0] * jobs
    completed: dict[int, str] = {}
    effects: set[int] = set()
    first_start = [None] * jobs
    faults = {'network_failures': 0, 'worker_crashes': 0, 'recovered_leases': 0,
              'circuit_rejections': 0, 'retry_events': 0}
    max_events = jobs * 30
    processed = 0
    while event_queue:
        processed += 1
        if processed > max_events:
            raise RuntimeError('Simulation event budget exceeded')
        at, _, event, j = heapq.heappop(event_queue)
        clock[0] = at
        if j in completed:
            raise AssertionError('Terminal job scheduled again')
        if event == 'start':
            if active >= worker_count:
                waiting.append(j)
                continue
            if first_start[j] is None:
                first_start[j] = at
            attempts[j] += 1
            try:
                breaker.allow()
            except CircuitOpen:
                faults['circuit_rejections'] += 1
                if attempts[j] < policy.max_attempts:
                    schedule(at + delays[j][attempts[j] - 1] + 0.05, 'start', j)
                    faults['retry_events'] += 1
                else:
                    completed[j] = 'failure'
                    telemetry.observe('virtual_job', (at - first_start[j]) * 1000)
                if waiting and active < worker_count:
                    schedule(at, 'start', waiting.popleft())
                continue
            active += 1
            max_active = max(max_active, active)
            service_ms = rng.randint(1, 30)
            schedule(at + service_ms / 1000.0, 'finish', j)
        elif event == 'finish':
            active -= 1
            if rng.random() < 0.03:
                faults['worker_crashes'] += 1
                breaker.record_failure()
                if attempts[j] < policy.max_attempts:
                    schedule(at + delays[j][attempts[j] - 1] + 0.02, 'start', j)
                    faults['recovered_leases'] += 1
                    faults['retry_events'] += 1
                else:
                    completed[j] = 'failure'
            elif rng.random() < network_failure_rate:
                faults['network_failures'] += 1
                breaker.record_failure()
                if attempts[j] < policy.max_attempts:
                    schedule(at + delays[j][attempts[j] - 1], 'start', j)
                    faults['retry_events'] += 1
                else:
                    completed[j] = 'failure'
            else:
                breaker.record_success()
                if j in effects:
                    raise AssertionError('Duplicate simulated external effect')
                effects.add(j)
                completed[j] = 'success'
            if j in completed:
                telemetry.observe('virtual_job', (at - first_start[j]) * 1000)
            if waiting and active < worker_count:
                schedule(at, 'start', waiting.popleft())
        else:
            raise AssertionError('Unknown event')
    success = sum(v == 'success' for v in completed.values())
    failure = sum(v == 'failure' for v in completed.values())
    stats = telemetry.snapshot('virtual_job')
    return {
        'scope': 'DETERMINISTIC_SIMULATION_ONLY', 'seed': seed, 'jobs': jobs,
        'workers': worker_count, 'network_failure_rate': network_failure_rate,
        'outcomes': {'success': success, 'failure': failure}, 'faults': faults,
        'metrics': {'virtual_elapsed_ms': round(clock[0] * 1000, 3),
                    'throughput_virtual_jobs_s': round(jobs / max(clock[0], 1e-9), 3),
                    'p50_ms': stats['p50_ms'], 'p95_ms': stats['p95_ms'],
                    'p99_ms': stats['p99_ms'], 'max_active': max_active,
                    'max_attempts_observed': max(attempts)},
        'invariants': {
            'unique_effects': len(effects) == success,
            'no_unbounded_retries': max(attempts) <= policy.max_attempts,
            'queue_drained': len(completed) == jobs and not event_queue and not waiting and active == 0,
            'bounded_parallelism': max_active <= worker_count,
            'durable_recovery': faults['recovered_leases'] <= faults['worker_crashes']
        },
        'simulated_components': ['Android process lifecycle', 'GitHub REST',
                                 'Hugging Face transfer', 'OpenAI responses API',
                                 'Digital-Life protocol v1'],
    }
