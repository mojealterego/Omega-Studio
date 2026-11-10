"""Real local contract adapter and reversible migration state-machine tests."""
import pytest
from omega_actions.dl_adapter import DigitalLifeAdapter, MigrationJournal, MigrationError
from omega_actions.dl_contract import ContractError


def test_adapter_signed_exchange_replay_and_strict_capabilities(tmp_path):
    adapter=DigitalLifeAdapter('tenant-a',key=b'z'*32,replay_path=tmp_path/'replay.db')
    msg=adapter.encode('ci.result',{'run_id':'r1','status':'success'},now=100,nonce='a'*32)
    assert adapter.decode(msg,now=101)=={'capability':'ci.result','data':{'run_id':'r1','status':'success'}}
    with pytest.raises(ContractError):adapter.decode(msg,now=101)
    with pytest.raises(ContractError):adapter.encode('repo.push',{'repo':'private'},now=100)


def test_migration_journal_approval_rollback_and_invalid_transitions(tmp_path):
    j=MigrationJournal(tmp_path/'migration.db',key=b'q'*32)
    p=j.plan('profile-a','1.0','1.1',digest='b'*64)
    assert p['phase']=='planned'
    with pytest.raises(MigrationError):j.activate('profile-a')
    assert j.start_shadow('profile-a')['phase']=='shadow'
    token=j.approval_token('profile-a')
    assert j.approve('profile-a',token)['phase']=='approved'
    assert j.activate('profile-a')['phase']=='active'
    assert j.rollback('profile-a')['phase']=='rolled_back'
    with pytest.raises(MigrationError):j.activate('profile-a')
