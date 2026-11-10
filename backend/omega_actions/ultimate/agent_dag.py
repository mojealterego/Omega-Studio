"""Fail-closed DAG planning and capability authorization for agent workflows.

No tools are executed by this module. Plans are untrusted data.
"""
from dataclasses import dataclass
from collections import deque
from typing import Mapping, Sequence

class PlanError(ValueError):
    """Invalid or unauthorized execution plan."""

@dataclass(frozen=True)
class Task:
    task_id: str
    capability: str
    dependencies: tuple[str, ...] = ()
    estimated_cost: int = 1

@dataclass(frozen=True)
class Plan:
    levels: tuple[tuple[str, ...], ...]
    total_cost: int

def validate_plan(
    tasks: Sequence[Task],
    allowed_capabilities: frozenset[str],
    *,
    max_tasks: int = 128,
    max_cost: int = 1000,
    max_parallel: int = 8,
) -> Plan:
    """Validate graph, authority and resource budgets; return stable execution waves."""
    if not isinstance(max_tasks, int) or isinstance(max_tasks, bool) or max_tasks < 1:
        raise PlanError("invalid max_tasks")
    if not isinstance(max_cost, int) or isinstance(max_cost, bool) or max_cost < 0:
        raise PlanError("invalid max_cost")
    if not isinstance(max_parallel, int) or isinstance(max_parallel, bool) or max_parallel < 1:
        raise PlanError("invalid max_parallel")
    if not tasks or len(tasks) > max_tasks:
        raise PlanError("task count outside limits")
    by_id: dict[str, Task] = {}
    cost = 0
    for task in tasks:
        if not isinstance(task, Task):
            raise PlanError("task must be Task")
        if not isinstance(task.task_id, str) or not task.task_id or len(task.task_id) > 128:
            raise PlanError("invalid task ID")
        if task.task_id in by_id:
            raise PlanError("duplicate task ID")
        if not isinstance(task.capability, str) or task.capability not in allowed_capabilities:
            raise PlanError("capability denied")
        if (not isinstance(task.estimated_cost, int)
            or isinstance(task.estimated_cost, bool) or task.estimated_cost < 0):
            raise PlanError("invalid task cost")
        if not isinstance(task.dependencies, tuple) or any(
            not isinstance(d, str) for d in task.dependencies
        ):
            raise PlanError("invalid dependencies")
        if len(set(task.dependencies)) != len(task.dependencies):
            raise PlanError("duplicate dependency")
        cost += task.estimated_cost
        if cost > max_cost:
            raise PlanError("cost budget exceeded")
        by_id[task.task_id] = task
    outgoing: dict[str, list[str]] = {k: [] for k in by_id}
    indegree = {k: 0 for k in by_id}
    for task in tasks:
        for dep in task.dependencies:
            if dep not in by_id or dep == task.task_id:
                raise PlanError("missing or self dependency")
            outgoing[dep].append(task.task_id)
            indegree[task.task_id] += 1
    ready = deque(sorted(k for k, n in indegree.items() if n == 0))
    levels: list[tuple[str, ...]] = []
    visited = 0
    while ready:
        wave = tuple(ready.popleft() for _ in range(min(len(ready), max_parallel)))
        levels.append(wave)
        visited += len(wave)
        for task_id in wave:
            for child in outgoing[task_id]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
        ready = deque(sorted(ready))
    if visited != len(tasks):
        raise PlanError("cycle detected")
    return Plan(tuple(levels), cost)
