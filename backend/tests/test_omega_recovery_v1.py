"""Durable local queue with leases, retry and crash recovery."""
from omega_actions.recovery import DurableLeaseQueue


def test_crash_recovery_reclaims_expired_lease_without_duplicate_effect(tmp_path):
    q=DurableLeaseQueue(tmp_path/'queue.db',max_attempts=3)
    assert q.submit('job-1',{'kind':'compile'},now=10)
    assert not q.submit('job-1',{'kind':'compile'},now=10)
    first=q.claim('worker-a',now=11,lease_seconds=5)
    assert first['id']=='job-1' and first['attempts']==1
    assert q.claim('worker-b',now=12) is None
    assert q.recover(now=17)==1
    second=q.claim('worker-b',now=18,lease_seconds=5)
    assert second['id']=='job-1' and second['attempts']==2
    assert not q.complete('job-1','worker-a',{'ok':True},now=19)
    assert q.complete('job-1','worker-b',{'ok':True},now=19)
    assert q.claim('worker-c',now=20) is None
    assert q.result('job-1')['status']=='succeeded'


def test_exhausted_attempts_terminal_failure(tmp_path):
    q=DurableLeaseQueue(tmp_path/'queue.db',max_attempts=2)
    q.submit('x',{'cmd':'test'},now=0)
    assert q.claim('w',now=0,lease_seconds=1)
    assert q.recover(now=2)==1
    assert q.claim('w2',now=2,lease_seconds=1)
    assert q.recover(now=4)==1
    assert q.result('x')['status']=='failed'
    assert q.claim('w3',now=5) is None
