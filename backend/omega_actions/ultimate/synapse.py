"""Deterministic bounded STDP-inspired routing for offline agent scheduling.

A scheduling heuristic, not biological neuromorphic hardware or infinite capacity.
"""
from __future__ import annotations
import math


class NeuromorphicRouter:
    def __init__(self, agents: tuple[str, ...], *, threshold: float = 0.8):
        if not 2 <= len(agents) <= 64 or len(set(agents)) != len(agents):
            raise ValueError('Requires 2..64 distinct agents')
        if any(not isinstance(x, str) or not x.isidentifier() for x in agents):
            raise ValueError('Invalid agent identifier')
        if not 0 < threshold <= 1:
            raise ValueError('Invalid threshold')
        self.agents = tuple(agents)
        self.threshold = threshold
        self._weights = {(a, b): 0.5 for a in agents for b in agents if a != b}
        self._quarantined: set[str] = set()

    def weight(self, source: str, target: str) -> float:
        return self._weights[(source, target)]

    def route(self, source: str) -> str:
        if source not in self.agents:
            raise ValueError('Unknown source agent')
        eligible = [name for name in self.agents if name != source and name not in self._quarantined]
        if not eligible:
            raise RuntimeError('No available downstream agents')
        return max(eligible, key=lambda target: self._weights[(source, target)])

    def feedback(self, source: str, target: str, *, reward: float) -> None:
        if (source, target) not in self._weights or not math.isfinite(reward) or not -1 <= reward <= 1:
            raise ValueError('Invalid synaptic feedback')
        old = self._weights[(source, target)]
        self._weights[(source, target)] = max(0.0, min(1.0, old + 0.05 * reward * (1 - abs(old - 0.5))))

    def quarantine(self, agent: str) -> None:
        if agent not in self.agents:
            raise ValueError('Unknown agent')
        self._quarantined.add(agent)

    def restore(self, agent: str) -> None:
        self._quarantined.discard(agent)
