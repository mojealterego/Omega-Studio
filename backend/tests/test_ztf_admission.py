"""RED/GREEN tests of read-only Zero Training Fusion evidence admission."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct

import pytest

from omega_actions.ultimate.ztf_admission import AdmissionError, admit_manifest


def make_tensor(path: Path, value: bytes = b'\x00\x00\x80?') -> str:
    header = json.dumps({'w': {'dtype': 'F32', 'shape': [1], 'data_offsets': [0, 4]}}).encode()
    header += b' ' * ((-len(header)) % 8)
    path.write_bytes(struct.pack('<Q', len(header)) + header + value)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(tmp_path: Path):
    base_hash = make_tensor(tmp_path/'base.safetensors')
    contributor_hash = make_tensor(tmp_path/'delta.safetensors', b'\x00\x00\x00@')
    candidate_hash = make_tensor(tmp_path/'candidate.safetensors', b'\x00\x00@@')
    manifest = {
        'schema': 'omega.unified_model_manifest.v2', 'fusion_level': 'L2',
        'model_id': 'omegax-candidate',
        'base': {'artifact_sha256': base_hash, 'architecture_id': 'qwen-vl'},
        'contributors': [{'source_id': 'SRC-005', 'artifact_sha256': contributor_hash,
                          'ancestry_sha256': base_hash, 'role': 'task_delta', 'weight_alpha': 0.5}],
        'fusion_recipe': {'gradient_steps': 0},
        'artifact_abi': {'artifact_sha256': candidate_hash, 'container_format': 'safetensors'},
        'policy': {'weights_grant_permissions': False},
        'modalities': {'reasoning': 'NOT_VERIFIED', 'video': 'NOT_VERIFIED'},
        'release_status': 'CANDIDATE',
    }
    paths = {'base': 'base.safetensors', 'contributor:SRC-005': 'delta.safetensors',
             'candidate': 'candidate.safetensors'}
    return manifest, paths


def test_three_physical_hashes_pass_integrity_but_never_release(tmp_path):
    manifest, paths = fixture(tmp_path)
    res = admit_manifest(manifest, tmp_path, paths)
    assert res.artifact_integrity_verified is True
    assert res.release_authorized is False
    assert res.status == 'INTEGRITY_VERIFIED_ONLY'
    assert res.verified_artifacts == ('base', 'candidate', 'contributor:SRC-005')
    assert 'NO_INDEPENDENT_E2E_EVIDENCE' in res.blockers


def test_proposed_claims_do_not_promote_to_l3(tmp_path):
    m, paths = fixture(tmp_path)
    m['fusion_level'] = 'L3'
    m['modalities']['reasoning'] = 'SUPPORTED'
    res = admit_manifest(m, tmp_path, paths)
    assert res.release_authorized is False
    assert 'L3_BRIDGE_E2E_NOT_VERIFIED' in res.blockers
    assert 'SUPPORTED_WITHOUT_INDEPENDENT_E2E:reasoning' in res.blockers


def test_no_real_artifact_blocks_even_when_sha_is_hex(tmp_path):
    m, paths = fixture(tmp_path)
    paths['base'] = 'missing.safetensors'
    res = admit_manifest(m, tmp_path, paths)
    assert res.artifact_integrity_verified is False
    assert 'ARTIFACT_UNAVAILABLE:base' in res.blockers


def test_wrong_bytes_fail_closed(tmp_path):
    m, paths = fixture(tmp_path)
    make_tensor(tmp_path/'delta.safetensors', b'\x00\x00\x80@')
    res = admit_manifest(m, tmp_path, paths)
    assert 'SHA256_MISMATCH:contributor:SRC-005' in res.blockers


def test_fake_or_invalid_lineage_is_blocked(tmp_path):
    m, paths = fixture(tmp_path)
    m['contributors'][0]['ancestry_sha256'] = '0'*64
    res = admit_manifest(m, tmp_path, paths)
    assert 'BASE_ANCESTRY_MISMATCH:SRC-005' in res.blockers


def test_evidence_is_not_inferred_from_claimed_host_tested(tmp_path):
    m, paths = fixture(tmp_path)
    m['modalities']['reasoning'] = 'HOST_TESTED'
    res = admit_manifest(m, tmp_path, paths)
    assert 'UNVERIFIED_ASSERTION:reasoning:HOST_TESTED' in res.blockers


def test_training_steps_nonzero_hard_block(tmp_path):
    m, paths = fixture(tmp_path)
    m['fusion_recipe']['gradient_steps'] = 200
    res = admit_manifest(m, tmp_path, paths)
    assert 'TRAINING_NOT_AUTHORIZED' in res.blockers


def test_self_permission_escalation_hard_block(tmp_path):
    m, paths = fixture(tmp_path)
    m['policy']['weights_grant_permissions'] = True
    res = admit_manifest(m, tmp_path, paths)
    assert 'POLICY_ABI_PERMISSION_ESCALATION' in res.blockers


def test_no_candidate_does_not_invent_fusion(tmp_path):
    m, paths = fixture(tmp_path)
    del paths['candidate']
    res = admit_manifest(m, tmp_path, paths)
    assert res.artifact_integrity_verified is False
    assert 'ARTIFACT_UNAVAILABLE:candidate' in res.blockers


@pytest.mark.parametrize('unsafe', ['../escape.safetensors', '/etc/passwd', './../escape.safetensors'])
def test_path_escape_rejected(tmp_path, unsafe):
    m, paths = fixture(tmp_path)
    paths['base'] = unsafe
    res = admit_manifest(m, tmp_path, paths)
    assert 'UNSAFE_ARTIFACT_PATH:base' in res.blockers


def test_symlink_rejected(tmp_path):
    m, paths = fixture(tmp_path)
    (tmp_path/'link.safetensors').symlink_to(tmp_path/'base.safetensors')
    paths['base'] = 'link.safetensors'
    res = admit_manifest(m, tmp_path, paths)
    assert 'UNSAFE_ARTIFACT_PATH:base' in res.blockers


def test_symlink_parent_rejected(tmp_path):
    m, paths = fixture(tmp_path)
    (tmp_path/'linkdir').symlink_to(tmp_path, target_is_directory=True)
    paths['base'] = 'linkdir/base.safetensors'
    res = admit_manifest(m, tmp_path, paths)
    assert 'UNSAFE_ARTIFACT_PATH:base' in res.blockers


def test_duplicate_sources_rejected(tmp_path):
    m, paths = fixture(tmp_path)
    m['contributors'].append(dict(m['contributors'][0]))
    with pytest.raises(AdmissionError, match='Duplicate'):
        admit_manifest(m, tmp_path, paths)


def test_wrong_json_type_rejected(tmp_path):
    m, paths = fixture(tmp_path)
    m['fusion_recipe']['gradient_steps'] = False  # bool is subclass of int
    res = admit_manifest(m, tmp_path, paths)
    assert 'TRAINING_NOT_AUTHORIZED' in res.blockers


def test_metadata_artifact_sha_not_confused_with_git_commit(tmp_path):
    m, paths = fixture(tmp_path)
    m['base']['artifact_sha256'] = '753369bce3797cfe000577770eabcd3741a6a32a' + '0'*24
    res = admit_manifest(m, tmp_path, paths)
    assert 'SHA256_MISMATCH:base' in res.blockers


def test_unsupported_container_rejected(tmp_path):
    m, paths = fixture(tmp_path)
    m['artifact_abi']['container_format'] = 'pickle'
    res = admit_manifest(m, tmp_path, paths)
    assert 'UNSAFE_CONTAINER_FORMAT' in res.blockers


def test_invalid_safetensors_detected(tmp_path):
    m, paths = fixture(tmp_path)
    bad = tmp_path/'candidate.safetensors'
    bad.write_bytes(b'not-a-real-safetensors')
    m['artifact_abi']['artifact_sha256'] = hashlib.sha256(bad.read_bytes()).hexdigest()
    res = admit_manifest(m, tmp_path, paths)
    assert 'INVALID_SAFETENSORS:candidate' in res.blockers


def test_bad_fusion_level_hard_rejected(tmp_path):
    m, paths = fixture(tmp_path)
    m['fusion_level'] = 'L99'
    with pytest.raises(AdmissionError, match='fusion_level'):
        admit_manifest(m, tmp_path, paths)
