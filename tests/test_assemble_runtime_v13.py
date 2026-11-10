"""Cross-build import must be offline, deterministic and reject hostile archives."""
import hashlib
from pathlib import Path
import zipfile
import pytest
from tools.assemble_runtime_from_bootstrap import unpack_bootstrap, RuntimeImportError


def make_zip(tmp_path, entries):
    p=tmp_path/'bootstrap.zip'
    with zipfile.ZipFile(p,'w') as z:
        for name,data in entries.items():z.writestr(name,data)
    return p


def test_import_preserves_files_and_internal_symlinks(tmp_path):
    archive=make_zip(tmp_path,{'bin/bash':b'binary','SYMLINKS.txt':'bash←bin/sh\n'})
    root=tmp_path/'prefix'
    unpack_bootstrap(archive,root,package_name='org.omega.actions')
    assert (root/'bin/bash').read_bytes()==b'binary'
    assert (root/'bin/sh').is_symlink()
    assert (root/'bin/sh').resolve()==(root/'bin/bash').resolve()


def test_import_rewrites_absolute_matching_prefix_to_relative(tmp_path):
    archive=make_zip(tmp_path,{'bin/bash':b'binary','SYMLINKS.txt':'/data/data/org.omega.actions/files/usr/bin/bash←bin/sh\n'})
    root=tmp_path/'prefix'
    unpack_bootstrap(archive,root,package_name='org.omega.actions')
    assert (root/'bin/sh').is_symlink()
    assert (root/'bin/sh').resolve()==(root/'bin/bash').resolve()


def test_import_rejects_zip_slip(tmp_path):
    archive=make_zip(tmp_path,{'../escape':b'x','SYMLINKS.txt':''})
    with pytest.raises(RuntimeImportError,match='path'):
        unpack_bootstrap(archive,tmp_path/'prefix',package_name='org.omega.actions')
    assert not (tmp_path/'escape').exists()


def test_import_rejects_external_symlink(tmp_path):
    archive=make_zip(tmp_path,{'bin/bash':b'binary','SYMLINKS.txt':'/system/bin/sh←bin/sh\n'})
    with pytest.raises(RuntimeImportError,match='symlink'):
        unpack_bootstrap(archive,tmp_path/'prefix',package_name='org.omega.actions')


def test_import_rejects_symlink_over_existing_file(tmp_path):
    archive=make_zip(tmp_path,{'bin/bash':b'binary','SYMLINKS.txt':'bash←bin/bash\n'})
    with pytest.raises(RuntimeImportError,match='collision'):
        unpack_bootstrap(archive,tmp_path/'prefix',package_name='org.omega.actions')


def test_import_rejects_duplicate_entries(tmp_path):
    archive=tmp_path/'bootstrap.zip'
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('bin/bash',b'1');z.writestr('bin/bash',b'2');z.writestr('SYMLINKS.txt',b'')
    with pytest.raises(RuntimeImportError,match='duplicate'):
        unpack_bootstrap(archive,tmp_path/'prefix',package_name='org.omega.actions')
