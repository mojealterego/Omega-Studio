#!/usr/bin/env bash
# Source build of a prefix-compatible aarch64 Termux runtime; no GitHub Actions.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: tools/build_custom_termux.sh --termux-ref <40-char SHA> --editor-prefix <dir> --work-dir <dir>

Requires: Linux x86_64, git, Docker daemon, network access, substantial disk space.
Builds Python, Git, llama-cpp and Node.js for /data/data/org.omega.actions/files/usr.
code-server must be compiled/installed for THE SAME prefix into --editor-prefix.
No binary is silently downloaded or replaced by a host build.
EOF
}

TERMUX_REF=''; EDITOR_PREFIX=''; WORK_DIR=''; PACKAGE='org.omega.actions'
while (( $# )); do
  case "$1" in
    --termux-ref) TERMUX_REF="${2:-}"; shift 2;;
    --editor-prefix) EDITOR_PREFIX="${2:-}"; shift 2;;
    --work-dir) WORK_DIR="${2:-}"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Invalid argument: $1" >&2; usage >&2; exit 2;;
  esac
done
[[ "$TERMUX_REF" =~ ^[a-fA-F0-9]{40}$ ]] || { echo 'BLOCKED: --termux-ref must be a pinned 40-character Git SHA' >&2; exit 2; }
[[ -d "$EDITOR_PREFIX" && -d "$WORK_DIR" ]] || { echo 'BLOCKED: --editor-prefix and --work-dir must exist' >&2; exit 2; }
for cmd in git docker python3; do command -v "$cmd" >/dev/null || { echo "BLOCKED: $cmd unavailable" >&2; exit 3; }; done
docker info >/dev/null 2>&1 || { echo 'BLOCKED: Docker daemon unavailable' >&2; exit 3; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="$(cd "$WORK_DIR" && pwd)"
EDITOR_PREFIX="$(cd "$EDITOR_PREFIX" && pwd)"
REPO="$WORK_DIR/termux-packages"
[[ ! -e "$REPO" ]] || { echo 'BLOCKED: work directory already contains termux-packages' >&2; exit 2; }
git clone --filter=blob:none https://github.com/termux/termux-packages.git "$REPO"
git -C "$REPO" checkout --detach "$TERMUX_REF"
ACTUAL="$(git -C "$REPO" rev-parse HEAD)"
[[ "$ACTUAL" == "$TERMUX_REF" ]] || { echo 'BLOCKED: checkout ref mismatch' >&2; exit 2; }
python3 - "$REPO/scripts/properties.sh" "$PACKAGE" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1]);source=p.read_text()
import re
pattern=re.compile(r'^(TERMUX_APP_PACKAGE|TERMUX_APP__PACKAGE_NAME)=(?:"com\.termux"|com\.termux)$',re.M)
match=list(pattern.finditer(source))
if len(match)!=1:raise SystemExit('BLOCKED: unexpected Termux properties format; inspect pinned revision')
p.write_text(source[:match[0].start()]+match[0].group(1)+'="'+sys.argv[2]+'"'+source[match[0].end():])
PY
# Build dependencies from source; NEVER reuse official com.termux apt packages.
# CLI options must match the pinned upstream revision; fail closed if they differ.
(
  cd "$REPO"
  ./scripts/run-docker.sh ./scripts/build-bootstraps.sh \
    --architectures aarch64 \
    --add python --add git --add llama-cpp --add nodejs
)
mapfile -t ARCHIVES < <(find "$REPO" -maxdepth 3 -type f -name 'bootstrap-aarch64*.zip' | sort)
if (( ${#ARCHIVES[@]} != 1 )); then
  printf 'BLOCKED: expected exactly one ARM64 bootstrap, found %s\n' "${#ARCHIVES[@]}" >&2
  exit 3
fi
python3 -m tools.assemble_runtime_from_bootstrap \
  --bootstrap "${ARCHIVES[0]}" \
  --editor-prefix "$EDITOR_PREFIX" \
  --assets "$ROOT/android/app/src/main/assets" \
  --package "$PACKAGE"
python3 -m tools.verify_runtime_bundle
printf 'READY FOR SDK BUILD: source SHA=%s; Android execution NOT verified\n' "$ACTUAL"
