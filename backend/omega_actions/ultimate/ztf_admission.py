"""OMEGA-ZTF-003: fail-closed, read-only intake of candidate model artifacts.

This module reuses Omega Studio's existing bounded safetensors validator.
It does NOT load models, train, fuse, decide licensing, verify neural inference,
certify a Lean proof, or authorize a release. Operator-supplied SHA-256 values
must match *physical file bytes* before integrity is reported.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .safetensors_guard import SafetensorsValidationError, inspect_safetensors

_HASH = re.compile(r"[0-9a-f]{64}\Z")
_SOURCE = re.compile(r"[A-Za-z0-9._-]{2,128}\Z")
_FUSION_LEVELS = frozenset({'L0','L1','L2','L3','L4'})
_SELF_ASSERTED_LEVELS = frozenset({'HOST_TESTED','DEVICE_TESTED','DEPLOYED','PRODUCTION_VERIFIED'})


class AdmissionError(ValueError):
    """Malformed input contract (separate from an ordinary blocked admission)."""


@dataclass(frozen=True, slots=True)
class AdmissionReport:
    model_id: str
    declared_fusion_level: str
    status: str
    artifact_integrity_verified: bool
    verified_artifacts: tuple[str, ...]
    blockers: tuple[str, ...]
    release_authorized: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            'model_id': self.model_id,
            'declared_fusion_level': self.declared_fusion_level,
            'status': self.status,
            'artifact_integrity_verified': self.artifact_integrity_verified,
            'verified_artifacts': list(self.verified_artifacts),
            'blockers': list(self.blockers),
            'release_authorized': self.release_authorized,
            'verification_scope': 'PHYSICAL_SAFETENSORS_INTEGRITY_ONLY',
        }


def _as_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AdmissionError(f'{label} must be an object')
    return value


def _hash(value: Any) -> bool:
    return isinstance(value, str) and _HASH.fullmatch(value) is not None


def _file_in_workspace(root: Path, filename: Any) -> Path:
    if not isinstance(filename, str) or not filename or '\\' in filename:
        raise ValueError('Artifact path must be a relative POSIX string')
    rel = PurePosixPath(filename)
    if rel.is_absolute() or any(part in ('..', '.') for part in filename.split('/')):
        raise ValueError('Absolute paths, dot components and traversal are forbidden')
    if not rel.parts or any(part == '' for part in filename.split('/')):
        raise ValueError('Empty path components are forbidden')
    candidate = root
    for segment in rel.parts:
        candidate = candidate / segment
        if candidate.is_symlink():
            raise ValueError('Symlink paths are forbidden, including parent components')
    # .resolve() is only a secondary containment check: original components are
    # checked for symlinks above and safetensors_guard uses O_NOFOLLOW + fstat.
    if not candidate.resolve(strict=False).is_relative_to(root):
        raise ValueError('Artifact path escapes the workspace')
    return candidate


def admit_manifest(
    manifest: Mapping[str, Any],
    artifacts_root: Path,
    artifact_paths: Mapping[str, str],
) -> AdmissionReport:
    """Review actual, unmodified SafeTensors and quarantine unsupported model claims.

    artifact_paths is supplied *out of band* by the operator. Keys: ``base``,
    ``contributor:<source_id>``, ``candidate``. Absence is a blocker, not proof
    that a fictional 64-hex string represents a real checkpoint.

    Positive source integrity is intentionally NOT an L2/L3/L4 model/E2E claim.
    Promotion requires a separate trusted verifier and owner approval.
    """
    if not isinstance(manifest, Mapping):
        raise AdmissionError('Manifest must be an object')
    if manifest.get('schema') != 'omega.unified_model_manifest.v2':
        raise AdmissionError('Unsupported model schema')
    level = manifest.get('fusion_level')
    if level not in _FUSION_LEVELS:
        raise AdmissionError('Invalid fusion_level')
    model_id = manifest.get('model_id')
    if not isinstance(model_id, str) or not _SOURCE.fullmatch(model_id):
        raise AdmissionError('Invalid model_id')

    base = _as_dict(manifest.get('base'), 'base')
    fusion = _as_dict(manifest.get('fusion_recipe'), 'fusion_recipe')
    artifact_abi = _as_dict(manifest.get('artifact_abi'), 'artifact_abi')
    policy = _as_dict(manifest.get('policy'), 'policy')
    modalities = _as_dict(manifest.get('modalities'), 'modalities')
    contributors = manifest.get('contributors')
    if not isinstance(contributors, list) or not (1 <= len(contributors) <= 256):
        raise AdmissionError('Expected 1..256 contributors')
    if not isinstance(artifact_paths, Mapping):
        raise AdmissionError('artifact_paths must be an object')

    expected: dict[str, Any] = {
        'base': base.get('artifact_sha256'),
        'candidate': artifact_abi.get('artifact_sha256'),
    }
    blockers: list[str] = []
    if type(fusion.get('gradient_steps')) is not int or fusion['gradient_steps'] != 0:
        blockers.append('TRAINING_NOT_AUTHORIZED')
    if policy.get('weights_grant_permissions') is not False:
        blockers.append('POLICY_ABI_PERMISSION_ESCALATION')
    if artifact_abi.get('container_format') != 'safetensors':
        blockers.append('UNSAFE_CONTAINER_FORMAT')
    if level in ('L3', 'L4'):
        blockers.append('L3_BRIDGE_E2E_NOT_VERIFIED')
    if manifest.get('release_status') == 'RELEASED':
        blockers.append('UNVERIFIED_RELEASE_CLAIM')

    seen: set[str] = set()
    for c in contributors:
        if not isinstance(c, dict):
            raise AdmissionError('Contributor must be an object')
        source_id = c.get('source_id')
        if not isinstance(source_id, str) or not _SOURCE.fullmatch(source_id):
            raise AdmissionError('Invalid contributor source_id')
        if source_id in seen:
            raise AdmissionError(f'Duplicate contributor source_id: {source_id}')
        seen.add(source_id)
        key = f'contributor:{source_id}'
        expected[key] = c.get('artifact_sha256')
        if c.get('ancestry_sha256') != base.get('artifact_sha256'):
            blockers.append(f'BASE_ANCESTRY_MISMATCH:{source_id}')
        alpha = c.get('weight_alpha')
        if (type(alpha) not in (float, int) or not 0 <= alpha <= 2
                or alpha != alpha):
            blockers.append(f'INVALID_WEIGHT_ALPHA:{source_id}')

    for name, status in sorted(modalities.items()):
        if status == 'SUPPORTED':
            blockers.append(f'SUPPORTED_WITHOUT_INDEPENDENT_E2E:{name}')
        elif status in _SELF_ASSERTED_LEVELS:
            blockers.append(f'UNVERIFIED_ASSERTION:{name}:{status}')

    root = Path(artifacts_root)
    if root.is_symlink() or not root.is_dir():
        raise AdmissionError('artifacts_root must be an existing non-symlink directory')
    root = root.resolve()
    verified: list[str] = []
    for logical_id, asserted_digest in sorted(expected.items()):
        if not _hash(asserted_digest):
            blockers.append(f'INVALID_ARTIFACT_SHA256:{logical_id}')
            continue
        provided_path = artifact_paths.get(logical_id)
        if provided_path is None:
            blockers.append(f'ARTIFACT_UNAVAILABLE:{logical_id}')
            continue
        try:
            path = _file_in_workspace(root, provided_path)
        except ValueError:
            blockers.append(f'UNSAFE_ARTIFACT_PATH:{logical_id}')
            continue
        if not path.is_file():
            blockers.append(f'ARTIFACT_UNAVAILABLE:{logical_id}')
            continue
        if path.suffix != '.safetensors':
            blockers.append(f'UNSAFE_CONTAINER_FORMAT:{logical_id}')
            continue
        try:
            actual = inspect_safetensors(path, hash_file=True)
        except (SafetensorsValidationError, OSError, ValueError):
            blockers.append(f'INVALID_SAFETENSORS:{logical_id}')
            continue
        if actual.sha256 != asserted_digest:
            blockers.append(f'SHA256_MISMATCH:{logical_id}')
        else:
            verified.append(logical_id)

    artifact_block_prefixes = ('INVALID_ARTIFACT_', 'ARTIFACT_UNAVAILABLE:',
                               'UNSAFE_ARTIFACT_PATH:', 'INVALID_SAFETENSORS:',
                               'SHA256_MISMATCH:', 'UNSAFE_CONTAINER_FORMAT:')
    integrity_verified = (len(verified) == len(expected)
                          and not any(x.startswith(artifact_block_prefixes) for x in blockers))
    blockers.append('NO_INDEPENDENT_E2E_EVIDENCE')
    return AdmissionReport(
        model_id=model_id,
        declared_fusion_level=level,
        status='INTEGRITY_VERIFIED_ONLY' if integrity_verified
            and all(x == 'NO_INDEPENDENT_E2E_EVIDENCE' for x in blockers) else 'BLOCKED',
        artifact_integrity_verified=integrity_verified,
        verified_artifacts=tuple(sorted(verified)),
        blockers=tuple(sorted(set(blockers))),
    )
