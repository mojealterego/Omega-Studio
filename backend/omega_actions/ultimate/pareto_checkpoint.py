"""Read-only LoRA/Pareto compatibility assessment for OMEGA OMNI.

Only inspects trusted safetensors headers via the existing safetensors_guard.
No tensors are loaded, rewritten, reflected, merged, or abliterated here.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import re
from typing import Any, Mapping


class AdapterAuditError(ValueError):
    """Adapter manifest violates the structural contract."""


_SIDES = re.compile(r"^(?P<target>.+)\.lora_(?P<side>A|B)\.weight$")
_HASH = re.compile(r"^[0-9a-fA-F]{64}$")


def analyze_lora_report(report: Any) -> dict[str, Any]:
    """Validate a parsed safetensors report; never interpret source hash as base hash.

    The input is the immutable SafetensorsReport produced by safetensors_guard,
    but simple objects with the same public fields are supported in unit tests.
    """
    tensor_records = tuple(report.tensors)
    if not tensor_records:
        raise AdapterAuditError("Empty adapter: no tensor records")
    pair_map: dict[str, dict[str, Any]] = {}
    for tensor in tensor_records:
        match = _SIDES.fullmatch(tensor.name)
        if not match:
            raise AdapterAuditError(f"Non-LoRA tensor in adapter: {tensor.name}")
        target, side = match.group("target"), match.group("side")
        sides = pair_map.setdefault(target, {})
        if side in sides:
            raise AdapterAuditError(f"Duplicate LoRA side: {tensor.name}")
        sides[side] = tensor
    pairs: list[dict[str, Any]] = []
    for target in sorted(pair_map):
        sides = pair_map[target]
        if set(sides) != {"A", "B"}:
            raise AdapterAuditError(f"Unpaired LoRA projection: {target}")
        a, b = sides["A"], sides["B"]
        if len(a.shape) != 2 or len(b.shape) != 2:
            raise AdapterAuditError(f"LoRA tensors must be matrices: {target}")
        rank_a, in_dim = a.shape
        out_dim, rank_b = b.shape
        if not all(type(dim) is int and dim > 0 for dim in (rank_a, in_dim, out_dim, rank_b)):
            raise AdapterAuditError(f"LoRA dimensions must be positive: {target}")
        if rank_a != rank_b:
            raise AdapterAuditError(f"Inconsistent LoRA rank: {target}")
        pairs.append({
            "target": target,
            "base_weight_key": f"{target}.weight",
            "base_shape": [out_dim, in_dim],
            "rank": rank_a,
            "dtype_a": a.dtype,
            "dtype_b": b.dtype,
            "dtype_mismatch": a.dtype != b.dtype,
        })
    metadata = dict(report.metadata)
    sha = metadata.get("base_model_sha256") or metadata.get("omega.base_model_sha256")
    source_sha = metadata.get("omega.source_sha256")
    blockers: list[str] = []
    if not sha or not _HASH.fullmatch(sha):
        blockers.append("NO_BASE_MODEL_IDENTITY")
        sha = None
    alpha_raw = metadata.get("lora_alpha") or metadata.get("omega.lora_alpha")
    alpha = None
    if alpha_raw is not None:
        try:
            alpha = float(alpha_raw)
        except (ValueError, TypeError, OverflowError):
            pass
    if alpha is None or not math.isfinite(alpha) or alpha <= 0:
        blockers.append("NO_LORA_ALPHA")
        alpha = None
    mixed = sum(p["dtype_mismatch"] for p in pairs)
    if mixed:
        blockers.append("MIXED_DTYPE")
    if not getattr(report, "sha256", None):
        blockers.append("NO_CHECKPOINT_DIGEST")
    return {
        "schema": "omega.pareto.adapter-audit.v1",
        "checkpoint_sha256": getattr(report, "sha256", None),
        "file_bytes": getattr(report, "file_bytes", None),
        "tensor_count": len(tensor_records),
        "pair_count": len(pairs),
        "rank_histogram": dict(sorted(Counter(str(p["rank"]) for p in pairs).items())),
        "mixed_dtype_pairs": mixed,
        "source_adapter_sha256": source_sha,
        "base_model_sha256": sha.lower() if sha else None,
        "lora_alpha": alpha,
        "metadata_version": metadata.get("omega.version"),
        "base_compatibility": "UNVERIFIED",
        "eligible_for_automatic_merge": False,
        "blockers": blockers,
        "pairs": pairs,
    }


def evaluate_base_contract(
    audit: Mapping[str, Any], *,
    base_shapes: Mapping[str, tuple[int, int]],
    measured_base_sha256: str | None,
    declared_base_sha256: str | None,
    lora_alpha: float | None,
    license_confirmed: bool,
) -> dict[str, Any]:
    """Check a pinned compatibility contract, not inference or weight quality.

    The caller is responsible for measuring the actual base-file hash and for
    checking licensing. A report is never proof of running a generative model.
    """
    blockers: list[str] = []
    declared = declared_base_sha256 or audit.get("base_model_sha256")
    if not declared or not _HASH.fullmatch(declared):
        blockers.append("BASE_IDENTITY_UNDECLARED")
    if not measured_base_sha256 or not _HASH.fullmatch(measured_base_sha256):
        blockers.append("BASE_FILE_NOT_MEASURED")
    if declared and measured_base_sha256 and declared.lower() != measured_base_sha256.lower():
        blockers.append("BASE_HASH_MISMATCH")
    for pair in audit["pairs"]:
        key = pair["base_weight_key"]
        shape = base_shapes.get(key)
        if shape is None:
            blockers.append("BASE_LAYER_MISSING")
        elif tuple(shape) != tuple(pair["base_shape"]):
            blockers.append("BASE_SHAPE_MISMATCH")
    if lora_alpha is None or not isinstance(lora_alpha, (int, float)) or not math.isfinite(lora_alpha) or lora_alpha <= 0:
        blockers.append("INVALID_LORA_ALPHA")
    if audit.get("mixed_dtype_pairs"):
        blockers.append("DTYPE_CONVERSION_REQUIRED")
    if license_confirmed is not True:
        blockers.append("LICENSE_NOT_CONFIRMED")
    blockers = list(dict.fromkeys(blockers))
    return {
        "status": "BLOCKED" if blockers else "CONTRACT_MATCH_ONLY",
        "blockers": blockers,
        "pair_count": audit["pair_count"],
        "model_inference_verified": False,
        "production_ready": False,
        "weights_modified": False,
    }


def audit_lora_checkpoint(path: str) -> dict[str, Any]:
    """Inspect a local non-symlink safetensors file and compute SHA-256."""
    from .safetensors_guard import inspect_safetensors
    return analyze_lora_report(inspect_safetensors(path, hash_file=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OMEGA OMNI read-only LoRA audit; no weight modification")
    parser.add_argument("checkpoint", help="Regular .safetensors file")
    parser.add_argument("--output", help="Optional UTF-8 report JSON path (never overwrites checkpoint)")
    args = parser.parse_args(argv)
    try:
        from pathlib import Path
        result = audit_lora_checkpoint(args.checkpoint)
        serialized = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output:
            target = Path(args.output)
            if target.resolve() == Path(args.checkpoint).resolve():
                raise AdapterAuditError("Report path cannot overwrite the source checkpoint")
            with target.open("x", encoding="utf-8") as out:
                out.write(serialized)
        else:
            print(serialized, end="")
    except (AdapterAuditError, OSError, ValueError) as exc:
        parser.exit(2, f"OMEGA LoRA audit rejected input: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())