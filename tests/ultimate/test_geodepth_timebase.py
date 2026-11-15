"""Contracts lifted from GeoDepth Omega and OCG, tested independently of any model."""
import math
import pytest

from omega_actions.ultimate.cinematic_timebase import FrameRate, TimelineError
from omega_actions.ultimate.geodepth_contract import (
    CameraIntrinsics, GeometryClaim, GeometryUnit, Provenance,
    DepthDefinition, GeometryContractError, WorldToCameraPose,
)


def test_fractional_fps_ntsc_has_zero_cumulative_audio_drift():
    timeline = FrameRate(30000, 1001)
    assert timeline.audio_sample_at(0) == 0
    assert timeline.audio_sample_at(5, 48000) == 8008
    assert timeline.audio_sample_at(107892, 48000) == 172799827
    lengths = [timeline.audio_sample_window(i)[1] - timeline.audio_sample_window(i)[0] for i in range(20)]
    assert set(lengths) == {1601, 1602}
    assert sum(lengths) == timeline.audio_sample_at(20)
    assert timeline.frame_time(30000).numerator == 1001
    assert timeline.frame_time(30000).denominator == 1


def test_timebase_rejects_invalid_values_and_normalizes_fraction():
    assert FrameRate(48000, 2002) == FrameRate(24000, 1001)
    for args in [(0, 1), (1, 0), (-1, 1), (30.0, 1), (True, 1)]:
        with pytest.raises(TimelineError): FrameRate(*args)
    with pytest.raises(TimelineError): FrameRate(24, 1).audio_sample_at(-1)
    with pytest.raises(TimelineError): FrameRate(24, 1).audio_sample_at(1, 0)
    with pytest.raises(TimelineError): FrameRate(24, 1).audio_sample_window(0, 48000, end_frame=0)


def test_intrinsics_roi_crop_resize_uses_half_pixel_convention():
    camera = CameraIntrinsics(fx=1000, fy=900, cx=400, cy=300, width=800, height=600, skew=10)
    crop = camera.crop_resize(100, 50, 400, 300, 200, 150)
    assert crop.fx == 500
    assert crop.fy == 450
    assert crop.skew == 5
    assert crop.cx == pytest.approx(149.75)
    assert crop.cy == pytest.approx(124.75)
    # A pixel coordinate mapped by the same half-pixel transform backprojects to the same ray.
    u, v = 250.0, 175.0
    resized_u = (u - 100 + 0.5) * 0.5 - 0.5
    resized_v = (v - 50 + 0.5) * 0.5 - 0.5
    assert crop.pixel_ray(resized_u, resized_v) == pytest.approx(camera.pixel_ray(u, v))


def test_optical_z_and_ray_distance_are_not_interchangeable():
    cam = CameraIntrinsics(fx=100, fy=100, cx=0, cy=0, width=300, height=200)
    point_optical = cam.backproject(100, 0, 10, DepthDefinition.OPTICAL_Z)
    ray = cam.pixel_ray(100, 0)
    rho = 10 * math.sqrt(2)
    point_range = cam.backproject(100, 0, rho, DepthDefinition.RAY_RANGE_RHO)
    assert point_optical == pytest.approx((10, 0, 10))
    assert point_range == pytest.approx(point_optical)
    assert ray == pytest.approx((1, 0, 1))


def test_camera_extrinsics_explicit_world_to_camera_convention():
    pose = WorldToCameraPose(
        rotation=((0, -1, 0), (1, 0, 0), (0, 0, 1)),
        translation=(1, 2, 3),
    )
    point_cam = (4, 5, 6)
    world = pose.camera_to_world(point_cam)
    assert world == pytest.approx((3, -3, 3))
    assert pose.world_to_camera(world) == pytest.approx(point_cam)


def test_geometry_provenance_is_fail_closed_for_metric_claims():
    assert GeometryClaim(Provenance.RELATIVE_ESTIMATED, GeometryUnit.ARBITRARY_SCALE).is_measured is False
    with pytest.raises(GeometryContractError):
        GeometryClaim(Provenance.RELATIVE_ESTIMATED, GeometryUnit.METERS)
    with pytest.raises(GeometryContractError):
        GeometryClaim(Provenance.METRIC_MEASURED, GeometryUnit.METERS)
    assert GeometryClaim(Provenance.METRIC_MEASURED, GeometryUnit.METERS, sensor_id='tof-1').is_measured
    with pytest.raises(GeometryContractError):
        GeometryClaim(Provenance.SCALE_ALIGNED, GeometryUnit.METERS)
    assert not GeometryClaim(Provenance.SCALE_ALIGNED, GeometryUnit.METERS, anchor_id='lidar-7').is_measured
    with pytest.raises(GeometryContractError):
        GeometryClaim(Provenance.METRIC_ESTIMATED, GeometryUnit.METERS)
    assert not GeometryClaim(Provenance.METRIC_ESTIMATED, GeometryUnit.METERS, model_release_id='da3metric').is_measured


def test_geometry_rejects_invalid_calibrations_and_depth():
    for args in [dict(fx=0, fy=10, cx=0, cy=0, width=10, height=10),
                 dict(fx=10, fy=float('nan'), cx=0, cy=0, width=10, height=10)]:
        with pytest.raises(GeometryContractError): CameraIntrinsics(**args)
    cam = CameraIntrinsics(fx=100, fy=100, cx=20, cy=20, width=100, height=100)
    with pytest.raises(GeometryContractError): cam.crop_resize(90, 0, 20, 20, 20, 20)
    with pytest.raises(GeometryContractError): cam.backproject(10, 10, float('nan'), DepthDefinition.OPTICAL_Z)
    with pytest.raises(GeometryContractError): cam.backproject(10, 10, 0, DepthDefinition.OPTICAL_Z)
    with pytest.raises(GeometryContractError):
        WorldToCameraPose(rotation=((1,0,0),(0,1,0),(0,0,-1)), translation=(0,0,0))
