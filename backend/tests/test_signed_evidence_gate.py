"""Trust-root negative tests. Signing in tests proves format, not a Lean run."""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from omega_actions.ultimate.signed_evidence_gate import (
    EvidenceAttestationError, TrustedVerifierKey, verify_signed_attestation,
)

UTC=timezone.utc
FIXED=datetime(2026,11,15,16,0,0,tzinfo=UTC)
EVIDENCE=b'local test log: mock verification evidence; not Lean'
SUBJECT_HASH='a'*64


def fixture(*,kind='LEAN4_KERNEL', evidence=EVIDENCE):
    private=Ed25519PrivateKey.generate()
    public=private.public_key().public_bytes(encoding=serialization.Encoding.Raw,
                                             format=serialization.PublicFormat.Raw)
    key=TrustedVerifierKey(key_id='verifier-main',public_key_raw=public,
                           allowed_kinds=frozenset({kind}))
    payload={
       'kind':kind,
       'subject_sha256':SUBJECT_HASH,
       'evidence_sha256':hashlib.sha256(evidence).hexdigest(),
       'run_id':'run20261115-001',
       'issued_at_utc':'2026-11-15T15:59:00Z',
       'outcome':'PASS',
       'verifier_identity':'independent-lean-worker-01',
    }
    text=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
    sig=base64.b64encode(private.sign(text)).decode('ascii')
    envelope={'schema':'omega.signed_verifier_attestation.v1','key_id':'verifier-main',
              'payload':payload, 'signature_b64':sig}
    return envelope, {'verifier-main':key}


def check(envelope, keys, *,evidence=EVIDENCE,kind='LEAN4_KERNEL',subject=SUBJECT_HASH,now=FIXED):
    return verify_signed_attestation(envelope, trusted_keys=keys, expected_kind=kind,
                                     expected_subject_sha256=subject, evidence_bytes=evidence, now=now)


def test_valid_signed_claim_still_not_release_or_kernel_proof():
    env, keys=fixture()
    result=check(env,keys)
    assert result.status == 'AUTHENTIC_ATTESTATION_ONLY'
    assert result.release_authorized is False
    assert result.kernel_proof_verified is False
    assert result.key_id == 'verifier-main'


def test_self_asserted_boolean_without_signature_rejected():
    env, keys=fixture()
    env['signature_b64']=''
    env['lean_kernel_checked']=True
    with pytest.raises(EvidenceAttestationError):check(env,keys)


def test_modified_payload_invalidates_signature():
    env, keys=fixture()
    env['payload']['run_id']='modified-run'
    with pytest.raises(EvidenceAttestationError,match='signature'):check(env,keys)


def test_wrong_evidence_bytes_fail():
    env, keys=fixture()
    with pytest.raises(EvidenceAttestationError,match='evidence'):check(env,keys,evidence=b'forged log')


def test_wrong_subject_rejected():
    env, keys=fixture()
    with pytest.raises(EvidenceAttestationError,match='subject'):check(env,keys,subject='b'*64)


def test_trusted_key_scope_is_enforced():
    env, keys=fixture(kind='LEAN4_KERNEL')
    key=keys['verifier-main']
    keys={'verifier-main':TrustedVerifierKey(key_id=key.key_id,public_key_raw=key.public_key_raw,
                                             allowed_kinds=frozenset({'NEURAL_E2E'}))}
    with pytest.raises(EvidenceAttestationError,match='scope'):check(env,keys)


def test_expired_attestation_rejected():
    env, keys=fixture()
    with pytest.raises(EvidenceAttestationError,match='expired'):check(env,keys,now=FIXED+timedelta(days=3))


def test_future_attestation_rejected():
    env, keys=fixture()
    with pytest.raises(EvidenceAttestationError,match='future'):check(env,keys,now=FIXED-timedelta(minutes=5))


def test_unknown_key_rejected():
    env, keys=fixture()
    with pytest.raises(EvidenceAttestationError,match='Untrusted'):check(env,{})


def test_large_evidence_rejected():
    env, keys=fixture()
    with pytest.raises(EvidenceAttestationError,match='size'):check(env,keys,evidence=b'x'*(4*1024*1024+1))


def test_improper_boolean_payload_field_rejected():
    env, keys=fixture()
    env['payload']['outcome']=True
    with pytest.raises(EvidenceAttestationError):check(env,keys)


def test_same_signature_different_key_rejected():
    env, keys=fixture()
    e2, other=fixture()
    with pytest.raises(EvidenceAttestationError,match='signature'):check(env,other)
