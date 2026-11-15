"""C2-continuous overlap crossfade for the existing mobile tile planner.

An ordinary Hann/raised-cosine edge is C1 but not C2 at constant-extension
joins. The quintic polynomial 6t^5-15t^4+10t^3 has zero first and second
endpoint derivatives and yields C2 transitions with a partition of unity.

This operator blends two already available small overlap strips. It does not
allocate a full 400 MP frame or claim that arbitrary tile processing is seam-free.
"""
from __future__ import annotations

import numpy as np


class C2BlendError(ValueError):
    """Invalid overlap geometry or non-finite input."""


def quintic_smoothstep(x: np.ndarray | float) -> np.ndarray:
    """Clamped, C2-continuous smoothstep in [0, 1]."""
    values = np.asarray(x, dtype=np.float64)
    if not np.all(np.isfinite(values)):
        raise C2BlendError('Blend coordinate must be finite')
    t = np.clip(values, 0.0, 1.0)
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def c2_crossfade(left: np.ndarray, right: np.ndarray, *, axis: int = 1) -> np.ndarray:
    """Blend identically shaped overlap strips over width/height, not full frames.

    ``axis=1`` is horizontal (left-right), ``axis=0`` vertical (top-bottom).
    Each endpoint exactly equals its corresponding strip; interior is smoothly
    crossfaded. Values represent the same scene-referred linear color space.
    """
    if not isinstance(left, np.ndarray) or not isinstance(right, np.ndarray):
        raise C2BlendError('Expected numpy arrays')
    if left.shape != right.shape or left.ndim not in (2, 3) or axis not in (0, 1):
        raise C2BlendError('Overlaps must have the same 2D/3D shape and spatial axis')
    if left.shape[axis] < 2 or min(left.shape[:2]) < 1:
        raise C2BlendError('Overlap has insufficient spatial samples')
    if left.dtype.kind != 'f' or right.dtype.kind != 'f':
        raise C2BlendError('Overlaps must be floating-point linear pixel data')
    if not np.all(np.isfinite(left)) or not np.all(np.isfinite(right)):
        raise C2BlendError('NaN/Inf in overlap input')
    samples = np.linspace(0.0, 1.0, left.shape[axis], dtype=np.float64)
    w = quintic_smoothstep(samples)
    broadcast = [1] * left.ndim
    broadcast[axis] = w.size
    weight = w.reshape(broadcast)
    blend = np.asarray(left, dtype=np.float64) * (1.0 - weight) + np.asarray(right, dtype=np.float64) * weight
    return blend.astype(np.result_type(left.dtype, right.dtype), copy=False)
