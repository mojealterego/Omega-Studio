"""Deterministic offline release package with verified uploaded source archives."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TIMESTAMP = (2026, 11, 10, 0, 0, 0)
ARCHIVES = ('vscode-main.zip', 'termux-app-master.zip', 'llama.cpp-master.zip',
            'vscode-droidscript-code-master.zip', 'vscode-droidscript-docs-master.zip')


def package(output: Path, source_dir: Path) -> dict:
    output = Path(output).resolve(strict=False)
    source_dir = Path(source_dir).resolve(strict=True)
    if output.is_relative_to(ROOT) or output.exists():
        raise ValueError('Output must be outside source tree and not exist')
    registry = json.loads((ROOT/'third_party/UPLOADED_SOURCE_ARCHIVES.json').read_text())
    by_name = {record['archive']:record for record in registry['archives']}
    records: list[tuple[str,Path,int]] = []
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel in ('MANIFEST_SHA256.txt',) or '__pycache__' in path.parts or '.pytest_cache' in path.parts:
            continue
        if any(part in ('.git','node_modules') for part in path.parts):
            continue
        records.append((rel,path,zipfile.ZIP_DEFLATED))
    for name in ARCHIVES:
        path = source_dir/name
        if not path.is_file():
            raise ValueError('Required user-supplied source archive missing: '+name)
        digest = hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
        if digest != by_name[name]['sha256']:
            raise ValueError('Source archive SHA-256 mismatch: '+name)
        records.append(('third_party/source_archives/'+name,path,zipfile.ZIP_STORED))
    output.parent.mkdir(parents=True,exist_ok=True)
    manifest = []
    with zipfile.ZipFile(output,'w',allowZip64=True) as bundle:
        for name,path,compression in records:
            digest = hashlib.sha256()
            info = zipfile.ZipInfo('OMEGA_STUDIO_ULTIMATE_v2.0.0/'+name, date_time=TIMESTAMP)
            info.compress_type = compression
            info.external_attr = (0o100644 << 16)
            with path.open('rb') as source, bundle.open(info,'w',force_zip64=path.stat().st_size>=2**31) as dest:
                for chunk in iter(lambda:source.read(1024*1024),b''):
                    digest.update(chunk)
                    dest.write(chunk)
            manifest.append(f'{digest.hexdigest()}  {name}')
        content = ('\n'.join(manifest)+'\n').encode()
        info = zipfile.ZipInfo('OMEGA_STUDIO_ULTIMATE_v2.0.0/MANIFEST_SHA256.txt', date_time=TIMESTAMP)
        info.compress_type = zipfile.ZIP_DEFLATED
        bundle.writestr(info,content)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP CRC verification failed')
        assert len(archive.namelist()) == len(records) + 1
    digest = hashlib.file_digest(output.open('rb'),'sha256').hexdigest()
    return {'file':str(output),'files':len(records)+1,'bytes':output.stat().st_size,
            'sha256':digest,'user_source_archives':len(ARCHIVES),'crc':'PASS'}


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('output',type=Path)
    parser.add_argument('--source-dir',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(package(args.output,args.source_dir),indent=2))
