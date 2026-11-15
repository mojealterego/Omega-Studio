"""Deterministic bounded-memory image tiling for mobile/offline editors.

Provides a scheduling *plan*, not GPU allocation, RAW decoding, 3D relighting,
or a claim of zero latency. Halo-aware invalidation avoids stale neighbor tiles.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


class TilePlanError(ValueError):
    """Requested image operation violates geometry or memory constraints."""


def _int(value: int, name: str, *, zero_ok: bool = False) -> int:
    if type(value) is not int or value < 0 or (not zero_ok and value == 0):
        raise TilePlanError(f'{name} must be {"non-negative" if zero_ok else "positive"} integer')
    return value


@dataclass(frozen=True, slots=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        _int(self.x, 'x', zero_ok=True)
        _int(self.y, 'y', zero_ok=True)
        _int(self.width, 'width')
        _int(self.height, 'height')

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def intersects(self, other: 'Rect') -> bool:
        return self.x < other.right and other.x < self.right and self.y < other.bottom and other.y < self.bottom


@dataclass(frozen=True, slots=True)
class MemoryProfile:
    total_ram_bytes: int
    reserved_system_bytes: int
    reserved_models_bytes: int
    working_set_cap_bytes: int

    def __post_init__(self) -> None:
        _int(self.total_ram_bytes, 'total_ram_bytes')
        _int(self.reserved_system_bytes, 'reserved_system_bytes', zero_ok=True)
        _int(self.reserved_models_bytes, 'reserved_models_bytes', zero_ok=True)
        _int(self.working_set_cap_bytes, 'working_set_cap_bytes')
        if self.reserved_system_bytes + self.reserved_models_bytes >= self.total_ram_bytes:
            raise TilePlanError('RAM reservations exhaust the physical memory budget')

    @property
    def available_bytes(self) -> int:
        return min(self.working_set_cap_bytes,
                   self.total_ram_bytes - self.reserved_system_bytes - self.reserved_models_bytes)


@dataclass(frozen=True, slots=True)
class Tile:
    core: Rect
    read: Rect
    working_set_bytes: int
    row: int
    column: int


def estimate_full_frame_bytes(width: int, height: int, *, channels: int = 4,
                              bytes_per_channel: int = 4, concurrent_buffers: int = 3) -> int:
    for key, val in (('width', width), ('height', height), ('channels', channels),
                     ('bytes_per_channel', bytes_per_channel), ('concurrent_buffers', concurrent_buffers)):
        _int(val, key)
    return width * height * channels * bytes_per_channel * concurrent_buffers


def plan_tiles(
    width: int, height: int, *, tile_size: int = 512, halo: int = 0,
    channels: int = 4, bytes_per_channel: int = 2, concurrent_buffers: int = 2,
    memory: MemoryProfile, focus: tuple[float, float] = (0.5, 0.5),
    roi: Rect | None = None, dirty: Rect | None = None, max_tiles: int = 100_000,
) -> tuple[Tile, ...]:
    """Plan read/compute tiles in focus order, respecting an explicit RAM cap.

    `core` is the output region, `read` includes the processing halo. `dirty`
    invalidates any tile whose read region intersects modified source pixels.
    `roi` restricts requested output tiles. The planner makes no allocations.
    """
    for key, val, zero_ok in (('width', width, False), ('height', height, False),
                              ('tile_size', tile_size, False), ('halo', halo, True),
                              ('channels', channels, False),
                              ('bytes_per_channel', bytes_per_channel, False),
                              ('concurrent_buffers', concurrent_buffers, False),
                              ('max_tiles', max_tiles, False)):
        _int(val, key, zero_ok=zero_ok)
    if not isinstance(memory, MemoryProfile):
        raise TilePlanError('A validated MemoryProfile is required')
    if (not isinstance(focus, (tuple, list)) or len(focus) != 2
            or any(isinstance(v, bool) or not isinstance(v, (float, int)) or
                   not math.isfinite(v) or not 0 <= v <= 1 for v in focus)):
        raise TilePlanError('focus must be normalized finite (x,y) in [0,1]')
    for name, region in (('roi', roi), ('dirty', dirty)):
        if region is not None and (not isinstance(region, Rect) or region.right > width or region.bottom > height):
            raise TilePlanError(f'{name} must be contained in the image')

    # Work only on candidate tile coordinates; this is safe for huge canvases
    # when ROI is small, and avoids an O(total-image-tiles) scan.
    left, top, right, bottom = 0, 0, width, height
    if roi is not None:
        left, top, right, bottom = roi.x, roi.y, roi.right, roi.bottom
    if dirty is not None:
        left = max(left, max(0, dirty.x - halo))
        top = max(top, max(0, dirty.y - halo))
        right = min(right, min(width, dirty.right + halo))
        bottom = min(bottom, min(height, dirty.bottom + halo))
    if right <= left or bottom <= top:
        return ()

    c0, c1 = left // tile_size, (right - 1) // tile_size
    r0, r1 = top // tile_size, (bottom - 1) // tile_size
    count = (c1 - c0 + 1) * (r1 - r0 + 1)
    if count > max_tiles:
        raise TilePlanError('Selected tile count exceeds max_tiles')

    tiles: list[Tile] = []
    for row in range(r0, r1 + 1):
        for col in range(c0, c1 + 1):
            x, y = col * tile_size, row * tile_size
            core = Rect(x, y, min(tile_size, width - x), min(tile_size, height - y))
            rx, ry = max(0, x - halo), max(0, y - halo)
            rright, rbottom = min(width, core.right + halo), min(height, core.bottom + halo)
            read = Rect(rx, ry, rright - rx, rbottom - ry)
            if dirty is not None and not read.intersects(dirty):
                continue
            bytes_needed = read.width * read.height * channels * bytes_per_channel * concurrent_buffers
            if bytes_needed > memory.available_bytes:
                raise TilePlanError('Single tile exceeds available working-set budget')
            tiles.append(Tile(core, read, bytes_needed, row, col))
    fx, fy = focus
    tiles.sort(key=lambda t: (
        ((t.core.x + t.core.width / 2) / width - fx) ** 2
        + ((t.core.y + t.core.height / 2) / height - fy) ** 2,
        t.row, t.column,
    ))
    return tuple(tiles)
