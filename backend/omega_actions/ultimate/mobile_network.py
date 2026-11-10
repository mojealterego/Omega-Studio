"""Seeded network handoff/loss/jitter model; never claims physical radio testing."""
from __future__ import annotations
from dataclasses import dataclass
import random


@dataclass(frozen=True)
class NetworkScenario:
    seed: int
    packets: int
    loss_rate: float = 0.0
    jitter_ms: int = 0
    handoff_every: int = 0
    max_retries: int = 4

    def __post_init__(self):
        if not 0 <= self.seed < 2**32 or not 1 <= self.packets <= 1_000_000:
            raise ValueError('Invalid seed or packet count')
        if not 0 <= self.loss_rate <= 1 or not 0 <= self.jitter_ms <= 60_000:
            raise ValueError('Invalid network loss or jitter')
        if not 0 <= self.handoff_every <= 1_000_000 or not 0 <= self.max_retries <= 8:
            raise ValueError('Invalid handoff or retry configuration')


def simulate_mobile_link(scenario: NetworkScenario) -> dict:
    rng = random.Random(scenario.seed)
    delivered = 0
    lost = 0
    retries = 0
    max_backoff = 0
    latency_total = 0
    handoffs = 0
    for i in range(1, scenario.packets + 1):
        if scenario.handoff_every and i % scenario.handoff_every == 0:
            handoffs += 1
        ok = False
        for attempt in range(scenario.max_retries + 1):
            latency_total += rng.randrange(scenario.jitter_ms + 1)
            if rng.random() >= scenario.loss_rate:
                ok = True
                break
            if attempt < scenario.max_retries:
                retries += 1
                max_backoff = max(max_backoff, min(8000, 250 * 2**attempt))
        if ok: delivered += 1
        else: lost += 1
    return {'scope':'DETERMINISTIC_NETWORK_MODEL', 'packets_sent':scenario.packets,
            'packets_delivered':delivered, 'packets_lost':lost, 'retries':retries,
            'handoffs':handoffs, 'max_backoff_ms':max_backoff,
            'simulated_jitter_ms_total':latency_total}
