#!/usr/bin/env bash
# Signed Android release requires real native assets, physical debug smoke and private signing keys.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python3 tools/prepare_android_assets.py
python3 tools/verify_runtime_bundle.py
for var in OMEGA_KEYSTORE OMEGA_KEYSTORE_PASSWORD OMEGA_KEY_ALIAS OMEGA_KEY_PASSWORD; do
  if [[ -z "${!var:-}" ]]; then echo "BLOCKED: missing signing variable $var" >&2; exit 3; fi
done
if [[ ! -f "$OMEGA_KEYSTORE" ]];then echo 'BLOCKED: signing keystore file missing' >&2;exit 3;fi
if [[ -z "${ANDROID_HOME:-}${ANDROID_SDK_ROOT:-}" ]];then echo 'BLOCKED: Android SDK missing' >&2;exit 3;fi
if ! command -v apksigner >/dev/null 2>&1;then echo 'BLOCKED: apksigner missing' >&2;exit 3;fi
if [[ -x android/gradlew ]];then BUILD=(./gradlew);elif command -v gradle >/dev/null 2>&1;then BUILD=(gradle);else
  echo 'BLOCKED: Gradle missing' >&2;exit 3
fi
# Separate physical debug execution gate; this step must not be skipped.
bash tools/build_full_apk.sh
(cd android && "${BUILD[@]}" --no-daemon assembleRelease)
APK="$ROOT/android/app/build/outputs/apk/release/app-release.apk"
if [[ ! -s "$APK" ]];then echo 'BLOCKED: signed release APK missing' >&2;exit 3;fi
apksigner verify --verbose --print-certs "$APK"
mkdir -p "$ROOT/dist"
cp "$APK" "$ROOT/dist/OMEGA_STUDIO_v1.3.0_SIGNED_RELEASE_DEVICE_TEST_PENDING.apk"
sha256sum "$ROOT/dist/OMEGA_STUDIO_v1.3.0_SIGNED_RELEASE_DEVICE_TEST_PENDING.apk"
echo 'SIGNED_RELEASE_BUILT: physical smoke passed for debug build; release APK still requires device-specific acceptance.'
