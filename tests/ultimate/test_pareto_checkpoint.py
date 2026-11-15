"""Read-only LoRA gate: metadata is not a substitute for a base model."""
import unittest
from types import SimpleNamespace

from omega_actions.ultimate.pareto_checkpoint import (
    AdapterAuditError, analyze_lora_report, evaluate_base_contract,
)


def make_report(*, missing_b=False, dtype_b='F16', alpha=None):
    tensors = [SimpleNamespace(name='diffusion_model.blocks.0.attn.wq.lora_A.weight',
                    shape=(2, 16), dtype='F16')]
    if not missing_b:
        tensors.append(SimpleNamespace(name='diffusion_model.blocks.0.attn.wq.lora_B.weight',
                    shape=(32, 2), dtype=dtype_b))
    meta = {'omega.source_sha256': 'a'*64, 'omega.version': '4.0.0'}
    if alpha is not None: meta['lora_alpha'] = str(alpha)
    return SimpleNamespace(tensors=tensors, metadata=meta, sha256='b'*64,
                          tensor_count=len(tensors), file_bytes=200)


class ParetoCheckpointTests(unittest.TestCase):
    def test_valid_pair_is_read_only_and_missing_base_is_blocked(self):
        report = analyze_lora_report(make_report())
        self.assertEqual(report['pair_count'], 1)
        self.assertEqual(report['rank_histogram'], {'2': 1})
        self.assertFalse(report['eligible_for_automatic_merge'])
        self.assertEqual(report['base_compatibility'], 'UNVERIFIED')
        self.assertIn('NO_BASE_MODEL_IDENTITY', report['blockers'])
        self.assertIn('NO_LORA_ALPHA', report['blockers'])
        self.assertEqual(report['source_adapter_sha256'], 'a'*64)
        self.assertNotEqual(report['source_adapter_sha256'], report.get('base_model_sha256'))

    def test_unpaired_tensor_is_rejected(self):
        with self.assertRaises(AdapterAuditError):
            analyze_lora_report(make_report(missing_b=True))

    def test_bad_rank_is_rejected(self):
        r = make_report()
        r.tensors[1].shape = (32, 3)
        with self.assertRaises(AdapterAuditError):
            analyze_lora_report(r)

    def test_mixed_dtype_is_recorded_not_treated_as_matched(self):
        result=analyze_lora_report(make_report(dtype_b='F32'))
        self.assertEqual(result['mixed_dtype_pairs'], 1)
        self.assertIn('MIXED_DTYPE', result['blockers'])

    def test_matched_base_is_only_contract_not_model_inference(self):
        audit=analyze_lora_report(make_report(alpha=4.0))
        assessment=evaluate_base_contract(
            audit,
            base_shapes={'diffusion_model.blocks.0.attn.wq.weight': (32,16)},
            measured_base_sha256='c'*64, declared_base_sha256='c'*64,
            lora_alpha=4.0, license_confirmed=True)
        self.assertEqual(assessment['status'], 'CONTRACT_MATCH_ONLY')
        self.assertFalse(assessment['model_inference_verified'])
        self.assertFalse(assessment['production_ready'])

    def test_wrong_base_shape_rejected(self):
        audit=analyze_lora_report(make_report(alpha=4.0))
        assess=evaluate_base_contract(audit, base_shapes={'diffusion_model.blocks.0.attn.wq.weight': (16,32)},
            measured_base_sha256='c'*64, declared_base_sha256='c'*64,
            lora_alpha=4.0, license_confirmed=True)
        self.assertEqual(assess['status'], 'BLOCKED')
        self.assertIn('BASE_SHAPE_MISMATCH', assess['blockers'])

    def test_mismatched_base_hash_rejected(self):
        audit=analyze_lora_report(make_report(alpha=4.0))
        assess=evaluate_base_contract(audit, base_shapes={'diffusion_model.blocks.0.attn.wq.weight': (32,16)},
            measured_base_sha256='d'*64, declared_base_sha256='c'*64,
            lora_alpha=4.0, license_confirmed=True)
        self.assertIn('BASE_HASH_MISMATCH', assess['blockers'])

    def test_empty_and_non_lora_are_rejected(self):
        r=make_report()
        r.tensors=[]
        with self.assertRaises(AdapterAuditError):analyze_lora_report(r)
        r.tensors=[SimpleNamespace(name='raw.base.weight',shape=(4,4),dtype='F32')]
        with self.assertRaises(AdapterAuditError):analyze_lora_report(r)


    def test_real_safetensors_checkpoint_audit_does_not_modify_bytes(self):
        import hashlib
        import json
        import struct
        import tempfile
        from pathlib import Path
        from omega_actions.ultimate.pareto_checkpoint import audit_lora_checkpoint

        prefix = "vision.blocks.0.attn.wq"
        header = {
            f"{prefix}.lora_A.weight": {"dtype": "F16", "shape": [2, 16], "data_offsets": [0, 64]},
            f"{prefix}.lora_B.weight": {"dtype": "F16", "shape": [32, 2], "data_offsets": [64, 192]},
            "__metadata__": {"lora_alpha": "4.0", "base_model_sha256": "c" * 64},
        }
        raw_header = json.dumps(header).encode("utf-8")
        raw_header += b" " * ((-len(raw_header)) % 8)
        payload = struct.pack("<Q", len(raw_header)) + raw_header + (b"\x00" * 192)
        with tempfile.TemporaryDirectory() as tmp:
            filename = Path(tmp) / "adapter.safetensors"
            filename.write_bytes(payload)
            outcome = audit_lora_checkpoint(str(filename))
            self.assertEqual(outcome["pair_count"], 1)
            self.assertEqual(outcome["base_model_sha256"], "c" * 64)
            self.assertEqual(outcome["lora_alpha"], 4.0)
            self.assertFalse(outcome["eligible_for_automatic_merge"])
            self.assertEqual(outcome["checkpoint_sha256"], hashlib.sha256(payload).hexdigest())
            self.assertEqual(filename.read_bytes(), payload)

    def test_binary_audit_rejects_invalid_header(self):
        import struct
        import tempfile
        from pathlib import Path
        from omega_actions.ultimate.pareto_checkpoint import audit_lora_checkpoint
        from omega_actions.ultimate.safetensors_guard import SafetensorsValidationError
        with tempfile.TemporaryDirectory() as tmp:
            filename = Path(tmp) / "bad.safetensors"
            filename.write_bytes(struct.pack("<Q", 2) + b"[]")
            with self.assertRaises(SafetensorsValidationError):
                audit_lora_checkpoint(str(filename))


if __name__ == '__main__': unittest.main()