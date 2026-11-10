"""Tamper-evident and concurrency-safe audit log acceptance."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from omega_actions.audit_ledger import IntegrityLedger, LedgerIntegrityError


def test_ledger_verifies_hash_chain_and_detects_tamper(tmp_path):
    db=tmp_path/'audit.db'
    l=IntegrityLedger(db,key=b'a'*32)
    a=l.append('run',{'id':'abc','state':'started'})
    b=l.append('run',{'id':'abc','state':'success'})
    assert a['seq']==1 and b['seq']==2 and l.verify()['records']==2
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE ledger SET payload=? WHERE seq=1",('"tampered"',))
    with pytest.raises(LedgerIntegrityError):l.verify()


def test_ledger_atomic_parallel_append(tmp_path):
    l=IntegrityLedger(tmp_path/'audit.db',key=b'b'*32)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i:l.append('job',{'i':i}),range(80)))
    assert l.verify()['records']==80
    assert len({e['seq'] for e in l.events()})==80


def test_ledger_rejects_invalid_inputs(tmp_path):
    l=IntegrityLedger(tmp_path/'audit.db',key=b'c'*32)
    with pytest.raises(ValueError):l.append('',{})
    with pytest.raises(ValueError):l.append('job',{'secret':object()})
