"""SHA-256 CAS and safe local cache restore; reflink fast path where available."""
import hashlib
import json
import os
import shutil
from pathlib import Path
import tempfile

class CAS:
    def __init__(self,root:Path):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
    def _path(self,digest:str)->Path:
        if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest): raise ValueError('Invalid digest')
        return self.root/'blobs'/digest[:2]/digest
    def put(self,data:bytes)->str:
        digest=hashlib.sha256(data).hexdigest(); target=self._path(digest)
        if target.exists(): return digest
        target.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(dir=target.parent)
        try:
            with os.fdopen(fd,'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
            os.chmod(tmp,0o444)
            if not target.exists(): os.replace(tmp,target)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
        return digest
    def get(self,digest:str)->bytes:
        data=self._path(digest).read_bytes()
        if hashlib.sha256(data).hexdigest()!=digest: raise ValueError('Corrupted CAS blob')
        return data
    def put_file(self,source:Path)->str:
        source=Path(source)
        if source.is_symlink() or not source.is_file(): raise ValueError('Unsafe source file')
        digest=hashlib.sha256()
        with source.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024),b''): digest.update(chunk)
        hexdigest=digest.hexdigest(); target=self._path(hexdigest)
        if not target.exists():
            target.parent.mkdir(parents=True,exist_ok=True)
            fd,tmp=tempfile.mkstemp(dir=target.parent)
            try:
                with os.fdopen(fd,'wb') as dst,source.open('rb') as src: shutil.copyfileobj(src,dst)
                os.chmod(tmp,0o444)
                if not target.exists(): os.replace(tmp,target)
            finally:
                if os.path.exists(tmp): os.unlink(tmp)
        return hexdigest
    def restore_file(self,digest:str,destination:Path):
        src=self._path(digest)
        if hashlib.sha256(src.read_bytes()).hexdigest()!=digest: raise ValueError('Corrupted CAS blob')
        destination=Path(destination); destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.is_symlink(): raise ValueError('Refusing symlink destination')
        # Linux reflink: copy-on-write (zero-copy where supported), safe against cache mutation.
        try:
            import fcntl
            with src.open('rb') as inp,destination.open('wb') as out:
                fcntl.ioctl(out.fileno(),0x40049409,inp.fileno())
        except (ImportError,OSError): shutil.copyfile(src,destination)
        if hashlib.sha256(destination.read_bytes()).hexdigest()!=digest: raise ValueError('CAS restore failed')

class DependencyCache:
    def __init__(self,root:Path):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
        self.cas=CAS(self.root/'cas')
    def _index(self,key:str)->Path:
        return self.root/'keys'/(hashlib.sha256(key.encode()).hexdigest()+'.json')
    def save(self,key:str,paths:list[str],workspace:Path,secrets:list[str]|None=None)->int:
        files={'__key':key}
        workspace=workspace.resolve()
        for pattern in paths:
            for path in workspace.glob(pattern):
                if path.is_symlink(): continue
                for item in ([path] if path.is_file() else path.rglob('*')):
                    if item.is_symlink() or not item.is_file(): continue
                    resolved=item.resolve()
                    if not resolved.is_relative_to(workspace): continue
                    content=item.read_bytes()
                    if any(secret.encode('utf-8') in content for secret in (secrets or []) if secret):
                        raise ValueError('Dependency cache contains a secret; save rejected')
                    files[str(resolved.relative_to(workspace))]=self.cas.put_file(item)
        index=self._index(key); index.parent.mkdir(parents=True,exist_ok=True)
        tmp=index.with_suffix('.tmp')
        tmp.write_text(json.dumps(files,sort_keys=True),encoding='utf-8'); os.replace(tmp,index)
        return len(files)-1
    def restore(self,key:str,workspace:Path,restore_keys:list[str]|None=None)->int:
        index=self._index(key)
        if not index.exists():
            for prefix in restore_keys or []:
                for candidate in sorted((self.root/'keys').glob('*.json')):
                    # Prefix matching requires stored key, not hash; see metadata below.
                    try: obj=json.loads(candidate.read_text())
                    except (OSError,ValueError): continue
                    if isinstance(obj,dict) and obj.get('__key','').startswith(prefix):
                        index=candidate; break
                if index.exists(): break
        if not index.exists(): return 0
        data=json.loads(index.read_text())
        workspace=workspace.resolve(); count=0
        for rel,digest in data.items():
            if rel=='__key': continue
            dest=(workspace/rel).resolve()
            if not dest.is_relative_to(workspace): raise ValueError('Cache path escape')
            self.cas.restore_file(digest,dest); count+=1
        return count
