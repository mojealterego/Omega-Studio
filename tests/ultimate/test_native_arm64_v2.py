"""Native artifact tests: cross-compilation is not Android device execution."""
from __future__ import annotations
import ctypes
from pathlib import Path
import shutil
import subprocess
import zlib
import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(not shutil.which('clang') or not shutil.which('readelf'), reason='cross compiler unavailable')
def test_cross_compiled_arm64_elf_and_native_crc(tmp_path):
    from tools.build_native_arm64 import build
    result = build(tmp_path / 'libomega_runtime.so')
    assert result['elf_class'] == 64
    assert result['machine'] == 183
    assert result['abi_version'] == 2
    assert result['sha256']
    host = tmp_path / 'libhost.so'
    subprocess.run(['clang', '-fPIC', '-shared', '-O2', '-o', str(host),
                    str(ROOT / 'android/native/omega_runtime.c')], check=True, timeout=30)
    lib = ctypes.CDLL(str(host))
    lib.omega_crc32.argtypes = [ctypes.POINTER(ctypes.c_ubyte), ctypes.c_size_t]
    lib.omega_crc32.restype = ctypes.c_uint32
    data = b'GGUF-data'
    ptr = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    assert lib.omega_crc32(ptr, len(data)) == zlib.crc32(data)
    lib.omega_is_gguf_header.argtypes = [ctypes.POINTER(ctypes.c_ubyte), ctypes.c_size_t]
    assert lib.omega_is_gguf_header(ptr, len(data)) == 1
    assert lib.omega_is_gguf_header(ptr, 3) == 0
