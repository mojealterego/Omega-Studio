"""TDD: executable source-tree packer for a package-specific Android runtime."""
import hashlib
import os
import struct
import zipfile
from pathlib import Path
import pytest

from tools.runtime_supply_chain import package_prefix, validate_elf, RuntimePackagingError
from tools.verify_runtime_bundle import inspect_runtime_bundle, RuntimeBundleError

PREFIX='/data/data/org.omega.actions/files/usr'


def elf_arm64(*, machine=183, e_type=3, with_load=True):
    data=bytearray(8192)
    data[:4]=b'\x7fELF'; data[4]=2; data[5]=1; data[6]=1
    struct.pack_into('<HHIQQQIHHHHHH',data,16,e_type,machine,1,0x1000,64,0,0,64,56,1,0,0,0)
    if with_load:
        struct.pack_into('<IIQQQQQQ',data,64,1,5,0,0,0,8192,8192,4096)
    data[4096:4100]=b'\x1f\x20\x03\xd5'  # AArch64 NOP
    return bytes(data)


def source_tree(tmp_path):
    root=tmp_path/'prefix'; (root/'bin').mkdir(parents=True)
    for name in ('bash','python','git','llama-cli','node'):
        (root/'bin'/name).write_bytes(elf_arm64()); (root/'bin'/name).chmod(0o755)
    (root/'bin'/'code-server').write_text(f'#!{PREFIX}/bin/sh\nexec "{PREFIX}/bin/node" "{PREFIX}/share/code-server/main.js" "$@"\n')
    (root/'bin'/'code-server').chmod(0o755)
    (root/'bin'/'sh').symlink_to('bash')
    (root/'share/code-server').mkdir(parents=True)
    (root/'share/code-server/main.js').write_text('console.log("code-server")\n')
    return root


def test_rejects_truncated_elf():
    with pytest.raises(RuntimePackagingError,match='ELF'):
        validate_elf(b'\x7fELF'+b'\0'*60,'bin/bash')


def test_rejects_wrong_machine():
    with pytest.raises(RuntimePackagingError,match='AArch64'):
        validate_elf(elf_arm64(machine=62),'bin/git')


def test_rejects_non_executable_elf():
    with pytest.raises(RuntimePackagingError,match='PT_LOAD'):
        validate_elf(elf_arm64(with_load=False),'bin/python')


def test_rejects_non_pie_elf():
    with pytest.raises(RuntimePackagingError,match='PIE'):
        validate_elf(elf_arm64(e_type=2),'bin/llama-cli')


def test_packages_all_runtime_commands_and_vscode(tmp_path):
    root=source_tree(tmp_path);assets=tmp_path/'assets'
    manifest=package_prefix(root,assets,package_name='org.omega.actions')
    assert manifest['commands']==['bash','python','git','llama-cli','node','code-server']
    assert manifest['execution_verified'] is False
    with zipfile.ZipFile(assets/'bootstrap-aarch64-v8a.zip') as z:
        assert 'bin/code-server' in z.namelist()
        assert 'share/code-server/main.js' in z.namelist()
        assert 'bin/sh' not in z.namelist()
        assert 'bash←bin/sh' in z.read('SYMLINKS.txt').decode()
    assert inspect_runtime_bundle(assets,'org.omega.actions')['required_commands']==manifest['commands']
    assert hashlib.sha256((assets/'bootstrap-aarch64-v8a.zip').read_bytes()).hexdigest()==(assets/'bootstrap-aarch64-v8a.sha256').read_text().strip()


def test_rejects_missing_code_server(tmp_path):
    root=source_tree(tmp_path);(root/'bin/code-server').unlink()
    with pytest.raises(RuntimePackagingError,match='code-server'):
        package_prefix(root,tmp_path/'assets',package_name='org.omega.actions')


def test_rejects_symlink_escape(tmp_path):
    root=source_tree(tmp_path);(root/'bin/sh').unlink();(root/'bin/sh').symlink_to('/system/bin/sh')
    with pytest.raises(RuntimePackagingError,match='symlink'):
        package_prefix(root,tmp_path/'assets',package_name='org.omega.actions')


def test_rejects_wrong_shebang_prefix(tmp_path):
    root=source_tree(tmp_path)
    (root/'bin/code-server').write_text('#!/data/data/com.termux/files/usr/bin/bash\n')
    with pytest.raises(RuntimePackagingError,match='shebang'):
        package_prefix(root,tmp_path/'assets',package_name='org.omega.actions')


def test_rejects_broken_symlink(tmp_path):
    root=source_tree(tmp_path);(root/'bin/sh').unlink();(root/'bin/sh').symlink_to('not-found')
    with pytest.raises(RuntimePackagingError,match='symlink'):
        package_prefix(root,tmp_path/'assets',package_name='org.omega.actions')


def test_release_gate_rejects_synthetic_64_byte_binaries(tmp_path):
    assets=tmp_path/'assets';assets.mkdir()
    with zipfile.ZipFile(assets/'bootstrap-aarch64-v8a.zip','w') as z:
        for name in ('bash','python','git','llama-cli','node'):
            elf=bytearray(64);elf[:4]=b'\x7fELF';elf[4]=2;elf[5]=1;struct.pack_into('<H',elf,18,183)
            z.writestr('bin/'+name,elf)
        z.writestr('bin/code-server',f'#!{PREFIX}/bin/sh\n')
        z.writestr('share/code-server/main.js',b'hello')
        z.writestr('SYMLINKS.txt',b'')
    (assets/'bootstrap-aarch64-v8a.sha256').write_text(hashlib.sha256((assets/'bootstrap-aarch64-v8a.zip').read_bytes()).hexdigest())
    (assets/'bootstrap-prefix.txt').write_text(PREFIX)
    with pytest.raises(RuntimeBundleError,match='ELF'):
        inspect_runtime_bundle(assets,'org.omega.actions')
