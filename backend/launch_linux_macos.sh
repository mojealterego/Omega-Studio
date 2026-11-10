#!/bin/sh
set -eu
cd "$(dirname "$0")"
PYTHON="${PYTHON:-python3}"
exec "$PYTHON" -m omega_actions serve "$@"
