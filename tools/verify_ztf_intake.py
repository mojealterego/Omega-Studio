#!/usr/bin/env python3
"""Read-only OMEGA-ZTF-003 candidate intake.

Exit code 0: physical artifact integrity verified; NOT authorization to release.
Exit code 2: provenance, contract, or artifact blocked.
Exit code 1: invalid input/usage.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / 'backend'))

from omega_actions.ultimate.ztf_admission import AdmissionError, admit_manifest  # noqa: E402


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    out: dict[str, object] = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f'Duplicate JSON key: {k}')
        out[k] = v
    return out


def _reject_nonfinite(s: str) -> None:
    raise ValueError(f'Non-finite JSON number: {s}')


def _read_bounded_object(path: Path, max_bytes: int = 2 * 1024 * 1024) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'Invalid/untrusted JSON input file: {path}')
    if path.stat().st_size > max_bytes:
        raise ValueError(f'JSON input too large: {path}')
    with path.open('rb') as f:
        raw = f.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError(f'JSON input too large: {path}')
    val = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_pairs,
                     parse_constant=_reject_nonfinite)
    if not isinstance(val, dict):
        raise ValueError(f'Expected JSON object: {path}')
    return val


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='OMEGA-ZTF-003 physical checkpoint admission, no model load')
    ap.add_argument('--manifest', type=Path, required=True)
    ap.add_argument('--artifacts-root', type=Path, required=True)
    ap.add_argument('--artifact-map', type=Path, required=True,
                    help='JSON: base, contributor:<source_id>, candidate => relative filenames')
    args = ap.parse_args(argv)
    try:
        manifest = _read_bounded_object(args.manifest)
        artifact_map = _read_bounded_object(args.artifact_map)
        report = admit_manifest(manifest, args.artifacts_root, artifact_map)
        print(json.dumps(report.as_dict(), ensure_ascii=False, sort_keys=True, indent=2))
        return 0 if report.artifact_integrity_verified else 2
    except (AdmissionError, ValueError, OSError, UnicodeDecodeError) as exc:
        print(json.dumps({'error': 'INVALID_ADMISSION_INPUT', 'detail': str(exc)}, ensure_ascii=False),
              file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
