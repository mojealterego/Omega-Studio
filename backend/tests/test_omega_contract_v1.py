"""Digital-Life-compatible signed envelope, anti-replay and idempotency."""
import pytest
from omega_actions.dl_contract import SignedEnvelope, ReplayGuard, ContractError, negotiate_version


def test_signed_envelope_accepts_once_and_rejects_tamper_and_cross_tenant(tmp_path):
    key=b'k'*32
    env=SignedEnvelope.issue('tenant-alpha','omega.studio.job.v1',{'job':'compile'},key=key,now=1000,nonce='1'*32)
    guard=ReplayGuard(tmp_path/'replay.db')
    assert SignedEnvelope.verify(env,key=key,now=1001,tenant='tenant-alpha',replay_guard=guard)['job']=='compile'
    with pytest.raises(ContractError,match='replay'):
        SignedEnvelope.verify(env,key=key,now=1001,tenant='tenant-alpha',replay_guard=guard)
    with pytest.raises(ContractError,match='tenant'):
        SignedEnvelope.verify(env,key=key,now=1001,tenant='tenant-beta')
    with pytest.raises(ContractError,match='signature'):
        SignedEnvelope.verify({**env,'payload':{'job':'erase'}},key=key,now=1001,tenant='tenant-alpha')
    with pytest.raises(ContractError,match='expired'):
        SignedEnvelope.verify(env,key=key,now=2000,tenant='tenant-alpha')


def test_contract_version_and_payload_bounds():
    assert negotiate_version(['1.0','1.1'],['1.0','2.0'])=='1.0'
    with pytest.raises(ContractError):negotiate_version(['2.0'],['1.0'])
    with pytest.raises(ContractError):SignedEnvelope.issue('a','x',{'data':'x'*1000000},key=b'k'*32,now=1)
