"""Exercise the same C sources on the host; Android ARM64 execution remains separate."""
from __future__ import annotations
import ctypes
from pathlib import Path
import shutil
import subprocess
import tempfile
import pytest


def test_native_gguf_header_utf8_and_hash_on_host():
    compiler = shutil.which('clang')
    if not compiler:
        pytest.fail('clang is required for native host verification')
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix='omega-native-host-') as d:
        binary = Path(d)/'libomega_test.so'
        subprocess.run([compiler,'-shared','-fPIC','-O2','-Wall','-Wextra','-Werror',
                        '-o',str(binary),str(root/'native/omega_runtime.c')],check=True)
        library = ctypes.CDLL(str(binary))
        library.omega_gguf_version.argtypes=[ctypes.c_char_p,ctypes.c_size_t]
        library.omega_gguf_version.restype=ctypes.c_int
        assert library.omega_gguf_version(b'GGUF\x03\x00\x00\x00',8) == 3
        assert library.omega_gguf_version(b'GGUF\x02\x00\x00\x00',8) == 2
        assert library.omega_gguf_version(b'GGUF\x01\x00\x00\x00',8) == -3
        assert library.omega_gguf_version(b'NOPE\x03\x00\x00\x00',8) == -2
        assert library.omega_gguf_version(b'GGUF',4) == -1
        library.omega_utf8_valid.argtypes=[ctypes.c_char_p,ctypes.c_size_t]
        library.omega_utf8_valid.restype=ctypes.c_int
        assert library.omega_utf8_valid('żółw'.encode(),len('żółw'.encode())) == 1
        assert library.omega_utf8_valid(b'\xc0\xaf',2) == 0
        assert library.omega_utf8_valid(b'\xed\xa0\x80',3) == 0
        assert library.omega_utf8_valid(b'\xf4\x90\x80\x80',4) == 0
        library.omega_fnv1a64.argtypes=[ctypes.c_char_p,ctypes.c_size_t]
        library.omega_fnv1a64.restype=ctypes.c_uint64
        assert library.omega_fnv1a64(b'hello',5) == 0xa430d84680aabd0b
        assert library.Java_org_omega_actions_core_OmegaNative_abiVersion(None,None) == 2
