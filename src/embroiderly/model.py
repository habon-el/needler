"""Structured, millimetre-native design data used by every pipeline stage."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CommandKind(str, Enum):
    STITCH = "stitch"
    JUMP = "jump"
    TRIM = "trim"
    COLOR_CHANGE = "color_change"


@dataclass(frozen=True)
class Thread:
    """A thread is positional: its index matches a colour block."""

    hex: str
    description: str = ""

    def __post_init__(self) -> None:
        value = self.hex.lstrip("#")
        if len(value) != 6 or any(char not in "0123456789abcdefABCDEF" for char in value):
            raise ValueError(f"invalid RGB thread colour: {self.hex!r}")


@dataclass(frozen=True)
class Command:
    """One needle command in millimetres, before quantisation."""

    kind: CommandKind
    x_mm: float
    y_mm: float
    region_id: str | None = None


@dataclass(frozen=True)
class Design:
    """An immutable pipeline result; no stage communicates through stdout."""

    commands: tuple[Command, ...]
    threads: tuple[Thread, ...]
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.commands:
            raise ValueError("a design needs at least one command")
        if not self.threads:
            raise ValueError("a design needs at least one thread")
        changes = sum(c.kind is CommandKind.COLOR_CHANGE for c in self.commands)
        if len(self.threads) != changes + 1:
            raise ValueError("thread list must be exactly one plus colour-change count")

