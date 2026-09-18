"""Bounded header parsing and opt-in pixel allocation limits."""

from io import BytesIO

import numpy as np
import pytest

from justpfm import justpfm, read_pfm


@pytest.mark.parametrize("line_index", [0, 1, 2])
@pytest.mark.parametrize("length", [4096, 4097])
def test_header_line_length_boundary(tmp_path, line_index, length):
    lines = [b"Pf", b"1 1", b"-1"]
    lines[line_index] += b" " * (length - len(lines[line_index]) - 1)
    path = tmp_path / "header.pfm"
    path.write_bytes(b"\n".join(lines) + b"\n" + b"\0" * 4)
    if length == 4096:
        np.testing.assert_array_equal(read_pfm(path), np.zeros((1, 1, 1)))
    else:
        with pytest.raises(ValueError, match="header line exceeds 4096 bytes"):
            read_pfm(path)


@pytest.mark.parametrize("contents", [b"", b"Pf", b"Pf\n", b"Pf\n1 1", b"Pf\n1 1\n-1"])
def test_truncated_header(tmp_path, contents):
    path = tmp_path / "truncated.pfm"
    path.write_bytes(contents)
    with pytest.raises(ValueError, match="Truncated PFM header: missing newline"):
        read_pfm(path)


@pytest.mark.parametrize("prefix", [b"", b"Pf\n", b"Pf\n1 1\n"])
def test_unterminated_large_header_uses_bounded_reads(monkeypatch, prefix):
    read_lengths = []

    class ObservedFile(BytesIO):
        def readline(self, size=-1):
            assert 0 < size <= 4097
            line = super().readline(size)
            read_lengths.append(len(line))
            return line

    file = ObservedFile(prefix + b"9" * 100_000)
    monkeypatch.setattr(justpfm, "open", lambda *args: file, raising=False)
    with pytest.raises(ValueError, match="header line exceeds 4096 bytes"):
        read_pfm("untrusted.pfm")
    assert max(read_lengths) == 4097
    assert sum(read_lengths) <= len(prefix) + 4097
    assert file.closed


@pytest.mark.parametrize("limit", [True, False, 0, -1, 1.0, "2", np.int64(2), []])
def test_invalid_limit_rejected_before_open(tmp_path, limit):
    with pytest.raises(
        ValueError, match="max_pixels must be a positive integer or None"
    ):
        read_pfm(tmp_path / "missing.pfm", max_pixels=limit)


@pytest.mark.parametrize("identifier,channels", [("Pf", 1), ("PF", 3)])
@pytest.mark.parametrize("limit", [None, 6, 7])
def test_pixel_limit_accepts_boundary_and_counts_pixels(
    tmp_path, identifier, channels, limit
):
    path = tmp_path / "allowed.pfm"
    path.write_bytes(f"{identifier}\n3 2\n-1\n".encode() + b"\0" * (6 * channels * 4))
    result = read_pfm(path, max_pixels=limit)
    assert result.shape == (2, 3, channels)
    assert not result.any()


@pytest.mark.parametrize("dimensions", ["3 2", "1000000000000 1000000000000"])
def test_exceeded_limit_precedes_raster_allocation(tmp_path, monkeypatch, dimensions):
    path = tmp_path / "oversized.pfm"
    path.write_bytes(f"Pf\n{dimensions}\n-1\n".encode() + b"\0" * 24)

    def unexpected_allocation(*args, **kwargs):
        pytest.fail("Over-limit images must be rejected before raster allocation")

    monkeypatch.setattr(np, "fromfile", unexpected_allocation)
    with pytest.raises(ValueError, match="exceeds max_pixels limit of 5"):
        read_pfm(path, max_pixels=5)


def test_crlf_header_remains_supported(tmp_path):
    path = tmp_path / "crlf.pfm"
    path.write_bytes(b"Pf\r\n1 1\r\n-1\r\n" + b"\0" * 4)
    assert read_pfm(path, max_pixels=1).shape == (1, 1, 1)
