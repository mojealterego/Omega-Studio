"""Package the isolated OMEGA Studio continuation, verify every ZIP member SHA-256."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'OMEGA_STUDIO_ANDROID_CONTINUATION_PACKAGE_v1.1.0.zip'
EXCLUDED={'.pytest_cache','__pycache__','.git','.mypy_cache'}


def source_files():
    return sorted(p for p in ROOT.rglob('*') if p.is_file() and not any(x in EXCLUDED for x in p.relative_to(ROOT).parts)
                  and not p.name.endswith(('.pyc','.class')) and p.name!='MANIFEST_SHA256.txt')


def main():
    files=source_files()
    manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(ROOT).as_posix()+'\n' for p in files)
    (ROOT/'MANIFEST_SHA256.txt').write_text(manifest,encoding='utf-8')
    entries=files+[ROOT/'MANIFEST_SHA256.txt']
    with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9,allowZip64=True) as z:
        for p in entries:
            arc='OMEGA_STUDIO_ANDROID_v1_1/'+p.relative_to(ROOT).as_posix()
            z.write(p,arcname=arc)
    with zipfile.ZipFile(OUT) as z:
        if z.testzip() is not None:raise RuntimeError('CRC error in ZIP')
        found=set(z.namelist())
        assert len(found)==len(entries)
        for line in manifest.splitlines():
            sha,relative=line.split('  ',1)
            data=z.read('OMEGA_STUDIO_ANDROID_v1_1/'+relative)
            if hashlib.sha256(data).hexdigest()!=sha:raise RuntimeError('SHA mismatch: '+relative)
    suffixes={'.py','.java','.js','.html','.css','.sh','.ps1','.gradle'}
    source=[p for p in files if p.suffix in suffixes]
    loc=sum(len(p.read_text('utf-8',errors='replace').splitlines()) for p in source)
    result={'archive':str(OUT),'sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),
            'bytes':OUT.stat().st_size,'files':len(entries),'source_files':len(source),'source_lines':loc,
            'manifest_entries':len(files),'zip_crc':'PASS','sha256_manifest':'PASS'}
    print(json.dumps(result,indent=2,ensure_ascii=False))
    return result


if __name__=='__main__':main()
