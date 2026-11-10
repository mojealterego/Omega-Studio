#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/android/app/src/main/jniLibs/arm64-v8a/libomega_runtime.so"
CLANG="${OMEGA_ANDROID_CLANG:-clang}"
"$CLANG" --target=aarch64-linux-android26 -fPIC -O2 -fvisibility=hidden -fstack-protector-strong \
    -Werror -Wall -Wextra -shared -nostdlib -fuse-ld=lld \
    -Wl,-soname,libomega_runtime.so -Wl,-z,relro -Wl,-z,now -Wl,--no-undefined \
    -o "$OUT" "$ROOT/native/omega_runtime.c"
readelf -h "$OUT" | grep -q 'Machine:.*AArch64'
readelf -h "$OUT" | grep -q 'Type:.*DYN'
readelf -Ws "$OUT" | grep -q omega_gguf_version
sha256sum "$OUT"
