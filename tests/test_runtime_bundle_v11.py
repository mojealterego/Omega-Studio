"""Structural runtime checks never imply executable proof on Android hardware."""
import hashlib
from pathlib import Path
import struct
import zipfile
import pytest
from tools.verify_runtime_bundle import inspect_runtime_bundle, RuntimeBundleError
from tests.test_runtime_supply_chain_v13 import elf_arm64


def synthetic_elf(machine=183):
    return elf_arm64(machine=machine)


def make_bundle(tmp_path, files=None, prefix='org.omega.actions', machine=183):
    assets=tmp_path/'assets';assets.mkdir()
    archive=assets/'bootstrap-aarch64-v8a.zip'
    content=files or {f'bin/{name}':synthetic_elf(machine) for name in ('bash','python','git','llama-cli','node')}
    content.setdefault('bin/code-server',b'#!/data/data/org.omega.actions/files/usr/bin/bash\n')
    content.setdefault('share/code-server/main.js',b'console.log(42)\n')
    content.setdefault('SYMLINKS.txt','lib/libpython.so←lib/libpython-omega.so\n')
    content.setdefault('lib/libpython.so',synthetic_elf(machine))
    with zipfile.ZipFile(archive,'w') as z:
        for name,data in content.items():z.writestr(name,data)
    (assets/'bootstrap-aarch64-v8a.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'\n')
    (assets/'bootstrap-prefix.txt').write_text(f'/data/data/{prefix}/files/usr\n')
    return assets


def test_missing_runtime_bundle_fails_closed(tmp_path):
    with pytest.raises(RuntimeBundleError,match='bootstrap'):
        inspect_runtime_bundle(tmp_path,'org.omega.actions')


def test_valid_arm64_structural_bundle(tmp_path):
    assets=make_bundle(tmp_path)
    result=inspect_runtime_bundle(assets,'org.omega.actions')
    assert result['abi']=='arm64-v8a'
    assert result['required_commands']==['bash','python','git','llama-cli','node','code-server']
    assert result['verified_sha256'] is True
    assert result['execution_verified'] is False


def test_rejects_mismatched_package_prefix(tmp_path):
    assets=make_bundle(tmp_path,prefix='com.termux')
    with pytest.raises(RuntimeBundleError,match='prefix'):
        inspect_runtime_bundle(assets,'org.omega.actions')


def test_rejects_wrong_architecture(tmp_path):
    assets=make_bundle(tmp_path,machine=62)
    with pytest.raises(RuntimeBundleError,match='AArch64'):
        inspect_runtime_bundle(assets,'org.omega.actions')


def test_rejects_zip_slip(tmp_path):
    assets=make_bundle(tmp_path)
    archive=assets/'bootstrap-aarch64-v8a.zip'
    with zipfile.ZipFile(archive,'a') as z:z.writestr('../bad',b'payload')
    (assets/'bootstrap-aarch64-v8a.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest())
    with pytest.raises(RuntimeBundleError,match='path'):
        inspect_runtime_bundle(assets,'org.omega.actions')


def test_rejects_digest_mismatch(tmp_path):
    assets=make_bundle(tmp_path)
    (assets/'bootstrap-aarch64-v8a.sha256').write_text('0'*64)
    with pytest.raises(RuntimeBundleError,match='SHA-256'):
        inspect_runtime_bundle(assets,'org.omega.actions')


def test_rejects_missing_llama_binary(tmp_path):
    files={f'bin/{name}':synthetic_elf() for name in ('bash','python','git')}
    assets=make_bundle(tmp_path,files=files)
    with pytest.raises(RuntimeBundleError,match='llama-cli'):
        inspect_runtime_bundle(assets,'org.omega.actions')
