#!/usr/bin/env bash
# Debug APK smoke test on an actual ARM64 phone, never an emulator or host simulation.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APK="${1:-$ROOT/android/app/build/outputs/apk/debug/app-debug.apk}"
PKG=org.omega.actions
if [[ ! -f "$APK" ]]; then echo 'BLOCKED: APK missing' >&2; exit 3; fi
if ! command -v adb >/dev/null 2>&1; then echo 'BLOCKED: adb missing' >&2; exit 3; fi
mapfile -t DEVICES < <(adb devices | awk 'NR>1 && $2=="device" {print $1}')
if [[ ${#DEVICES[@]} -ne 1 ]]; then echo 'BLOCKED: exactly one authorized device required' >&2; exit 3; fi
SERIAL="${DEVICES[0]}"
ADB=(adb -s "$SERIAL")
ABI="$("${ADB[@]}" shell getprop ro.product.cpu.abi | tr -d '\r')"
QEMU="$("${ADB[@]}" shell getprop ro.kernel.qemu | tr -d '\r')"
if [[ "$ABI" != 'arm64-v8a' || "$QEMU" == 1 ]]; then
  echo 'BLOCKED: physical arm64-v8a Android device required' >&2; exit 3
fi
"${ADB[@]}" install -r "$APK" >/dev/null
"${ADB[@]}" shell am start -n "$PKG/.MainActivity" >/dev/null
PREFIX="/data/data/$PKG/files/usr"
# The UI performs first-run installation when a verified runtime is bundled.
READY=0
for _ in $(seq 1 120); do
  if "${ADB[@]}" shell run-as "$PKG" sh -c "test -x $PREFIX/bin/bash" >/dev/null 2>&1; then READY=1; break; fi
  sleep 1
done
if [[ "$READY" != 1 ]]; then echo 'BLOCKED: runtime not installed or not executable after 120s' >&2; exit 4; fi
for CMD in bash python git llama-cli node code-server; do
  if ! "${ADB[@]}" shell run-as "$PKG" "$PREFIX/bin/$CMD" --version >/dev/null 2>&1; then
    echo "BLOCKED: ARM64 binary failed on device: $CMD" >&2; exit 4
  fi
  echo "DEVICE PASS: $CMD"
done
# Execute real code, not only version switches.
"${ADB[@]}" shell run-as "$PKG" "$PREFIX/bin/bash" -c 'printf OMEGA_BASH_OK' | grep -q 'OMEGA_BASH_OK' || {
  echo 'BLOCKED: Bash failed to execute a command' >&2;exit 4;
}
"${ADB[@]}" shell run-as "$PKG" "$PREFIX/bin/python" -c 'import json,sqlite3,ssl; print("OMEGA_PYTHON_OK")' | grep -q 'OMEGA_PYTHON_OK' || {
  echo 'BLOCKED: Python standard library is incomplete' >&2;exit 4;
}
"${ADB[@]}" shell run-as "$PKG" "$PREFIX/bin/node" -e 'console.log("OMEGA_NODE_OK")' | grep -q 'OMEGA_NODE_OK' || {
  echo 'BLOCKED: Node.js execution failed' >&2;exit 4;
}
printf 'DEVICE_SMOKE_PASS: six commands executed on physical arm64-v8a device\n'
