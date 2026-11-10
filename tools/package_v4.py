"""Deterministic archive manifest, CRC, SHA-256 and APK-v2 structural validation."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import zipfile
from tools.apk_signing import verify_apk
from tools.validate_dex import verify_dex

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT.parent/'OMEGA_STUDIO_ANDROID_SOURCE_AND_PREVIEW_v4.0.0.zip'
APK='dist/OMEGA_STUDIO_ANDROID_OFFLINE_PREVIEW_v4.0.0.apk'
EXCLUDE_DIRS={'.git','__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','.venv','javac','node_modules'}
EXCLUDE_FILES={'MANIFEST_SHA256.txt'}

def files():
    return sorted((p for p in ROOT.rglob('*') if p.is_file() and p.name not in EXCLUDE_FILES
                   and not any(x in EXCLUDE_DIRS for x in p.relative_to(ROOT).parts)
                   and p.suffix not in ('.pyc','.class','.pyo')),
                  key=lambda p:p.relative_to(ROOT).as_posix())

def create():
    apk=ROOT/APK
    if not apk.is_file() or not verify_apk(apk):raise RuntimeError('Signed APK is missing or invalid')
    with zipfile.ZipFile(apk) as z:
        dex=verify_dex(z.read('classes.dex'))
        if 'assets/index.html' not in z.namelist() or 'assets/app.js' not in z.namelist():
            raise RuntimeError('APK is missing UI assets')
    entries=files()
    manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(ROOT).as_posix()+'\n' for p in entries)
    (ROOT/'MANIFEST_SHA256.txt').write_text(manifest,encoding='utf-8')
    with zipfile.ZipFile(OUTPUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9,allowZip64=True) as z:
        for p in entries:z.write(p,p.relative_to(ROOT).as_posix())
        z.writestr('MANIFEST_SHA256.txt',manifest)
    with zipfile.ZipFile(OUTPUT) as z:
        if z.testzip() is not None:raise RuntimeError('Archive CRC verification failed')
        names=z.namelist()
        if len(names)!=len(set(names)) or len(names)!=len(entries)+1:raise RuntimeError('Missing or duplicate files')
        for line in z.read('MANIFEST_SHA256.txt').decode().splitlines():
            digest,name=line.split('  ',1)
            if name.startswith('/') or '..' in Path(name).parts:raise RuntimeError('Unsafe path')
            if hashlib.sha256(z.read(name)).hexdigest()!=digest:raise RuntimeError('SHA-256 mismatch: '+name)
    return {'zip_path':str(OUTPUT),'zip_bytes':OUTPUT.stat().st_size,
            'zip_sha256':hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
            'files':len(entries)+1,'source_lines':sum(len(p.read_text(errors='replace').splitlines()) for p in entries if p.suffix in ('.py','.java','.js','.css','.html')),
            'documentation_files':sum(p.suffix=='.md' for p in entries),
            'apk_bytes':apk.stat().st_size,'apk_sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),
            'apk_classes':dex['classes'],'apk_signed_v2':True,'crc':'PASS','sha256_manifest_entries':len(entries)}

if __name__=='__main__':print(json.dumps(create(),ensure_ascii=False,indent=2))
