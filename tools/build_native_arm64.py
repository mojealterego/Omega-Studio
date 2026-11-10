"""Cross-compile the small, real AArch64 OMEGA ABI library without Android SDK.

The output is a native ELF, NOT a Termux/Python/Git/llama.cpp distribution.
Device execution requires a separate test on an ARM64 Android target.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def build(output: Path) -> dict:
    compiler = shutil.which('clang')
    if not compiler:
        raise RuntimeError('clang not installed')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [compiler, '--target=aarch64-linux-android26', '-fuse-ld=lld',
           '-fPIC', '-shared', '-nostdlib', '-O2', '-ffreestanding',
           '-ffile-prefix-map=' + str(ROOT) + '=.',
           '-Wl,-soname,libomega_runtime.so', '-Wl,--build-id=none',
           '-Wl,--no-undefined', '-Wl,-z,relro,-z,now',
           '-o', str(output), str(ROOT / 'android/native/omega_runtime.c')]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError('Native cross compiler failed') from exc
    if result.returncode:
        raise RuntimeError('Native cross compiler failed: ' + result.stderr[-1500:])
    data = output.read_bytes()
    if len(data) < 64 or data[:4] != b'\x7fELF' or data[4] != 2 or data[5] != 1:
        raise RuntimeError('Not an ELF64 little-endian binary')
    machine = struct.unpack_from('<H', data, 18)[0]
    if machine != 183:
        raise RuntimeError('Not an AArch64 binary')
    return {'path': str(output), 'elf_class': 64, 'machine': machine,
            'abi_version': 2, 'sha256': hashlib.sha256(data).hexdigest(),
            'size_bytes': len(data), 'device_execution_verified': False,
            'scope': 'freestanding-native-integrity-primitives'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    import json
    print(json.dumps(build(args.output), indent=2))
