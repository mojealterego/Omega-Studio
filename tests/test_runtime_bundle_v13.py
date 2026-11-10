"""Runtime acceptance tests: fail-closed native assets, no false production claims."""
from __future__ import annotations
import hashlib
from pathlib import Path
import struct
import zipfile

import pytest

from tools.verify_runtime_bundle import RuntimeBundleError, inspect_runtime_bundle
from tools.prepare_runtime_release import prepare_runtime_release

PACKAGE='org.omega.actions'
PREFIX=f'/data/data/{PACKAGE}/files/usr'


def elf(machine=183, interpreter=b'/system/bin/linker64\0'):
    """Synthetic ELF with a real program-header table (not an executable program)."""
    phnum=2 if interpreter else 1
    data=bytearray(8192)
    data[:16]=b'\x7fELF'+bytes([2,1,1])+b'\0'*9
    struct.pack_into('<HHIQQQIHHHHHH',data,16,3,machine,1,0,64,0,0,64,56,phnum,0,0,0)
    struct.pack_into('<IIQQQQQQ',data,64,1,5,0,0,0,8192,8192,4096)
    if interpreter:
        struct.pack_into('<IIQQQQQQ',data,120,3,4,192,0,0,len(interpreter),len(interpreter),1)
        data[192:192+len(interpreter)]=interpreter
    return bytes(data)


def payload(*,include_node=True,include_editor=True):
    files={f'bin/{cmd}':elf() for cmd in ('bash','python3','git','llama-cli')}
    files['SYMLINKS.txt']='python3←bin/python\n'
    if include_node:files['bin/node']=elf()
    if include_editor:
        files['bin/code-server']=f'#!{PREFIX}/bin/bash\nexec "{PREFIX}/bin/node" "{PREFIX}/lib/node_modules/code-server/out/node/entry.js" "$@"\n'.encode()
        files['lib/node_modules/code-server/package.json']='{"name":"code-server"}'
    return files


def create(tmp_path, files=None, package=PACKAGE):
    assets=tmp_path/'assets';assets.mkdir(parents=True,exist_ok=True)
    z=assets/'bootstrap-aarch64-v8a.zip'
    with zipfile.ZipFile(z,'w') as archive:
        for name,content in (files if files is not None else payload()).items():
            archive.writestr(name,content)
    (assets/'bootstrap-aarch64-v8a.sha256').write_text(hashlib.sha256(z.read_bytes()).hexdigest()+'\n')
    (assets/'bootstrap-prefix.txt').write_text(f'/data/data/{package}/files/usr\n')
    return assets


def test_valid_complete_runtime_requires_physical_proof(tmp_path):
    result=inspect_runtime_bundle(create(tmp_path),PACKAGE)
    assert set(result['required_commands'])=={'bash','python','git','llama-cli','node','code-server'}
    assert result['editor_payload_detected'] is True
    assert result['execution_verified'] is False
    assert result['validation']=='STRUCTURAL_ONLY'


def test_missing_node_is_a_release_blocker(tmp_path):
    with pytest.raises(RuntimeBundleError,match='node'):
        inspect_runtime_bundle(create(tmp_path,payload(include_node=False)),PACKAGE)


def test_missing_code_server_is_a_release_blocker(tmp_path):
    with pytest.raises(RuntimeBundleError,match='code-server'):
        inspect_runtime_bundle(create(tmp_path,payload(include_editor=False)),PACKAGE)


def test_code_server_requires_real_assets(tmp_path):
    p=payload();del p['lib/node_modules/code-server/package.json']
    with pytest.raises(RuntimeBundleError,match='editor|code-server'):
        inspect_runtime_bundle(create(tmp_path,p),PACKAGE)


def test_linux_glibc_interpreter_rejected(tmp_path):
    p=payload();p['bin/git']=elf(interpreter=b'/lib/ld-linux-aarch64.so.1\0')
    with pytest.raises(RuntimeBundleError,match='linker|interpreter'):
        inspect_runtime_bundle(create(tmp_path,p),PACKAGE)


def test_truncated_elf_rejected(tmp_path):
    p=payload();p['bin/git']=elf()[:64]
    with pytest.raises(RuntimeBundleError,match='ELF|program header'):
        inspect_runtime_bundle(create(tmp_path,p),PACKAGE)


def test_script_outside_prefix_rejected(tmp_path):
    p=payload();p['bin/code-server']=b'#!/usr/bin/env node\necho nope\n'
    with pytest.raises(RuntimeBundleError,match='shebang|interpreter'):
        inspect_runtime_bundle(create(tmp_path,p),PACKAGE)


def test_zip_symlink_escape_rejected(tmp_path):
    p=payload();p['SYMLINKS.txt']='../../outside←bin/python\n'
    with pytest.raises(RuntimeBundleError,match='symlink|escape'):
        inspect_runtime_bundle(create(tmp_path,p),PACKAGE)


def test_zip_duplicate_rejected(tmp_path):
    assets=create(tmp_path)
    z=assets/'bootstrap-aarch64-v8a.zip'
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',UserWarning)
        with zipfile.ZipFile(z,'a') as archive:archive.writestr('bin/git',elf())
    (assets/'bootstrap-aarch64-v8a.sha256').write_text(hashlib.sha256(z.read_bytes()).hexdigest())
    with pytest.raises(RuntimeBundleError,match='Duplicate'):
        inspect_runtime_bundle(assets,PACKAGE)


def test_prepare_release_is_atomic_and_produces_manifest(tmp_path):
    src=create(tmp_path)
    target=tmp_path/'app-assets'
    result=prepare_runtime_release(src/'bootstrap-aarch64-v8a.zip',src/'bootstrap-prefix.txt',target,PACKAGE)
    assert result['execution_verified'] is False
    assert (target/'runtime-integrity.json').is_file()
    assert (target/'bootstrap-aarch64-v8a.sha256').read_text().strip()==result['bootstrap_sha256']
    assert inspect_runtime_bundle(target,PACKAGE)['verified_sha256'] is True


def test_prepare_release_does_not_publish_invalid_bundle(tmp_path):
    src=create(tmp_path,payload(include_editor=False))
    target=tmp_path/'app-assets'
    with pytest.raises(RuntimeBundleError):
        prepare_runtime_release(src/'bootstrap-aarch64-v8a.zip',src/'bootstrap-prefix.txt',target,PACKAGE)
    assert not target.exists()


def test_rejects_small_fake_elf_with_valid_header(tmp_path):
    p=payload();p['bin/git']=elf()[:256]
    with pytest.raises(RuntimeBundleError,match='ELF'):
        inspect_runtime_bundle(create(tmp_path,p),PACKAGE)


def test_rejects_non_pie_arm64_binary(tmp_path):
    p=payload();bad=bytearray(elf());struct.pack_into('<H',bad,16,2);p['bin/git']=bytes(bad)
    with pytest.raises(RuntimeBundleError,match='PIE|type'):
        inspect_runtime_bundle(create(tmp_path,p),PACKAGE)


def test_rejects_non_executable_pt_load(tmp_path):
    p=payload();bad=bytearray(elf());struct.pack_into('<I',bad,68,4);p['bin/git']=bytes(bad)
    with pytest.raises(RuntimeBundleError,match='executable|loadable'):
        inspect_runtime_bundle(create(tmp_path,p),PACKAGE)
