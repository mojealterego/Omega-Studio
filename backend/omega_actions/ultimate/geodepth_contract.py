"""GeoDepth Omega: pure geometry and epistemic provenance contracts.

Implements optical-Z vs ray-range distinction, explicit world-to-camera pose,
ROI intrinsics transformation with the half-pixel convention, and fail-closed
provenance validation. No inference or claim of metric camera measurement.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Sequence


class GeometryContractError(ValueError):
    """Input cannot satisfy the declared geometric/measurement contract."""


class DepthDefinition(str, Enum):
    OPTICAL_Z = "optical_z"
    RAY_RANGE_RHO = "ray_range_rho"


class GeometryUnit(str, Enum):
    ARBITRARY_SCALE = "arbitrary_scale"
    METERS = "meters"


class Provenance(str, Enum):
    RELATIVE_ESTIMATED = "relative_estimated"
    SCALE_ALIGNED = "scale_aligned"
    METRIC_ESTIMATED = "metric_estimated"
    METRIC_MEASURED = "metric_measured"
    RECONSTRUCTED_3D = "reconstructed_3d"
    GENERATED_SYNTHETIC = "generated_synthetic"


def _finite_number(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise GeometryContractError(f"{label} must be finite numeric")
    return float(value)


@dataclass(frozen=True, slots=True)
class GeometryClaim:
    provenance: Provenance
    unit: GeometryUnit
    anchor_id: str | None = None
    model_release_id: str | None = None
    sensor_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, Provenance) or not isinstance(self.unit, GeometryUnit):
            raise GeometryContractError("Unknown provenance or unit")
        if self.provenance is Provenance.RELATIVE_ESTIMATED and self.unit is not GeometryUnit.ARBITRARY_SCALE:
            raise GeometryContractError("Monocular relative depth cannot be reported in meters")
        if self.provenance is Provenance.METRIC_MEASURED:
            if self.unit is not GeometryUnit.METERS or not self.sensor_id:
                raise GeometryContractError("Measured metric depth requires meters and a sensor identifier")
        if self.provenance is Provenance.METRIC_ESTIMATED:
            if self.unit is not GeometryUnit.METERS or not self.model_release_id:
                raise GeometryContractError("Estimated metric depth requires meters and a model release")
        if self.provenance is Provenance.SCALE_ALIGNED:
            if self.unit is not GeometryUnit.METERS or not self.anchor_id:
                raise GeometryContractError("Scale-aligned metric depth requires an anchor identifier")
        if self.provenance is Provenance.RECONSTRUCTED_3D and self.unit is GeometryUnit.METERS:
            if not (self.anchor_id or self.sensor_id):
                raise GeometryContractError("Metric reconstruction requires documented scale evidence")

    @property
    def is_measured(self) -> bool:
        return self.provenance is Provenance.METRIC_MEASURED


@dataclass(frozen=True, slots=True)
class CameraIntrinsics:
    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int
    skew: float = 0.0

    def __post_init__(self) -> None:
        for field in ("fx", "fy", "cx", "cy", "skew"):
            val = _finite_number(getattr(self, field), field)
            if field in ("fx", "fy") and val <= 0.0:
                raise GeometryContractError(f"{field} must be > 0")
        if type(self.width) is not int or type(self.height) is not int or self.width <= 0 or self.height <= 0:
            raise GeometryContractError("width and height must be positive integers")

    def crop_resize(
        self, x0: int, y0: int, crop_width: int, crop_height: int, out_width: int, out_height: int
    ) -> "CameraIntrinsics":
        values = (x0, y0, crop_width, crop_height, out_width, out_height)
        if any(type(v) is not int for v in values) or x0 < 0 or y0 < 0 or min(values[2:]) <= 0:
            raise GeometryContractError("ROI and output dimensions must be valid integers")
        if x0 + crop_width > self.width or y0 + crop_height > self.height:
            raise GeometryContractError("ROI must be contained in the source frame")
        sx = out_width / crop_width
        sy = out_height / crop_height
        return CameraIntrinsics(
            fx=sx * self.fx,
            fy=sy * self.fy,
            cx=sx * (self.cx - x0 + 0.5) - 0.5,
            cy=sy * (self.cy - y0 + 0.5) - 0.5,
            width=out_width,
            height=out_height,
            skew=sx * self.skew,
        )

    def pixel_ray(self, u: float, v: float) -> tuple[float, float, float]:
        """Non-unit ray K^-1 [u, v, 1] including camera skew."""
        pu = _finite_number(u, "u")
        pv = _finite_number(v, "v")
        y = (pv - self.cy) / self.fy
        x = (pu - self.cx - self.skew * y) / self.fx
        return x, y, 1.0

    def backproject(self, u: float, v: float, distance: float, kind: DepthDefinition) -> tuple[float, float, float]:
        depth = _finite_number(distance, "distance")
        if depth <= 0:
            raise GeometryContractError("Depth/range must be strictly positive")
        if not isinstance(kind, DepthDefinition):
            raise GeometryContractError("Unknown depth definition")
        ray = self.pixel_ray(u, v)
        if kind is DepthDefinition.OPTICAL_Z:
            return tuple(component * depth for component in ray)
        ray_len = math.sqrt(sum(component * component for component in ray))
        return tuple(component * depth / ray_len for component in ray)


@dataclass(frozen=True, slots=True)
class WorldToCameraPose:
    """T_w2c: X_camera = R_w2c @ X_world + t_w2c.

    Orthogonal R is required. Inverse X_world = R_w2c^T @ (X_camera - t_w2c).
    This spelling deliberately avoids ambiguous T_cw/T_wc conventions.
    """

    rotation: tuple[tuple[float, float, float], ...]
    translation: tuple[float, float, float]

    def __post_init__(self) -> None:
        R = self.rotation
        if len(R) != 3 or any(len(row) != 3 for row in R) or len(self.translation) != 3:
            raise GeometryContractError("SE(3) pose requires a 3x3 rotation and 3-vector translation")
        for i in range(3):
            for j in range(3):
                _finite_number(R[i][j], "rotation")
            _finite_number(self.translation[i], "translation")
        for i in range(3):
            for j in range(3):
                dot = sum(R[k][i] * R[k][j] for k in range(3))
                if abs(dot - (1.0 if i == j else 0.0)) > 1e-6:
                    raise GeometryContractError("Rotation must be orthonormal")
        det = (R[0][0] * (R[1][1]*R[2][2]-R[1][2]*R[2][1])
               - R[0][1] * (R[1][0]*R[2][2]-R[1][2]*R[2][0])
               + R[0][2] * (R[1][0]*R[2][1]-R[1][1]*R[2][0]))
        if abs(det - 1.0) > 1e-6:
            raise GeometryContractError("SE(3) requires a proper rotation with determinant +1")

    def world_to_camera(self, world: Sequence[float]) -> tuple[float, float, float]:
        if len(world) != 3:
            raise GeometryContractError("Expected a 3D point")
        w = [_finite_number(world[i], "world point") for i in range(3)]
        return tuple(sum(self.rotation[i][j] * w[j] for j in range(3)) + self.translation[i] for i in range(3))

    def camera_to_world(self, camera: Sequence[float]) -> tuple[float, float, float]:
        if len(camera) != 3:
            raise GeometryContractError("Expected a 3D point")
        c = [_finite_number(camera[i], "camera point") - self.translation[i] for i in range(3)]
        return tuple(sum(self.rotation[j][i] * c[j] for j in range(3)) for i in range(3))
