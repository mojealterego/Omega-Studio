"""Reproducible source-only ZIP. Does not include an obsolete preview APK."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'OMEGA_STUDIO_v1.3.0_SOURCE_RUNTIME_PIPELINE.zip'
PREFIX='OMEGA_STUDIO_v1.3.0/'
EXCLUDED={'__pycache__','.pytest_cache','.git','dist'}

def included(p:Path)->bool:
    rel=p.relative_to(ROOT)
    if any(x in EXCLUDED for x in rel.parts):return False
    if p.suffix in ('.pyc','.pyo','.apk','.zip','.gguf'):return False
    if rel.name=='MANIFEST_SHA256.txt':return False
    if rel.parts[0]=='validation':return rel.name.startswith('v13_') and rel.suffix in ('.log','.json')
    return True

def package()->dict:
    files={p.relative_to(ROOT).as_posix():p.read_bytes() for p in sorted(ROOT.rglob('*')) if p.is_file() and included(p)}
    manifest=''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n' for name,data in sorted(files.items()))
    files['MANIFEST_SHA256.txt']=manifest.encode()
    with zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(PREFIX+name,date_time=(2020,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o644<<16
            z.writestr(info,data)
    with zipfile.ZipFile(OUT) as z:
        assert z.testzip() is None
        for line in z.read(PREFIX+'MANIFEST_SHA256.txt').decode().splitlines():
            digest,name=line.split('  ',1)
            assert hashlib.sha256(z.read(PREFIX+name)).hexdigest()==digest,name
    return {'archive':str(OUT),'files':len(files),'sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),
            'size_bytes':OUT.stat().st_size,'manifest_entries':len(files)-1,'zip_crc':'PASS'}

if __name__=='__main__':print(json.dumps(package(),indent=2))
