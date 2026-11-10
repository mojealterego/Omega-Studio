"""Small reproducible source-code-only backup suitable for GitHub Git Blob API."""
from __future__ import annotations
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
INCLUDE = ('android','backend','builder','config','docs','native','tests','tools')

def build(output: Path) -> dict:
    output = Path(output).resolve(strict=False)
    if output.is_relative_to(ROOT) or output.exists():
        raise ValueError('Backup must be new and outside project')
    files=[]
    for folder in INCLUDE:
        for path in (ROOT/folder).rglob('*'):
            if not path.is_file() or path.is_symlink() or any(p in ('.git','__pycache__','.pytest_cache','node_modules') for p in path.parts):
                continue
            if path.suffix in ('.pyc','.apk','.so','.png','.jpg','.jpeg','.log','.pdf','.zip'):
                continue
            files.append(path)
    files += [ROOT/'README.md',ROOT/'PRODUCTION_READINESS_REPORT.md',ROOT/'RELEASE_STATUS.json',
              ROOT/'third_party/UPLOADED_SOURCE_ARCHIVES.json']
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in sorted(files):
            info=zipfile.ZipInfo('OMEGA_STUDIO_v2_SOURCE/'+path.relative_to(ROOT).as_posix(),date_time=(2026,11,10,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,path.read_bytes())
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None:raise ValueError('CRC failure')
    with output.open('rb') as stream:
        digest=hashlib.file_digest(stream,'sha256').hexdigest()
    return {'files':len(files),'bytes':output.stat().st_size,'sha256':digest}

if __name__=='__main__':
    import json,sys
    print(json.dumps(build(Path(sys.argv[1])),indent=2))
