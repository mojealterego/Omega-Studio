"""Proof-driven regression of C2-continuous tile crossfades."""
from __future__ import annotations

import numpy as np
import pytest

from omega_actions.ultimate.c2_blending import C2BlendError, c2_crossfade, quintic_smoothstep


def test_partition_of_unity_and_boundaries():
    x = np.linspace(0, 1, 1001)
    w = quintic_smoothstep(x)
    np.testing.assert_allclose(w + quintic_smoothstep(1-x), 1, atol=2e-15)
    assert w[0] == 0 and w[-1] == 1
    assert np.all(np.diff(w) >= -1e-15)


def test_c2_derivatives_zero_at_joins():
    h = 1e-4
    f = quintic_smoothstep
    for x in (0.0, 1.0):
        first = (f(x+h) - f(x-h))/(2*h)
        second = (f(x+h)-2*f(x)+f(x-h))/(h*h)
        assert abs(first) < 1e-6
        assert abs(second) < 2e-3  # central-difference truncation error is O(h) at clamped join


def test_two_dimensional_stitch_is_weighted_not_core_crop():
    left = np.full((8, 4, 3), 10, dtype=np.float32)
    right = np.full((8, 4, 3), 30, dtype=np.float32)
    blend = c2_crossfade(left, right, axis=1)
    assert blend.shape == left.shape
    np.testing.assert_allclose(blend[:,0,:], 10)
    np.testing.assert_allclose(blend[:,-1,:], 30)
    np.testing.assert_allclose(blend[:,2,:], 10 + 20*quintic_smoothstep(2/3), atol=1e-6)


def test_reject_nans_wrong_shapes_and_too_small():
    arr = np.ones((3,4,3), dtype=np.float32)
    with pytest.raises(C2BlendError): c2_crossfade(arr, arr[:2])
    with pytest.raises(C2BlendError): c2_crossfade(arr, arr, axis=3)
    with pytest.raises(C2BlendError): c2_crossfade(arr[:,:1], arr[:,:1], axis=1)
    dirty = arr.copy(); dirty[1,2,0] = np.nan
    with pytest.raises(C2BlendError): c2_crossfade(dirty, arr)
