#!/usr/bin/env bash
# Production-only Android build. Missing native runtime or signing keys = BLOCKED.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python3 tools/prepare_android_assets.py
python3 tools/verify_runtime_bundle.py
for key in OMEGA_KEYSTORE OMEGA_KEYSTORE_PASSWORD OMEGA_KEY_ALIAS OMEGA_KEY_PASSWORD; do
  if [[ -z "${!key:-}" ]]; then
    printf 'BLOCKED: %s is required for signed release\n' "$key" >&2
    exit 3
  fi
done
[[ -f "$OMEGA_KEYSTORE" ]] || { echo 'BLOCKED: keystore file missing' >&2; exit 3; }
SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
[[ -d "$SDK" ]] || { echo 'BLOCKED: Android SDK unavailable' >&2; exit 3; }
if [[ -x "$ROOT/android/gradlew" ]]; then
  GRADLE=("$ROOT/android/gradlew")
elif command -v gradle >/dev/null 2>&1; then
  GRADLE=(gradle)
else
  echo 'BLOCKED: Gradle and Android Gradle wrapper unavailable' >&2
  exit 3
fi
APKSIGNER="$(find "$SDK/build-tools" -maxdepth 2 -type f -name apksigner 2>/dev/null | sort -V | tail -1)"
[[ -x "$APKSIGNER" ]] || { echo 'BLOCKED: apksigner missing in Android SDK build-tools' >&2; exit 3; }
cd android
"${GRADLE[@]}" --no-daemon assembleRelease
APK='app/build/outputs/apk/release/app-release.apk'
[[ -s "$APK" ]] || { echo 'BLOCKED: no signed release APK was produced' >&2; exit 3; }
"$APKSIGNER" verify --verbose "$APK"
python3 - "$APK" <<'PY'
import sys,zipfile
p=sys.argv[1]
with zipfile.ZipFile(p) as z:
    required=('assets/bootstrap-aarch64-v8a.zip','assets/bootstrap-aarch64-v8a.sha256','assets/bootstrap-prefix.txt')
    missing=[name for name in required if name not in z.namelist()]
    if missing:raise SystemExit('BLOCKED: runtime assets absent from APK: '+','.join(missing))
    if z.testzip() is not None:raise SystemExit('BLOCKED: APK ZIP CRC failed')
print('SIGNED APK STRUCTURE: PASS (on-device execution still requires device test)')
PY
printf 'SIGNED RELEASE APK: %s\n' "$ROOT/android/$APK"
