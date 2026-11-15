"""Foveated tiling, halo invalidation and explicit mobile RAM gates."""
import math
import pytest

from omega_actions.ultimate.mobile_tile_planner import (
    MemoryProfile, Rect, TilePlanError, plan_tiles, estimate_full_frame_bytes,
)


def test_full_frame_coverage_and_deterministic_focus_order():
    mem = MemoryProfile(total_ram_bytes=8 * 1024 * 1024, reserved_system_bytes=1024 * 1024,
                        reserved_models_bytes=1024 * 1024, working_set_cap_bytes=4 * 1024 * 1024)
    tiles = plan_tiles(1025, 513, tile_size=256, halo=8, channels=4,
                       bytes_per_channel=2, concurrent_buffers=3, memory=mem,
                       focus=(0.99, 0.99))
    assert len(tiles) == 15
    assert tiles[0].core.x == 1024 and tiles[0].core.y == 512
    assert {tuple((t.core.x, t.core.y)) for t in tiles} == {
        (x, y) for y in (0, 256, 512) for x in (0, 256, 512, 768, 1024)
    }
    assert all(t.working_set_bytes <= mem.available_bytes for t in tiles)
    assert tiles == plan_tiles(1025, 513, tile_size=256, halo=8, channels=4,
                               bytes_per_channel=2, concurrent_buffers=3, memory=mem,
                               focus=(0.99, 0.99))


def test_dirty_region_invalidates_tiles_touching_halo():
    mem = MemoryProfile(total_ram_bytes=16_000_000, reserved_system_bytes=1_000_000,
                        reserved_models_bytes=1_000_000, working_set_cap_bytes=1_000_000)
    tiles = plan_tiles(512, 256, tile_size=256, halo=16, channels=4,
                       bytes_per_channel=1, concurrent_buffers=2, memory=mem,
                       dirty=Rect(255, 10, 2, 2))
    assert len(tiles) == 2
    assert {t.core.x for t in tiles} == {0, 256}
    assert all(t.read.intersects(Rect(255, 10, 2, 2)) for t in tiles)


def test_requested_roi_and_dirty_region_are_both_honored():
    mem = MemoryProfile(total_ram_bytes=16_000_000, reserved_system_bytes=1_000_000,
                        reserved_models_bytes=1_000_000, working_set_cap_bytes=1_000_000)
    tiles = plan_tiles(1024, 1024, tile_size=256, halo=8, channels=4,
                       bytes_per_channel=1, concurrent_buffers=1, memory=mem,
                       roi=Rect(256, 256, 256, 256), dirty=Rect(257, 257, 1, 1))
    assert len(tiles) == 1
    assert tiles[0].core == Rect(256, 256, 256, 256)


def test_150_megapixel_raw_requires_tiles_and_memory_budget():
    full = estimate_full_frame_bytes(14204, 10652, channels=4, bytes_per_channel=4, concurrent_buffers=3)
    assert full > 7_000_000_000
    memory = MemoryProfile(total_ram_bytes=12 * 1024**3,
                           reserved_system_bytes=4 * 1024**3,
                           reserved_models_bytes=6 * 1024**3,
                           working_set_cap_bytes=192 * 1024**2)
    tiles = plan_tiles(14204, 10652, tile_size=512, halo=16, channels=4,
                       bytes_per_channel=4, concurrent_buffers=3, memory=memory)
    assert len(tiles) == math.ceil(14204/512) * math.ceil(10652/512)
    assert max(t.working_set_bytes for t in tiles) <= memory.available_bytes
    assert memory.available_bytes == 192 * 1024**2


def test_fail_closed_on_overbudget_tile():
    memory = MemoryProfile(total_ram_bytes=1024, reserved_system_bytes=128,
                           reserved_models_bytes=128, working_set_cap_bytes=64)
    with pytest.raises(TilePlanError, match='budget'):
        plan_tiles(1000, 1000, tile_size=256, halo=16, channels=4,
                   bytes_per_channel=4, concurrent_buffers=3, memory=memory)


@pytest.mark.parametrize('params', [
    {'width': 0}, {'height': -1}, {'tile_size': 0}, {'tile_size': True},
    {'halo': -1}, {'channels': 0}, {'bytes_per_channel': 0},
    {'concurrent_buffers': 0}, {'focus': (float('nan'), 0.5)},
    {'focus': (1.1, 0.5)}, {'max_tiles': 0},
])
def test_invalid_plan_parameters_rejected(params):
    kwargs = {'width': 100, 'height': 100, 'tile_size': 64, 'halo': 2,
              'channels': 4, 'bytes_per_channel': 1, 'concurrent_buffers': 1,
              'memory': MemoryProfile(1024 * 1024, 0, 0, 1024 * 1024)}
    kwargs.update(params)
    with pytest.raises(TilePlanError):
        plan_tiles(**kwargs)


def test_rejects_invalid_memory_and_rectangles():
    with pytest.raises(TilePlanError): MemoryProfile(100, 80, 30, 100)
    with pytest.raises(TilePlanError): Rect(-1, 0, 2, 2)
    with pytest.raises(TilePlanError): Rect(0, 0, 0, 2)
    mem = MemoryProfile(1000000, 0, 0, 1000000)
    with pytest.raises(TilePlanError):
        plan_tiles(100, 100, tile_size=50, memory=mem, roi=Rect(100, 0, 1, 1))


def test_tile_limit_enforced_without_materializing_massive_plan():
    mem = MemoryProfile(1000000, 0, 0, 1000000)
    with pytest.raises(TilePlanError, match='max_tiles'):
        plan_tiles(100000, 100000, tile_size=16, memory=mem, max_tiles=1000)


def test_deterministic_randomized_tiling_exactly_covers_small_images():
    import random
    rng = random.Random(20261115)
    mem = MemoryProfile(32 * 1024 * 1024, 0, 0, 16 * 1024 * 1024)
    for _ in range(150):
        width = rng.randint(1, 45)
        height = rng.randint(1, 45)
        tile_size = rng.randint(1, 24)
        halo = rng.randint(0, 8)
        tiles = plan_tiles(width, height, tile_size=tile_size, halo=halo,
                           channels=4, bytes_per_channel=2,
                           concurrent_buffers=3, memory=mem)
        coverage = [[0 for _ in range(width)] for _ in range(height)]
        for tile in tiles:
            assert tile.read.x <= tile.core.x
            assert tile.read.y <= tile.core.y
            assert tile.read.right >= tile.core.right
            assert tile.read.bottom >= tile.core.bottom
            for y in range(tile.core.y, tile.core.bottom):
                for x in range(tile.core.x, tile.core.right):
                    coverage[y][x] += 1
        assert all(c == 1 for row in coverage for c in row)


def test_halo_invalidation_property_against_bruteforce():
    import random
    rng = random.Random(45)
    mem = MemoryProfile(16 * 1024 * 1024, 0, 0, 8 * 1024 * 1024)
    for _ in range(100):
        width, height = rng.randint(20, 100), rng.randint(20, 100)
        tile_size, halo = rng.randint(5, 25), rng.randint(0, 10)
        dirty = Rect(rng.randrange(width), rng.randrange(height), 1, 1)
        all_tiles = plan_tiles(width, height, tile_size=tile_size, halo=halo, memory=mem)
        expected = {(t.row, t.column) for t in all_tiles if t.read.intersects(dirty)}
        selected = plan_tiles(width, height, tile_size=tile_size, halo=halo,
                              memory=mem, dirty=dirty)
        assert {(t.row, t.column) for t in selected} == expected
