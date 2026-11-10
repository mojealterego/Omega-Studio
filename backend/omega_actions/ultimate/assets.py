"""Offline procedural SVG/PNG/WAV/glTF assets; no model inference is claimed."""
from __future__ import annotations
import base64
import html
import io
import json
import math
import struct
import wave
import zlib


def make_svg(text: str, *, size: int = 512) -> str:
    if not 64 <= size <= 4096 or len(text) > 1000:
        raise ValueError('Invalid SVG size or text length')
    safe = html.escape(text, quote=True)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
            f'viewBox="0 0 {size} {size}"><rect width="100%" height="100%" fill="#07080A"/>'
            f'<rect x="12" y="12" width="{size-24}" height="{size-24}" rx="22" '
            f'fill="none" stroke="#D4AF37" stroke-width="3"/>'
            f'<text x="50%" y="50%" text-anchor="middle" fill="#F4F1EA" '
            f'font-family="serif" font-size="{size//15}">{safe}</text></svg>')


def make_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    if not 1 <= width <= 4096 or not 1 <= height <= 4096 or len(rgb) != 3 or any(not 0 <= c <= 255 for c in rgb):
        raise ValueError('Invalid image dimensions or RGB values')

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))

    row = b'\x00' + bytes(rgb) * width
    raw = row * height
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>2I5B', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, level=6)) + chunk(b'IEND', b''))


def make_wav(frequency: float, duration: float, *, sample_rate: int = 22050) -> bytes:
    if not 20 <= frequency <= 10000 or not 0.01 <= duration <= 30 or sample_rate not in (22050, 44100, 48000):
        raise ValueError('Invalid audio parameters')
    n = round(sample_rate * duration)
    frames = bytearray()
    for i in range(n):
        envelope = min(1.0, i / max(1, sample_rate * 0.01), (n-i) / max(1, sample_rate * 0.03))
        sample = int(8000 * envelope * math.sin(2 * math.pi * frequency * i / sample_rate))
        frames.extend(struct.pack('<h', sample))
    out = io.BytesIO()
    with wave.open(out, 'wb') as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(frames)
    return out.getvalue()


def make_gltf_animation(*, duration: float = 2.0) -> dict:
    """Valid glTF 2.0 cube animated in 3D over time (3D + time)."""
    if not 0.1 <= duration <= 3600:
        raise ValueError('Invalid animation duration')
    positions = [-1,-1,-1, 1,-1,-1, 1,1,-1, -1,1,-1,
                 -1,-1,1, 1,-1,1, 1,1,1, -1,1,1]
    indices = [0,1,2,0,2,3, 4,6,5,4,7,6, 0,4,5,0,5,1,
               1,5,6,1,6,2, 2,6,7,2,7,3, 3,7,4,3,4,0]
    times = [0.0, duration / 2.0, duration]
    translations = [0.,0.,0., 0.,1.,0., 0.,0.,0.]
    data = bytearray()
    views = []

    def add(data_bytes: bytes, target=None):
        while len(data) % 4:
            data.append(0)
        start = len(data)
        data.extend(data_bytes)
        result = {'buffer': 0, 'byteOffset': start, 'byteLength': len(data_bytes)}
        if target:
            result['target'] = target
        views.append(result)
        return len(views)-1

    pos = add(struct.pack('<24f', *positions), 34962)
    ind = add(struct.pack('<36H', *indices), 34963)
    tim = add(struct.pack('<3f', *times))
    trn = add(struct.pack('<9f', *translations))
    uri = 'data:application/octet-stream;base64,' + base64.b64encode(data).decode('ascii')
    return {
        'asset': {'version': '2.0', 'generator': 'OMEGA Studio Procedural Asset Engine'},
        'buffers': [{'byteLength': len(data), 'uri': uri}], 'bufferViews': views,
        'accessors': [
            {'bufferView': pos, 'componentType': 5126, 'count': 8, 'type': 'VEC3', 'min': [-1,-1,-1], 'max': [1,1,1]},
            {'bufferView': ind, 'componentType': 5123, 'count': 36, 'type': 'SCALAR'},
            {'bufferView': tim, 'componentType': 5126, 'count': 3, 'type': 'SCALAR', 'min': [0], 'max': [duration]},
            {'bufferView': trn, 'componentType': 5126, 'count': 3, 'type': 'VEC3'}],
        'meshes': [{'primitives': [{'attributes': {'POSITION': 0}, 'indices': 1, 'mode': 4}]}],
        'nodes': [{'mesh': 0}], 'scenes': [{'nodes': [0]}], 'scene': 0,
        'animations': [{'samplers': [{'input': 2, 'output': 3, 'interpolation': 'LINEAR'}],
                        'channels': [{'sampler': 0, 'target': {'node': 0, 'path': 'translation'}}]}]
    }


def make_video(destination, *, duration: float = 1.0, fps: int = 12,
               width: int = 320, height: int = 180) -> dict:
    """Generate original procedural MP4 via a locally installed FFmpeg encoder."""
    import os
    from pathlib import Path
    import shutil
    import subprocess
    import tempfile
    if not 0.1 <= duration <= 60 or not 1 <= fps <= 60:
        raise ValueError('Invalid video duration or frame rate')
    if not 32 <= width <= 1920 or not 32 <= height <= 1080 or width % 2 or height % 2:
        raise ValueError('Video dimensions must be even and within limits')
    encoder = shutil.which('ffmpeg')
    if not encoder:
        raise RuntimeError('MP4 generation requires local FFmpeg')
    dest = Path(destination).resolve(strict=False)
    dest.parent.mkdir(parents=True, exist_ok=True)
    frame_count = round(duration * fps)
    if frame_count < 1 or frame_count * width * height > 120_000_000:
        raise ValueError('Video frame budget exceeded')
    fd, temp = tempfile.mkstemp(prefix='.omega-video-', suffix='.mp4', dir=dest.parent)
    os.close(fd)
    try:
        cmd = [encoder, '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
               '-f', 'rawvideo', '-pixel_format', 'rgb24', '-video_size', f'{width}x{height}',
               '-framerate', str(fps), '-i', 'pipe:0', '-an', '-c:v', 'mpeg4', '-q:v', '4',
               '-pix_fmt', 'yuv420p', '-movflags', '+faststart', temp]
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE)
        try:
            for frame in range(frame_count):
                cx = width * (0.15 + 0.7 * frame / max(1, frame_count - 1))
                cy = height / 2
                radius = max(4, height // 7)
                pixels = bytearray(width * height * 3)
                for y in range(height):
                    for x in range(width):
                        inside = (x-cx)**2 + (y-cy)**2 <= radius*radius
                        rgb = (212,175,55) if inside else (7,8,10)
                        offset = (y*width+x)*3
                        pixels[offset:offset+3] = bytes(rgb)
                process.stdin.write(pixels)
            process.stdin.close()
            error = process.stderr.read()
            process.wait(timeout=max(20, duration * 3))
            if process.returncode != 0:
                raise RuntimeError('FFmpeg encoding failed: ' + error.decode('utf-8','replace')[-400:])
        except BaseException:
            process.kill()
            process.wait()
            raise
        if not Path(temp).is_file() or Path(temp).stat().st_size < 100:
            raise RuntimeError('FFmpeg produced an invalid output file')
        os.replace(temp, dest)
        return {'path': str(dest), 'bytes': dest.stat().st_size, 'frames': frame_count,
                'fps': fps, 'codec': 'mpeg4', 'container': 'mp4'}
    finally:
        Path(temp).unlink(missing_ok=True)
