"""Ed25519 trust-root gate for independent, tamper-evident verifier receipts.

An authenticated verifier assertion is not, by itself, proof that Lean executed,
that an E2E benchmark ran correctly, or that any model may be released. The
verifier's public key must be provisioned by the host outside model/manifest data.
No private keys, candidate model weights or tool permissions are handled here.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_HASH=re.compile(r'[0-9a-f]{64}\Z')
_ID=re.compile(r'[A-Za-z0-9._-]{3,128}\Z')
_KINDS=frozenset({'LEAN4_KERNEL','NEURAL_E2E','MOBILE_E2E','MODEL_REGRESSION'})
_PAYLOAD_FIELDS=frozenset({'kind','subject_sha256','evidence_sha256','run_id',
                           'issued_at_utc','outcome','verifier_identity'})
_ENVELOPE_FIELDS=frozenset({'schema','key_id','payload','signature_b64'})
_MAX_EVIDENCE_BYTES=4 * 1024 * 1024


class EvidenceAttestationError(ValueError):
    """An attestation violates authentication, temporal or provenance contracts."""


@dataclass(frozen=True, slots=True)
class TrustedVerifierKey:
    """Host-configured trust root, NEVER generated from untrusted model output."""
    key_id: str
    public_key_raw: bytes
    allowed_kinds: frozenset[str]

    def __post_init__(self) -> None:
        if not isinstance(self.key_id,str) or not _ID.fullmatch(self.key_id):
            raise EvidenceAttestationError('Invalid verifier key identifier')
        if not isinstance(self.public_key_raw,bytes) or len(self.public_key_raw)!=32:
            raise EvidenceAttestationError('Expected 32-byte Ed25519 public key')
        if not isinstance(self.allowed_kinds, frozenset) or not self.allowed_kinds or not self.allowed_kinds <= _KINDS:
            raise EvidenceAttestationError('Invalid verifier key scope')
        Ed25519PublicKey.from_public_bytes(self.public_key_raw)


@dataclass(frozen=True, slots=True)
class AttestationCheck:
    status: str
    key_id: str
    kind: str
    run_id: str
    evidence_sha256: str
    subject_sha256: str
    release_authorized: bool = False
    kernel_proof_verified: bool = False


def _str_field(obj: Mapping[str, Any], field: str) -> str:
    v=obj.get(field)
    if type(v) is not str or not v:
        raise EvidenceAttestationError(f'Missing or invalid {field}')
    return v


def verify_signed_attestation(
    envelope: Mapping[str, Any], *, trusted_keys: Mapping[str, TrustedVerifierKey],
    expected_kind: str, expected_subject_sha256: str, evidence_bytes: bytes,
    now: datetime | None = None, max_age: timedelta = timedelta(hours=24),
    future_skew: timedelta = timedelta(seconds=60),
) -> AttestationCheck:
    """Verify signature, evidence-byte hash, identity, role and freshness.

    This does NOT parse kernel transcripts or prove benchmark validity; separate
    worker attestation and independent review are mandatory for promotion.
    """
    if not isinstance(envelope, Mapping) or set(envelope) != _ENVELOPE_FIELDS:
        raise EvidenceAttestationError('Malformed signed evidence envelope')
    if envelope.get('schema') != 'omega.signed_verifier_attestation.v1':
        raise EvidenceAttestationError('Unknown signed evidence schema')
    if not isinstance(trusted_keys,Mapping):
        raise EvidenceAttestationError('Invalid trust root configuration')
    key_id=_str_field(envelope,'key_id')
    key=trusted_keys.get(key_id)
    if not isinstance(key,TrustedVerifierKey) or key.key_id!=key_id:
        raise EvidenceAttestationError(f'Untrusted verifier key: {key_id}')
    if expected_kind not in _KINDS or expected_kind not in key.allowed_kinds:
        raise EvidenceAttestationError('Verifier key scope does not authorize this attestation kind')
    payload=envelope.get('payload')
    if not isinstance(payload,Mapping) or set(payload)!=_PAYLOAD_FIELDS:
        raise EvidenceAttestationError('Malformed attestation payload')
    fields={k:_str_field(payload,k) for k in _PAYLOAD_FIELDS}
    if fields['kind'] != expected_kind:
        raise EvidenceAttestationError('Attestation kind differs from expected kind')
    if not _HASH.fullmatch(fields['subject_sha256']) or fields['subject_sha256']!=expected_subject_sha256:
        raise EvidenceAttestationError('Wrong or invalid subject SHA-256')
    if not _HASH.fullmatch(fields['evidence_sha256']):
        raise EvidenceAttestationError('Invalid evidence SHA-256')
    if not _ID.fullmatch(fields['run_id']) or not _ID.fullmatch(fields['verifier_identity']):
        raise EvidenceAttestationError('Invalid run id or verifier identity')
    if fields['outcome'] != 'PASS':
        raise EvidenceAttestationError('Only PASS outcome can satisfy this positive gate')
    if not isinstance(evidence_bytes,bytes) or not 0<len(evidence_bytes)<=_MAX_EVIDENCE_BYTES:
        raise EvidenceAttestationError('Invalid evidence byte size')
    observed_hash=hashlib.sha256(evidence_bytes).hexdigest()
    if observed_hash!=fields['evidence_sha256']:
        raise EvidenceAttestationError('Physical evidence bytes mismatch signed digest')

    try:
        issued=datetime.fromisoformat(fields['issued_at_utc'].replace('Z','+00:00'))
    except ValueError as exc:
        raise EvidenceAttestationError('Invalid issued_at_utc timestamp') from exc
    if issued.tzinfo is None or issued.utcoffset()!=timedelta(0):
        raise EvidenceAttestationError('Timestamp must be UTC with timezone')
    now=now if now is not None else datetime.now(timezone.utc)
    if not isinstance(now,datetime) or now.tzinfo is None:
        raise EvidenceAttestationError('Clock must be timezone-aware')
    if max_age <= timedelta(0) or future_skew < timedelta(0):
        raise EvidenceAttestationError('Invalid temporal constraints')
    if issued - now > future_skew:
        raise EvidenceAttestationError('Attestation timestamp is in the future')
    if now - issued > max_age:
        raise EvidenceAttestationError('Attestation expired')

    try:
        signature=base64.b64decode(_str_field(envelope,'signature_b64'),validate=True)
        if len(signature)!=64:
            raise ValueError('Signature has invalid length')
        canonical=json.dumps(dict(payload),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
        Ed25519PublicKey.from_public_bytes(key.public_key_raw).verify(signature,canonical)
    except (ValueError,InvalidSignature,binascii.Error) as exc:
        raise EvidenceAttestationError('Invalid signature or unauthenticated payload') from exc

    return AttestationCheck(
       status='AUTHENTIC_ATTESTATION_ONLY',
       key_id=key_id,
       kind=expected_kind,
       run_id=fields['run_id'],
       evidence_sha256=observed_hash,
       subject_sha256=fields['subject_sha256'],
    )
