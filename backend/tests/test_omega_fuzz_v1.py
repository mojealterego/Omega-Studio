"""Seeded adversarial/property tests for parsers, auth envelopes and queue fencing."""
from concurrent.futures import ThreadPoolExecutor
import random
from pathlib import Path
import pytest
from omega_actions.model_studio import GGUFInspector, GGUFError, hf_resolve_url
from omega_actions.dl_contract import SignedEnvelope, ContractError
from omega_actions.recovery import DurableLeaseQueue


def test_gguf_parser_fails_closed_for_500_seeded_random_inputs(tmp_path):
    rng=random.Random(20261110)
    for i in range(500):
        p=tmp_path/'random.gguf'
        p.write_bytes(rng.randbytes(rng.randint(0,256)))
        with pytest.raises(GGUFError):
            GGUFInspector.inspect(p)


def test_signed_envelope_rejects_field_mutations():
    key=b'k'*32
    base=SignedEnvelope.issue('tenant-a','ci.result',{'result':'success'},key=key,now=100,nonce='1'*32)
    mutants=[{**base,'version':'9.9'}, {**base,'tenant':'tenant-b'},
             {**base,'nonce':'2'*32}, {**base,'kind':'ci.erase'},
             {**base,'payload':{'result':'failure'}},
             {**base,'issued_at':101}, {**base,'expires_at':102},
             {**base,'signature':'0'*64}]
    for m in mutants:
        with pytest.raises(ContractError):
            SignedEnvelope.verify(m,key=key,now=101,tenant='tenant-a')


def test_hf_resolver_rejects_500_randomized_traversal_attempts():
    rng=random.Random(7)
    for _ in range(500):
        candidate=''.join(rng.choice('../\\%?\x00\n') for _ in range(10))+'.gguf'
        with pytest.raises(ValueError):hf_resolve_url('owner/model','main',candidate)


def test_parallel_lease_claims_have_unique_owners(tmp_path):
    q=DurableLeaseQueue(tmp_path/'work.db')
    for i in range(20):q.submit(f'job-{i}',{'id':i},now=1)
    with ThreadPoolExecutor(max_workers=16) as pool:
        claimed=list(pool.map(lambda i:q.claim(f'worker-{i}',now=2),range(40)))
    ids=[x['id'] for x in claimed if x]
    assert len(ids)==20 and len(set(ids))==20
