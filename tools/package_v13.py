"""Deterministic, inspectable OMEGA Studio 1.3 SOURCE-ONLY delivery.

This packaging function deliberately does not package an APK or claim ARM64
execution. Native release is separately gated by build_full_apk.sh.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

PREFIX='OMEGA_STUDIO_v1.3.0/'
EXCLUDE_DIRS={'.git','.pytest_cache','__pycache__','.gradle','.venv','dist','build','node_modules','OMEGA_STUDIO_v1_2_WORK'}
EXCLUDE_SUFFIXES={'.apk','.pyc','.pyo','.class','.gguf','.jks','.keystore'}
REQUIRED={
    'android/app/src/main/java/org/omega/actions/CodeServerManager.java',
    'android/app/src/main/java/org/omega/actions/RuntimeHealth.java',
    'android/app/src/main/java/org/omega/actions/CodeEditorActivity.java',
    'tools/verify_runtime_bundle.py',
    'tools/prepare_runtime_release.py',
    'tools/runtime_supply_chain.py',
    'tools/build_full_apk.sh',
    'tools/android_device_smoke.sh',
    'docs/NATIVE_RUNTIME_BUILD.md',
    'README.md',
}


def build_source_package(root:Path, output:Path)->dict:
    root=Path(root).resolve(strict=True)
    output=Path(output).resolve()
    files={}
    for path in root.rglob('*'):
        if not path.is_file() or path.is_symlink():continue
        rel=path.relative_to(root)
        if any(part in EXCLUDE_DIRS for part in rel.parts) or path.suffix in EXCLUDE_SUFFIXES:continue
        if rel.as_posix() in ('MANIFEST_SHA256.txt','RELEASE_STATUS.json'):continue
        if rel.parts[0]=='validation' and not (rel.name.startswith('V13_') or rel.name.startswith('vscode_') or rel.name in ('builder_desktop.png','builder_mobile.png')):continue
        if path.resolve()==output:continue
        files[rel.as_posix()]=path.read_bytes()
    if not REQUIRED.issubset(files):
        raise ValueError('Source archive missing required implementation: '+', '.join(sorted(REQUIRED-set(files))))
    status={'version':'1.3.0','package':'org.omega.actions','type':'SOURCE_ONLY',
            'binary_release_ready':False,'android_arm64_runtime_included':False,
            'android_device_test':'NOT_EXECUTED','production_signing':'NOT_EXECUTED',
            'release_gate':'BLOCKED_MISSING_NATIVE_RUNTIME',
            'required_commands':['bash','python','git','llama-cli','node','code-server']}
    files['RELEASE_STATUS.json']=(json.dumps(status,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode()
    files['MANIFEST_SHA256.txt']=''.join(
        hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in sorted(files.items())
    ).encode('ascii')
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=9,allowZip64=True) as z:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(PREFIX+name,date_time=(2020,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            z.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None:raise RuntimeError('Archive CRC verification failed')
        for line in z.read(PREFIX+'MANIFEST_SHA256.txt').decode('ascii').splitlines():
            digest,name=line.split('  ',1)
            if hashlib.sha256(z.read(PREFIX+name)).hexdigest()!=digest:
                raise RuntimeError('Archive SHA-256 verification failed: '+name)
    return {'file':str(output),'files':len(files),'bytes':output.stat().st_size,
            'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'binary_release_ready':False,'crc':'PASS','manifest':'PASS'}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(build_source_package(args.root,args.output),indent=2))
