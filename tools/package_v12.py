"""Deterministic source and APK-preview archive with verified SHA-256 manifest."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=Path('/mnt/data/OMEGA_STUDIO_ANDROID_APPBUILDER_SOURCE_PREVIEW_v1.2.0.zip')
PREFIX='OMEGA_STUDIO_v1.2.0/'
EXCLUDED={'__pycache__','.pytest_cache','.git'}
VALIDATION={'full_python_tests.log','full_js_tests.log','browser.log','native_java.log',
            'android_sources.log','apk_preview_build.log','runtime_release_gate.log',
            'builder_desktop.png','builder_mobile.png','premium_app_export.zip','generated_browser_export.zip'}

def included(path:Path)->bool:
    rel=path.relative_to(ROOT)
    if any(x in EXCLUDED for x in rel.parts):return False
    if path.suffix in ('.pyc','.pyo'):return False
    if rel.parts[0]=='dist':return rel.name=='OMEGA_STUDIO_APPBUILDER_UI_PREVIEW_v1.2.0.apk'
    if rel.parts[0]=='validation':return rel.name in VALIDATION
    if rel.name=='MANIFEST_SHA256.txt':return False
    if rel.name.endswith('.apk') or rel.name.endswith('.zip'):return False
    return True

def package()->dict:
    files={p.relative_to(ROOT).as_posix():p.read_bytes() for p in sorted(ROOT.rglob('*')) if p.is_file() and included(p)}
    manifest=''.join(f'{hashlib.sha256(data).hexdigest()}  {path}\n' for path,data in sorted(files.items()))
    files['MANIFEST_SHA256.txt']=manifest.encode('utf-8')
    with zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path,data in sorted(files.items()):
            info=zipfile.ZipInfo(PREFIX+path,date_time=(2020,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o644<<16
            z.writestr(info,data)
    with zipfile.ZipFile(OUT) as z:
        assert z.testzip() is None
        for line in z.read(PREFIX+'MANIFEST_SHA256.txt').decode().splitlines():
            digest,path=line.split('  ',1)
            assert hashlib.sha256(z.read(PREFIX+path)).hexdigest()==digest,path
    result={'archive':str(OUT),'sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),
            'files':len(files),'size_bytes':OUT.stat().st_size,
            'source_lines':sum(data.count(b'\n')+1 for path,data in files.items() if path.endswith(('.py','.js','.java','.css','.html','.mjs','.sh','.ps1'))),
            'manifest_entries':len(files)-1,'zip_crc':'PASS','sha256_manifest':'PASS'}
    (ROOT/'validation/FINAL_PACKAGE_v12.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(package(),indent=2))
