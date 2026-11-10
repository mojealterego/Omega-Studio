"""Local encrypted secret vault. Argon2id -> AES-256-GCM plus HMAC-SHA3-256 envelope."""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class VaultError(ValueError):
    pass

class SecretVault:
    def __init__(self, path: Path, password: str):
        if not password: raise VaultError('Nonempty vault password required')
        self.path = Path(path)
        self.password = password.encode('utf-8')
    def _derive(self, salt: bytes) -> bytes:
        return hash_secret_raw(self.password,salt,time_cost=3,memory_cost=65536,parallelism=2,hash_len=64,type=Type.ID)
    def _read(self) -> dict[str,str]:
        if not self.path.exists(): return {}
        try:
            env=json.loads(self.path.read_text('utf-8'))
            if env.get('version') != 1: raise VaultError('Unsupported vault version')
            salt=base64.b64decode(env['salt'],validate=True)
            nonce=base64.b64decode(env['nonce'],validate=True)
            ct=base64.b64decode(env['ciphertext'],validate=True)
            tag=base64.b64decode(env['hmac'],validate=True)
            keys=self._derive(salt)
            payload=b'OMEGA-TRS-SEAL-v1'+salt+nonce+ct
            if not hmac.compare_digest(hmac.new(keys[32:],payload,hashlib.sha3_256).digest(),tag):
                raise VaultError('Invalid password or corrupted vault')
            plaintext=AESGCM(keys[:32]).decrypt(nonce,ct,b'OMEGA-TRS-SEAL-v1')
            value=json.loads(plaintext)
            if not isinstance(value,dict): raise VaultError('Corrupted vault')
            return value
        except VaultError: raise
        except Exception as exc: raise VaultError('Invalid password or corrupted vault') from exc
    def _write(self, values: dict[str,str]):
        salt=os.urandom(16); nonce=os.urandom(12)
        keys=self._derive(salt)
        ct=AESGCM(keys[:32]).encrypt(nonce,json.dumps(values,ensure_ascii=False,sort_keys=True).encode(),b'OMEGA-TRS-SEAL-v1')
        tag=hmac.new(keys[32:],b'OMEGA-TRS-SEAL-v1'+salt+nonce+ct,hashlib.sha3_256).digest()
        data={'version':1,'kdf':'argon2id','cipher':'AES-256-GCM','mac':'HMAC-SHA3-256',
              'salt':base64.b64encode(salt).decode(),'nonce':base64.b64encode(nonce).decode(),
              'ciphertext':base64.b64encode(ct).decode(),'hmac':base64.b64encode(tag).decode()}
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_name(self.path.name+'.tmp-'+os.urandom(4).hex())
        try:
            fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,'w',encoding='utf-8') as f:
                json.dump(data,f,indent=2); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,self.path)
            if os.name != 'nt': self.path.chmod(0o600)
        finally:
            tmp.unlink(missing_ok=True)
    def list(self) -> list[str]:
        return sorted(self._read())
    def all(self) -> dict[str,str]:
        return self._read()
    def get(self,key:str) -> str:
        return self._read()[key]
    def set(self,key:str,value:str) -> None:
        if not key.isidentifier() or not isinstance(value,str): raise VaultError('Invalid secret name or value')
        values=self._read(); values[key]=value; self._write(values)
    def delete(self,key:str) -> None:
        values=self._read(); values.pop(key,None); self._write(values)
