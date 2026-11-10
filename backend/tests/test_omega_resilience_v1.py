"""Behavioral acceptance for bounded, deterministic failure control."""
import pytest
from omega_actions.resilience import AdaptiveCircuitBreaker, CircuitOpen, RetryPolicy, LatencyTelemetry


def test_breaker_transitions_and_single_probe():
    t=[0.0]
    b=AdaptiveCircuitBreaker(failure_threshold=2, recovery_seconds=5, clock=lambda:t[0])
    b.allow(); b.record_failure(); assert b.snapshot()['state']=='closed'
    b.allow(); b.record_failure(); assert b.snapshot()['state']=='open'
    with pytest.raises(CircuitOpen): b.allow()
    t[0]=5.0
    b.allow()
    assert b.snapshot()['state']=='half_open'
    with pytest.raises(CircuitOpen): b.allow()
    b.record_failure(); assert b.snapshot()['state']=='open'
    t[0]=10.0
    b.allow(); b.record_success()
    assert b.snapshot()['state']=='closed'
    assert b.snapshot()['consecutive_failures']==0


def test_retry_schedule_is_deterministic_bounded_and_seeded():
    p=RetryPolicy(max_attempts=5,base_seconds=0.2,max_seconds=1.0,jitter_ratio=0.25)
    a=p.delays(seed=42); b=p.delays(seed=42)
    assert a==b and len(a)==4
    assert all(0<=x<=1.25 for x in a)
    assert a!=p.delays(seed=43)
    with pytest.raises(ValueError): RetryPolicy(max_attempts=0)


def test_bounded_telemetry_histogram_and_percentiles():
    t=LatencyTelemetry(capacity=4)
    for ms in (1,2,3,4,100):t.observe('job',ms)
    s=t.snapshot('job')
    assert s['count_total']==5 and s['count_window']==4
    assert s['min_ms']==2 and s['max_ms']==100
    assert s['p50_ms']==3 and s['p99_ms']==100
    assert s['bucket_counts']['<=100ms']>=1
    assert t.snapshot('missing')['count_total']==0


def test_retry_hard_upper_bound_and_telemetry_metric_cardinality():
    policy=RetryPolicy(max_attempts=20,base_seconds=0.5,max_seconds=1.0,jitter_ratio=1.0)
    assert max(policy.delays(seed=123))<=1.0
    t=LatencyTelemetry(capacity=2,max_metrics=2)
    t.observe('one',1);t.observe('two',2)
    with pytest.raises(ValueError,match='cardinality'):
        t.observe('three',3)
