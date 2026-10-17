from pathlib import Path

from embroiderly.audit import audit_file
from embroiderly.demo import sample_design
from embroiderly.export import export_design, read_written_commands


def test_dst_and_pes_are_written_and_readable(tmp_path: Path) -> None:
    result = export_design(sample_design(), tmp_path, "sample")
    assert result.dst_path.stat().st_size > 512
    assert result.pes_path.stat().st_size > 512
    assert read_written_commands(result.dst_path)[-1][2] != 0
    assert read_written_commands(result.pes_path)[-1][2] != 0


def test_export_is_byte_identical_for_same_input(tmp_path: Path) -> None:
    first = export_design(sample_design(), tmp_path / "first", "sample")
    second = export_design(sample_design(), tmp_path / "second", "sample")
    assert first.dst_path.read_bytes() == second.dst_path.read_bytes()
    assert first.pes_path.read_bytes() == second.pes_path.read_bytes()


def test_audit_reads_written_grid_not_source_floats(tmp_path: Path) -> None:
    result = export_design(sample_design(), tmp_path, "sample")
    dst = audit_file(result.dst_path)
    assert dst.jump_count == 1
    assert dst.total_jump_mm == 3.0
    assert dst.trim_count == 1  # Explicit cut after the colour change.
    assert dst.min_stitch_mm == 2.0
