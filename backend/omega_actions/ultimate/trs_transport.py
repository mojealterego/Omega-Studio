"""Per-session authenticated application envelope for sensitive payloads.

AES-GCM/HKDF are the cryptographic primitives; phi and zeta critical-line
imagery have no security role. Transport compromise cannot be categorically
ruled out, especially if endpoints or session keys are compromised.
"""
from __future__ import annotations
from collections import deque
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes


class EnvelopeError(ValueError):
    pass


class SessionEnvelope:
    MAGIC = b'OMEGA2'
    def __init__(self, *, master_key: bytes, session_id: bytes, replay_capacity: int = 4096):
        if not isinstance(master_key, bytes) or len(master_key) != 32:
            raise EnvelopeError('Master key must be exactly 32 bytes')
        if not isinstance(session_id, bytes) or not 12 <= len(session_id) <= 64:
            raise EnvelopeError('Session ID must be 12..64 bytes')
        if not 64 <= replay_capacity <= 65536:
            raise EnvelopeError('Invalid replay capacity')
        self.session_id = session_id
        key = HKDF(algorithm=hashes.SHA256(), length=32, salt=session_id,
                   info=b'OMEGA-TRS-transport-v2').derive(master_key)
        self._aead = AESGCM(key)
        self._seen: set[bytes] = set()
        self._order: deque[bytes] = deque()
        self._capacity = replay_capacity

    def _aad(self, context: bytes) -> bytes:
        if not isinstance(context, bytes) or len(context) > 1024:
            raise EnvelopeError('Invalid authenticated context')
        return self.MAGIC + self.session_id + context

    def encrypt(self, payload: bytes, *, context: bytes) -> bytes:
        if not isinstance(payload, bytes) or len(payload) > 16 * 1024 * 1024:
            raise EnvelopeError('Payload exceeds 16 MiB envelope bound')
        nonce = os.urandom(12)
        return self.MAGIC + nonce + self._aead.encrypt(nonce, payload, self._aad(context))

    def decrypt(self, packet: bytes, *, context: bytes) -> bytes:
        if not isinstance(packet, bytes) or len(packet) < len(self.MAGIC) + 12 + 16 or not packet.startswith(self.MAGIC):
            raise EnvelopeError('Malformed encrypted envelope')
        nonce = packet[len(self.MAGIC):len(self.MAGIC)+12]
        if nonce in self._seen:
            raise EnvelopeError('Replay detected')
        try:
            plaintext = self._aead.decrypt(nonce, packet[len(self.MAGIC)+12:], self._aad(context))
        except Exception as exc:
            raise EnvelopeError('Authentication failed') from exc
        if len(self._order) == self._capacity:
            self._seen.remove(self._order.popleft())
        self._order.append(nonce)
        self._seen.add(nonce)
        return plaintext
