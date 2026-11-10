"""Deterministic external dependency simulation, not a real-device certification."""
from omega_actions.digital_twin import simulate_architecture


def test_simulation_deterministic_and_invariants():
    a=simulate_architecture(seed=20261110,jobs=250,worker_count=4,network_failure_rate=0.12)
    b=simulate_architecture(seed=20261110,jobs=250,worker_count=4,network_failure_rate=0.12)
    assert a==b
    assert a['seed']==20261110 and a['jobs']==250
    assert a['invariants']['unique_effects']
    assert a['invariants']['no_unbounded_retries']
    assert a['invariants']['queue_drained']
    assert a['invariants']['bounded_parallelism']
    assert a['invariants']['durable_recovery']
    assert a['outcomes']['success']+a['outcomes']['failure']==250
    assert a['faults']['network_failures']>0 and a['faults']['worker_crashes']>0


def test_simulation_extreme_outage_remains_bounded():
    a=simulate_architecture(seed=7,jobs=32,worker_count=2,network_failure_rate=1.0)
    assert a['outcomes']['failure']==32
    assert a['invariants']['no_unbounded_retries']
    assert a['invariants']['queue_drained']
