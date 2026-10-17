"""A hand-built, deterministic Milestone-0 fixture."""

from __future__ import annotations

import sys
from pathlib import Path

from .audit import audit_table
from .export import export_design
from .model import Command, CommandKind, Design, Thread


def sample_design() -> Design:
    return Design(
        threads=(Thread("#E6194B", "red"), Thread("#4363D8", "blue")),
        commands=(
            Command(CommandKind.STITCH, 0.0, 0.0),
            Command(CommandKind.STITCH, 2.0, 0.0),
            Command(CommandKind.STITCH, 2.0, 2.0),
            Command(CommandKind.COLOR_CHANGE, 2.0, 2.0),
            Command(CommandKind.JUMP, 5.0, 2.0),
            Command(CommandKind.STITCH, 5.0, 4.0),
        ),
    )


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("outputs")
    written = export_design(sample_design(), target, "milestone0")
    print(audit_table([written.dst_path, written.pes_path]))


if __name__ == "__main__":
    main()

