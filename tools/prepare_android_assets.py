"""Create a deterministic, offline source-code payload for an Android runtime.

The payload does not contain a Python interpreter or third-party native wheels.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import zipfile


def package_backend(source:Path, assets:Path)->dict:
    source=Path(source).resolve();assets=Path(assets).resolve()
    if not (source/'omega_actions/__main__.py').is_file():raise ValueError('Invalid backend source tree')
    assets.mkdir(parents=True,exist_ok=True)
    target=assets/'omega-backend.zip'
    entries=sorted(p for p in (source/'omega_actions').rglob('*') if p.is_file() and
                   not p.name.endswith('.pyc') and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts)
    entries += [source/'pyproject.toml']
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for p in entries:
            name=p.relative_to(source).as_posix()
            info=zipfile.ZipInfo(name,date_time=(2020,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o644<<16
            archive.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    (assets/'omega-backend.sha256').write_text(digest+'\n',encoding='ascii')
    return {'sha256':digest,'files':len(entries),'bytes':target.stat().st_size}


if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    print(package_backend(root/'backend',root/'android/app/src/main/assets'))
