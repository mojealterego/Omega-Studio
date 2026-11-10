"""Deterministic mobile network state-machine simulation, not physical RF testing."""
from __future__ import annotations
import random


def simulate_mobile_network(*, seed: int, steps: int = 1000, loss: float = 0.1, jitter_ms: int = 50) -> dict:
    if not isinstance(seed, int) or not 1 <= steps <= 1_000_000 or not 0 <= loss <= 1 or not 0 <= jitter_ms <= 5000:
        raise ValueError('Invalid simulation parameters')
    rng = random.Random(seed)
    lost = delivered = reconnects = total_jitter = 0
    state = 'wifi'
    for step in range(steps):
        # Scheduled handover is independent of packet loss, to cover each path.
        if step in (steps // 3, 2 * steps // 3) and step != 0:
            state = 'lte' if state == 'wifi' else '5g'
            reconnects += 1
        if rng.random() < loss:
            lost += 1
        else:
            delivered += 1
            total_jitter += rng.randint(0, jitter_ms)
    return {'model': 'deterministic-state-machine', 'seed': seed, 'sent': steps,
            'lost': lost, 'delivered': delivered, 'reconnects': reconnects,
            'final_network': state, 'mean_jitter_ms': total_jitter / delivered if delivered else 0}
