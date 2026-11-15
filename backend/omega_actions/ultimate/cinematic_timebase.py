"""Exact AV timeline arithmetic based on the OCG Rational Timebase contract.

All time and sample boundaries use integer/Fraction arithmetic. This module
provides a reusable domain primitive; it does not generate speech or video.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import gcd


class TimelineError(ValueError):
    """Invalid or unsafe timebase input."""


def _positive_int(value: int, field: str) -> int:
    if type(value) is not int or value <= 0:
        raise TimelineError(f"{field} must be a positive integer")
    return value


@dataclass(frozen=True, slots=True)
class FrameRate:
    """Frame rate expressed as the reduced rational numerator/denominator.

    E.g., FrameRate(30000, 1001) is NTSC 29.97, not floating-point 29.97.
    Audio sample boundaries are derived from the *absolute frame index*, never
    by repeatedly adding a rounded per-frame length.
    """

    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        n = _positive_int(self.numerator, "numerator")
        d = _positive_int(self.denominator, "denominator")
        divisor = gcd(n, d)
        object.__setattr__(self, "numerator", n // divisor)
        object.__setattr__(self, "denominator", d // divisor)

    def frame_time(self, frame_index: int) -> Fraction:
        if type(frame_index) is not int or frame_index < 0:
            raise TimelineError("frame_index must be a non-negative integer")
        return Fraction(frame_index * self.denominator, self.numerator)

    def audio_sample_at(self, frame_index: int, sample_rate: int = 48000) -> int:
        """Nearest integer sample using exact half-up rounding at frame boundary."""
        _positive_int(sample_rate, "sample_rate")
        self.frame_time(frame_index)  # validates index with no float round-trip
        a = frame_index * sample_rate * self.denominator
        b = self.numerator
        return (2 * a + b) // (2 * b)

    def audio_sample_window(
        self, frame_index: int, sample_rate: int = 48000, *, end_frame: int | None = None
    ) -> tuple[int, int]:
        if end_frame is None:
            if type(frame_index) is not int or frame_index < 0:
                raise TimelineError("frame_index must be a non-negative integer")
            end_frame = frame_index + 1
        if type(end_frame) is not int or end_frame <= frame_index:
            raise TimelineError("end_frame must be an integer greater than frame_index")
        start = self.audio_sample_at(frame_index, sample_rate)
        end = self.audio_sample_at(end_frame, sample_rate)
        return start, end
