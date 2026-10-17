"""Machine-facing metrics calculated only from a file read back from disk."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from pathlib import Path

import pyembroidery

from .export import TENTH_MM, read_written_commands


@dataclass(frozen=True)
class Audit:
    filename: str
    stitch_count: int
    jump_count: int
    trim_count: int
    total_jump_mm: float
    longest_jump_mm: float
    min_stitch_mm: float | None
    max_stitch_mm: float | None

    def table_row(self) -> str:
        minimum = "-" if self.min_stitch_mm is None else f"{self.min_stitch_mm:.2f}"
        maximum = "-" if self.max_stitch_mm is None else f"{self.max_stitch_mm:.2f}"
        return (f"{self.filename:16} {self.stitch_count:7} {self.jump_count:5} "
                f"{self.trim_count:5} {self.total_jump_mm:11.2f} {self.longest_jump_mm:11.2f} "
                f"{minimum:>10} {maximum:>10}")


def audit_file(path: Path) -> Audit:
    """Measure commands after destination-format rounding and writer transforms."""
    prior: tuple[int, int] | None = (0, 0)
    prior_sewn: tuple[int, int] | None = None
    lengths: list[float] = []
    jumps: list[float] = []
    trim_count = 0
    stitch_count = 0
    for x, y, flags in read_written_commands(path):
        command = flags & pyembroidery.COMMAND_MASK
        point = (x, y)
        distance_mm = 0.0 if prior is None else hypot(x - prior[0], y - prior[1]) / TENTH_MM
        if command == pyembroidery.STITCH:
            stitch_count += 1
            # A jump/trim changes needle position without sewing. The first
            # penetration after it has no stitch length to judge, even if a
            # writer represents it as a zero-distance STITCH after a JUMP.
            if distance_mm > 0:
                lengths.append(distance_mm)
            prior_sewn = point
        elif command == pyembroidery.JUMP:
            jumps.append(distance_mm)
            prior_sewn = None
        elif command == pyembroidery.TRIM:
            trim_count += 1
            prior_sewn = None
        elif command == pyembroidery.COLOR_CHANGE:
            prior_sewn = None
        prior = point
    return Audit(
        filename=path.name,
        stitch_count=stitch_count,
        jump_count=len(jumps), trim_count=trim_count,
        total_jump_mm=sum(jumps), longest_jump_mm=max(jumps, default=0.0),
        min_stitch_mm=min(lengths, default=None), max_stitch_mm=max(lengths, default=None),
    )


def audit_table(paths: list[Path]) -> str:
    header = "file             stitches jumps trims jump total  jump max min stitch max stitch"
    return "\n".join([header, *(audit_file(path).table_row() for path in paths)])
