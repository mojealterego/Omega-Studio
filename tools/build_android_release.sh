#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python3 tools/prepare_android_assets.py
python3 tools/verify_runtime_bundle.py
if ! command -v gradle >/dev/null 2>&1; then
  printf '%s\n' 'BUILD BLOCKED: Android Gradle/SDK toolchain is not installed.' >&2
  exit 3
fi
if [[ -z "${ANDROID_HOME:-}${ANDROID_SDK_ROOT:-}" ]]; then
  printf '%s\n' 'BUILD BLOCKED: ANDROID_HOME or ANDROID_SDK_ROOT is required.' >&2
  exit 3
fi
cd android
gradle --offline --no-daemon assembleDebug
printf '%s\n' 'APK assembled with the structurally verified bundled runtime.'
