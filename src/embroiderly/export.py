"""The sole binary-format boundary. pyembroidery owns every file byte."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pyembroidery

from .model import Command, CommandKind, Design

TENTH_MM = 10


def snap_mm(value: float) -> int:
    """Quantise a millimetre coordinate onto the written-file 0.1 mm grid."""
    # Decimal-free round is deterministic for finite normal input; geometry later
    # operates upstream in mm and reaches this conversion only here.
    return int(round(value * TENTH_MM))


_COMMAND_CODE = {
    CommandKind.STITCH: pyembroidery.STITCH,
    CommandKind.JUMP: pyembroidery.JUMP,
    CommandKind.TRIM: pyembroidery.TRIM,
    CommandKind.COLOR_CHANGE: pyembroidery.COLOR_CHANGE,
}


@dataclass(frozen=True)
class ExportResult:
    dst_path: Path
    pes_path: Path


def _pattern(design: Design) -> pyembroidery.EmbPattern:
    pattern = pyembroidery.EmbPattern()
    for thread in design.threads:
        pattern.add_thread(thread.hex)
    for command in design.commands:
        pattern.add_stitch_absolute(
            _COMMAND_CODE[command.kind], snap_mm(command.x_mm), snap_mm(command.y_mm)
        )
    return pattern


def export_design(design: Design, output_dir: Path, stem: str) -> ExportResult:
    """Write DST and PES using pyembroidery; formats are never encoded here."""
    output_dir.mkdir(parents=True, exist_ok=True)
    dst_path = output_dir / f"{stem}.dst"
    pes_path = output_dir / f"{stem}.pes"
    pattern = _pattern(design)
    from .machine_files import write_pair
    write_pair(pattern, pes_path, dst_path)
    return ExportResult(dst_path=dst_path, pes_path=pes_path)


def read_written_commands(path: Path) -> tuple[tuple[int, int, int], ...]:
    """Read the command stream back from disk in pyembroidery's 0.1 mm units."""
    from .machine_files import read_pattern
    return tuple(tuple(stitch) for stitch in read_pattern(path).stitches)
