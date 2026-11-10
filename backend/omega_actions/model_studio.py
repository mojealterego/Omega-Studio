"""Local GGUF inspection, validated generation parameters and resumable HF downloads.

Does not claim to run inference; inference requires an installed llama.cpp binary.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib
import math
from pathlib import Path
import re
import struct
from urllib.parse import quote, urlparse, urljoin
import httpx

class GGUFError(ValueError):
    """Malformed or unsupported GGUF metadata."""

class HFError(RuntimeError):
    """Download failed without exposing an authentication token."""

@dataclass(frozen=True)
class ModelParameters:
    context: int = 4096
    threads: int = 4
    batch: int = 256
    gpu_layers: int = 0
    temperature: float = 0.7
    top_k: int = 40
    top_p: float = 0.95
    min_p: float = 0.05
    repeat_penalty: float = 1.1
    seed: int = -1
    max_tokens: int = 512

    def __post_init__(self):
        for key,low,high in [('context',128,131072),('threads',1,128),('batch',1,8192),
                             ('gpu_layers',0,512),('top_k',0,100000),('seed',-1,2**31-1),
                             ('max_tokens',1,131072)]:
            val=getattr(self,key)
            if isinstance(val,bool) or not isinstance(val,int) or not low<=val<=high:
                raise ValueError(f'{key} must be an integer in [{low}, {high}]')
        for key,low,high in [('temperature',0.,5.),('top_p',0.,1.),('min_p',0.,1.),
                             ('repeat_penalty',0.1,10.)]:
            val=getattr(self,key)
            if isinstance(val,bool) or not isinstance(val,(float,int)) or not math.isfinite(val) or not low<=val<=high:
                raise ValueError(f'{key} must be finite in [{low}, {high}]')

    def to_dict(self):
        return asdict(self)

class GGUFInspector:
    _sizes={0:1,1:1,2:2,3:2,4:4,5:4,6:4,7:1,10:8,11:8,12:8}
    _formats={0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
    MAX_KEYS=100000
    MAX_STRING=1024*1024
    MAX_ARRAY=100000
    MAX_BYTES=8*1024*1024

    @classmethod
    def inspect(cls,path:Path)->dict:
        path=Path(path)
        size=path.stat().st_size
        if size<24: raise GGUFError('Truncated GGUF header')
        with path.open('rb') as f:
            budget=[cls.MAX_BYTES]
            def read(n:int)->bytes:
                if n<0 or n>budget[0] or n>size-f.tell():
                    raise GGUFError('GGUF header exceeds file or metadata budget')
                budget[0]-=n
                b=f.read(n)
                if len(b)!=n: raise GGUFError('Truncated GGUF')
                return b
            def num(fmt):return struct.unpack('<'+fmt,read(struct.calcsize(fmt)))[0]
            def string():
                n=num('Q')
                if n>cls.MAX_STRING: raise GGUFError('GGUF string exceeds size limit')
                try:return read(n).decode('utf-8')
                except UnicodeDecodeError as e:raise GGUFError('Invalid GGUF UTF-8') from e
            def value(typ,depth=0):
                if depth>2: raise GGUFError('GGUF metadata nesting limit exceeded')
                if typ==8:return string()
                if typ==9:
                    elem=num('I');count=num('Q')
                    if count>cls.MAX_ARRAY:raise GGUFError('GGUF array exceeds limit')
                    if elem not in cls._formats and elem not in (8,9):raise GGUFError('Unknown GGUF array type')
                    return [value(elem,depth+1) for _ in range(count)]
                if typ not in cls._formats:raise GGUFError('Unknown GGUF metadata type')
                return num(cls._formats[typ])
            if read(4)!=b'GGUF':raise GGUFError('Invalid GGUF magic')
            version=num('I')
            if version not in (2,3):raise GGUFError('Unsupported GGUF version')
            tensors=num('Q');count=num('Q')
            if count>cls.MAX_KEYS:raise GGUFError('Too many GGUF metadata entries')
            metadata={}
            for _ in range(count):
                key=string()
                if key in metadata:raise GGUFError('Duplicate GGUF key')
                metadata[key]=value(num('I'))
            return {'version':version,'tensor_count':tensors,'metadata_count':count,
                    'metadata':metadata,'file_size':size,'file_name':path.name}

_HF_SEG=re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')

def hf_resolve_url(repo:str,revision:str,filename:str)->str:
    parts=repo.split('/')
    if len(parts)!=2 or not all(_HF_SEG.fullmatch(p) and p not in ('.','..') for p in parts):
        raise ValueError('Hugging Face repo must be namespace/name')
    if not _HF_SEG.fullmatch(revision) or revision in ('.','..'):
        raise ValueError('Invalid revision; use a branch, tag or commit SHA')
    segs=filename.split('/')
    if not segs or any(not _HF_SEG.fullmatch(s) or s in ('.','..') for s in segs) or not filename.lower().endswith('.gguf'):
        raise ValueError('Only relative .gguf paths are supported')
    return 'https://huggingface.co/'+quote(repo,safe='/')+'/resolve/'+quote(revision,safe='')+'/'+quote(filename,safe='/')+'?download=true'

_ALLOWED_REDIRECT_HOSTS={'huggingface.co','cdn-lfs.huggingface.co','cdn-lfs-us-1.huggingface.co',
                         'cdn-lfs-eu-1.huggingface.co','cas-bridge.xethub.hf.co',
                         'transfer.xethub.hf.co','cas-server.xethub.hf.co'}

def _trusted_redirect(url:str)->bool:
    p=urlparse(url)
    return p.scheme=='https' and p.hostname in _ALLOWED_REDIRECT_HOSTS and p.port in (None,443) and not p.username and not p.password

class HFDownload:
    def __init__(self,client:httpx.Client|None=None,max_bytes:int=50*1024**3):
        self.client=client or httpx.Client(timeout=httpx.Timeout(120,connect=15),follow_redirects=False)
        self.max_bytes=max_bytes

    def download(self,repo:str,revision:str,filename:str,target:Path,token:str|None=None,
                 expected_sha256:str|None=None)->dict:
        url=hf_resolve_url(repo,revision,filename)
        target=Path(target)
        if target.suffix.lower()!='.gguf':raise ValueError('Destination must end with .gguf')
        if expected_sha256 is not None and not re.fullmatch(r'[0-9a-fA-F]{64}',expected_sha256):
            raise ValueError('Expected digest must be SHA-256 hex')
        target.parent.mkdir(parents=True,exist_ok=True)
        partial=target.with_name(target.name+'.part')
        offset=partial.stat().st_size if partial.exists() else 0
        if offset>self.max_bytes:raise HFError('Partial file exceeds configured limit')
        headers={'User-Agent':'OMEGA-Studio/4.0'}
        if token:headers['Authorization']='Bearer '+token
        if offset:headers['Range']=f'bytes={offset}-'
        try:
            for redirect in range(6):
                if not _trusted_redirect(url):raise HFError('Untrusted download redirect rejected')
                request_headers=headers if urlparse(url).hostname=='huggingface.co' else {k:v for k,v in headers.items() if k!='Authorization'}
                with self.client.stream('GET',url,headers=request_headers) as response:
                    if response.status_code in (301,302,303,307,308):
                        location=response.headers.get('location')
                        if not location:raise HFError('Redirect without Location')
                        url=urljoin(url,location)
                        continue
                    if response.status_code not in (200,206):raise HFError(f'HTTP {response.status_code} during download')
                    if offset:
                        if response.status_code!=206:raise HFError('Server ignored requested resume range')
                        cr=response.headers.get('content-range','')
                        if not cr.startswith(f'bytes {offset}-'):raise HFError('Invalid Content-Range')
                    if not offset and response.status_code==206:raise HFError('Unexpected partial response')
                    length=response.headers.get('content-length')
                    if length and (int(length)+offset)>self.max_bytes:raise HFError('Model exceeds size limit')
                    sha=hashlib.sha256()
                    if offset:
                        with partial.open('rb') as f:
                            for chunk in iter(lambda:f.read(1024*1024),b''):sha.update(chunk)
                    total=offset
                    with partial.open('ab' if offset else 'wb') as f:
                        for chunk in response.iter_bytes(chunk_size=1024*1024):
                            total+=len(chunk)
                            if total>self.max_bytes:raise HFError('Model exceeds size limit')
                            f.write(chunk);sha.update(chunk)
                    digest=sha.hexdigest()
                    if expected_sha256 and digest.lower()!=expected_sha256.lower():
                        raise HFError('Downloaded model digest mismatch')
                    if total<4 or partial.open('rb').read(4)!=b'GGUF':raise HFError('Downloaded file is not GGUF')
                    partial.replace(target)
                    return {'path':str(target),'bytes':total,'sha256':digest}
            raise HFError('Too many redirects')
        except (httpx.HTTPError, OSError) as exc:
            raise HFError(f'Download failed: {type(exc).__name__}') from exc

class ModelCatalog:
    def __init__(self,root:Path):
        self.root=Path(root).expanduser().resolve()
        self.root.mkdir(parents=True,exist_ok=True)

    def path(self,name:str)->Path:
        if not isinstance(name,str) or not name.lower().endswith('.gguf') or name in ('.','..'):
            raise ValueError('Invalid GGUF name')
        p=(self.root/name).resolve()
        if not p.is_relative_to(self.root) or not p.is_file():
            raise ValueError('GGUF not found inside model directory')
        return p

    def list(self)->list[dict]:
        return [{'name':p.name,'bytes':p.stat().st_size} for p in sorted(self.root.glob('*.gguf')) if p.is_file() and not p.is_symlink()]

    def inspect(self,name:str)->dict:
        return GGUFInspector.inspect(self.path(name))
