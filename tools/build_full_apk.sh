#!/usr/bin/env bash
# Production-readiness gate: no empty APK, no fake Termux, no synthetic device proof.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python3 tools/prepare_android_assets.py
python3 tools/verify_runtime_bundle.py
if [[ -z "${ANDROID_HOME:-}${ANDROID_SDK_ROOT:-}" ]]; then
  echo 'BLOCKED: Android SDK not available' >&2; exit 3
fi
if [[ -x android/gradlew ]]; then BUILD=(./gradlew);elif command -v gradle >/dev/null 2>&1;then BUILD=(gradle);else
  echo 'BLOCKED: Gradle not available' >&2;exit 3
fi
(cd android && "${BUILD[@]}" --no-daemon assembleDebug)
APK="$ROOT/android/app/build/outputs/apk/debug/app-debug.apk"
if [[ ! -s "$APK" ]];then echo 'BLOCKED: APK not produced' >&2;exit 3;fi
if ! command -v apksigner >/dev/null 2>&1;then echo 'BLOCKED: apksigner unavailable' >&2;exit 3;fi
apksigner verify --verbose "$APK"
"$ROOT/tools/android_device_smoke.sh" "$APK"
mkdir -p "$ROOT/dist"
cp "$APK" "$ROOT/dist/OMEGA_STUDIO_v1.3.0_ARM64_DEVICE_VERIFIED_DEBUG.apk"
sha256sum "$ROOT/dist/OMEGA_STUDIO_v1.3.0_ARM64_DEVICE_VERIFIED_DEBUG.apk"
echo 'DEBUG APK passed structural and physical ARM64 checks; production signing/release still separate.'
