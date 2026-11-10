"""Fail-closed package builder: SHA-256 manifest, safe ZIP, independent extraction verification."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path
import shutil
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT.parent/'OMEGA_STUDIO_ANDROID_PRODUCTION_PACKAGE_v1.0.0.zip'
EXCLUDE_DIRS={'__pycache__','.pytest_cache','.git','.venv','node_modules'}
EXCLUDE_SUFFIXES={'.pyc','.pyo','.tmp'}
DOCS={'README.md','ARCHITECTURE.md','ENGINEERING_SPECIFICATION.md',
      'BEYOND_MAXIMUM_INNOVATIONS.md','MODULE_REFERENCE.md','API_REFERENCE.md',
      'SECURITY_ARCHITECTURE.md','BUILD_AND_DEPLOYMENT_GUIDE.md',
      'TESTING_AND_VALIDATION.md','DEPENDENCIES_AND_LICENSES.md',
      'DIGITAL_LIFE_COMPATIBILITY.md','INTEGRATION_BLUEPRINT.md',
      'PRODUCTION_READINESS_REPORT.md'}
CODE_SUFFIXES={'.py','.java','.js','.mjs','.html','.css','.gradle','.sh','.ps1'}


def files():
    result=[]
    for p in ROOT.rglob('*'):
        if p.is_symlink():
            raise RuntimeError('Symlink in deliverable: '+str(p))
        if not p.is_file() or p.name=='MANIFEST_SHA256.txt':
            continue
        rel=p.relative_to(ROOT)
        if EXCLUDE_DIRS.intersection(rel.parts) or p.suffix in EXCLUDE_SUFFIXES:
            continue
        if rel.is_absolute() or '..' in rel.parts:
            raise RuntimeError('Unsafe file path')
        result.append((rel,p))
    return sorted(result,key=lambda x:x[0].as_posix())


def sha(p:Path):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def code_lines(paths):
    count=0
    for rel,p in paths:
        if p.suffix in CODE_SUFFIXES and not rel.parts[0] in ('validation',):
            count+=len(p.read_text('utf-8').splitlines())
    return count


def build():
    present={p.name for p in ROOT.glob('*.md')}
    if present!=DOCS:
        raise RuntimeError('Required documentation mismatch: '+repr(sorted(DOCS^present)))
    paths=files()
    for rel,p in paths:
        if p.suffix in CODE_SUFFIXES or p.suffix=='.md':
            data=p.read_text('utf-8')
            if re.search(r'^\s*(?:#|//|/\*|\*)\s*(?:TO'+'DO|FIX'+'ME|T'+'BD)\b',data,re.MULTILINE):
                raise RuntimeError(f'Unfinished implementation comment in {rel}')
    manifest=''.join(f'{sha(p)}  {rel.as_posix()}\n' for rel,p in paths)
    (ROOT/'MANIFEST_SHA256.txt').write_text(manifest,encoding='utf-8')
    paths.append((Path('MANIFEST_SHA256.txt'),ROOT/'MANIFEST_SHA256.txt'))
    if OUTPUT.exists():OUTPUT.unlink()
    with zipfile.ZipFile(OUTPUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9,strict_timestamps=True) as z:
        for rel,p in paths:
            z.write(p,arcname=rel.as_posix())
    with zipfile.ZipFile(OUTPUT) as z:
        if z.testzip() is not None:raise RuntimeError('ZIP CRC verification failed')
        names=z.namelist()
        if len(names)!=len(paths) or len(set(names))!=len(paths):
            raise RuntimeError('ZIP count or uniqueness mismatch')
        for name in names:
            p=Path(name)
            if p.is_absolute() or '..' in p.parts:
                raise RuntimeError('ZIP traversal path')
        with tempfile.TemporaryDirectory(prefix='omega-package-verify-') as d:
            dest=Path(d)
            z.extractall(dest)
            lines=(dest/'MANIFEST_SHA256.txt').read_text('utf-8').splitlines()
            if len(lines)!=len(paths)-1:raise RuntimeError('Manifest entry count mismatch')
            for line in lines:
                digest,rel=line.split('  ',1)
                if sha(dest/rel)!=digest:
                    raise RuntimeError('Extracted SHA-256 mismatch for '+rel)
    report={'package':str(OUTPUT),'package_bytes':OUTPUT.stat().st_size,
            'package_sha256':sha(OUTPUT),'files_in_archive':len(paths),
            'source_code_lines_including_tests':code_lines(paths),
            'root_documentation_files':len(DOCS),
            'zip_crc':'PASS','extraction':'PASS','manifest_sha256':'PASS',
            'repository_writes':'NONE','deployment':'NONE'}
    report_path=ROOT.parent/'OMEGA_STUDIO_ANDROID_PACKAGE_v1_VERIFICATION.json'
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    print(json.dumps(build(),ensure_ascii=False,indent=2))
