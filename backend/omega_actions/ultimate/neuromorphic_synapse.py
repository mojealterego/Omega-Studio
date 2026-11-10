"""Bounded STDP-inspired routing for local agents (classical software model)."""
from __future__ import annotations
import math


class NeuromorphicSynapse:
    def __init__(self, agents: list[str], *, max_weight: float = 2.0, learning_rate: float = 0.2):
        if not 1 <= len(agents) <= 64 or len(set(agents)) != len(agents) or any(not x for x in agents):
            raise ValueError('Agent IDs must be unique and bounded')
        if not 1 <= max_weight <= 100 or not 0 < learning_rate <= 1:
            raise ValueError('Invalid synapse parameters')
        self.agents = tuple(agents)
        self.max_weight = max_weight
        self.learning_rate = learning_rate
        self._weights = {(a, b): 1.0 for a in agents for b in agents if a != b}
        self._last_spike: dict[str, int] = {}
        self._clock = -1

    def weight(self, source: str, destination: str) -> float:
        return self._weights[(source, destination)]

    def spike(self, agent: str, *, tick: int) -> None:
        if agent not in self.agents or not isinstance(tick, int) or tick < self._clock:
            raise ValueError('Invalid agent or nonmonotonic tick')
        for other, previous in self._last_spike.items():
            if other == agent:
                continue
            dt = tick - previous
            delta = self.learning_rate * math.exp(-dt / 20)
            # Pre before post potentiates pre->post, depresses post->pre.
            self._weights[(other, agent)] = min(self.max_weight, self._weights[(other, agent)] + delta)
            self._weights[(agent, other)] = max(0.0, self._weights[(agent, other)] - delta)
        self._last_spike[agent] = tick
        self._clock = tick

    def route(self, source: str, pending: dict[str, int], *, tick: int) -> str:
        if source not in self.agents or not isinstance(tick, int) or tick < self._clock:
            raise ValueError('Invalid routing request')
        if any(a not in self.agents or not isinstance(v, int) or v < 0 or v > 4096 for a, v in pending.items()):
            raise ValueError('Invalid queue loads')
        candidates = [a for a in self.agents if a != source and a in pending]
        if not candidates:
            raise ValueError('No eligible destination')
        return max(candidates, key=lambda a: (self._weights[(source, a)] / (1 + pending[a]), -self.agents.index(a)))
