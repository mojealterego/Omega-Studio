"""Path-safe artifact packaging, integrity manifest, and extraction."""
import hashlib
import hmac
import os
import json
from pathlib import Path, PurePosixPath
import zipfile

class ArtifactStore:
    def __init__(self,root:Path):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
        self.key_path=self.root/'.seal-key'
        if not self.key_path.exists():
            try:
                fd=os.open(self.key_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
                with os.fdopen(fd,'wb') as f: f.write(os.urandom(32))
            except FileExistsError: pass
        self.seal_key=self.key_path.read_bytes()
        if len(self.seal_key)!=32: raise ValueError('Invalid artifact seal key')
    def _target(self,run_id:str,name:str)->Path:
        if not run_id.isalnum() or not name or not all(c.isalnum() or c in '-_.' for c in name):
            raise ValueError('Unsafe artifact identifier')
        return self.root/run_id/(name+'.zip')
    def upload(self,run_id:str,name:str,patterns:list[str],workspace:Path,secrets:list[str]|None=None)->tuple[Path,int,str]:
        workspace=workspace.resolve(); files={}
        for pattern in patterns:
            for path in workspace.glob(pattern):
                for item in ([path] if path.is_file() else path.rglob('*')):
                    if item.is_symlink() or not item.is_file(): continue
                    rp=item.resolve()
                    if rp.is_relative_to(workspace): files[rp.relative_to(workspace).as_posix()]=item
        if not files: raise FileNotFoundError('Artifact has no matching files')
        dest=self._target(run_id,name); dest.parent.mkdir(parents=True,exist_ok=True)
        manifest={}
        temporary=dest.with_suffix('.pending')
        try:
            with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
                for rel,item in sorted(files.items()):
                    if item.stat().st_size > 1024**3: raise ValueError('Artifact file too large')
                    data=item.read_bytes()
                    if any(secret.encode('utf-8') in data for secret in (secrets or []) if secret):
                        raise ValueError('Artifact contains a secret value; upload rejected')
                    if rel=='OMEGA_ARTIFACT_MANIFEST.json': raise ValueError('Reserved artifact manifest filename')
                    manifest[rel]=hashlib.sha256(data).hexdigest(); z.writestr(rel,data)
                z.writestr('OMEGA_ARTIFACT_MANIFEST.json',json.dumps(manifest,sort_keys=True))
            os.replace(temporary,dest)
        finally:
            temporary.unlink(missing_ok=True)
        digest=hashlib.sha256(dest.read_bytes()).hexdigest()
        seal=hmac.new(self.seal_key,dest.read_bytes(),hashlib.sha3_256).hexdigest()
        dest.with_suffix('.seal').write_text(seal,encoding='ascii')
        return dest,len(files),digest
    def verify(self,run_id:str,name:str)->bool:
        source=self._target(run_id,name)
        expected=source.with_suffix('.seal').read_text('ascii')
        actual=hmac.new(self.seal_key,source.read_bytes(),hashlib.sha3_256).hexdigest()
        if not hmac.compare_digest(expected,actual): raise ValueError('Artifact seal verification failed')
        return True
    def download(self,run_id:str,name:str,destination:Path)->int:
        source=self._target(run_id,name)
        self.verify(run_id,name)
        destination=destination.resolve(); destination.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(source) as z:
            manifest=json.loads(z.read('OMEGA_ARTIFACT_MANIFEST.json'))
            if len(manifest)>20000: raise ValueError('Too many artifact entries')
            count=0; total=0
            for entry in z.infolist():
                if entry.filename=='OMEGA_ARTIFACT_MANIFEST.json': continue
                rel=PurePosixPath(entry.filename)
                if rel.is_absolute() or '..' in rel.parts: raise ValueError('Artifact traversal rejected')
                if (entry.external_attr >> 16) & 0o170000 == 0o120000: raise ValueError('Artifact symlink rejected')
                if entry.file_size > 1024**3: raise ValueError('Artifact too large')
                total+=entry.file_size
                if total > 2*1024**3: raise ValueError('Artifact exceeds extraction limit')
                dest=(destination/str(rel)).resolve()
                if not dest.is_relative_to(destination): raise ValueError('Artifact escapes workspace')
                data=z.read(entry)
                if hashlib.sha256(data).hexdigest()!=manifest.get(entry.filename): raise ValueError('Artifact checksum mismatch')
                dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(data); count+=1
        return count
