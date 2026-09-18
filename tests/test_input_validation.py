"""Public API regressions for dimensions and bounded raster loading."""

import numpy as np
import pytest

from justpfm.justpfm import read_pfm, write_pfm


@pytest.mark.parametrize("width,height", [(0, 2), (2, 0), (-1, 2), (2, -1), (-1, -1)])
def test_read_rejects_nonpositive_dimensions(tmp_path, width, height):
    path = tmp_path / "invalid.pfm"
    path.write_bytes(f"Pf\n{width} {height}\n-1\n".encode() + b"\0" * 8)
    with pytest.raises(ValueError, match="width and height must be positive"):
        read_pfm(path)


@pytest.mark.parametrize("shape", [(0, 2), (2, 0), (0, 2, 1), (2, 0, 3)])
@pytest.mark.parametrize("existing", [False, True])
def test_write_rejects_empty_images_without_touching_destination(
    tmp_path, shape, existing
):
    path = tmp_path / "image.pfm"
    if existing:
        path.write_bytes(b"original contents")
    with pytest.raises(ValueError, match="invalid shape"):
        write_pfm(path, np.empty(shape, dtype=np.float32))
    if existing:
        assert path.read_bytes() == b"original contents"
    else:
        assert not path.exists()


@pytest.mark.parametrize("identifier,channels", [("Pf", 1), ("PF", 3)])
@pytest.mark.parametrize("delta", [-4, -3, -2, -1, 1, 2, 3, 4])
def test_read_rejects_inexact_payload_sizes(tmp_path, identifier, channels, delta):
    expected = 2 * 3 * channels * 4
    actual = expected + delta
    path = tmp_path / "invalid.pfm"
    path.write_bytes(f"{identifier}\n2 3\n-1\n".encode() + b"\0" * actual)
    with pytest.raises(ValueError, match=f"expected {expected} bytes, got {actual}"):
        read_pfm(path)


@pytest.mark.parametrize("dimensions", ["1000000000000 1000000000000", "1 1"])
def test_invalid_size_is_rejected_before_loading_pixels(
    tmp_path, monkeypatch, dimensions
):
    path = tmp_path / "invalid.pfm"
    path.write_bytes(f"Pf\n{dimensions}\n-1\n".encode())

    def unexpected_read(*args, **kwargs):
        pytest.fail("Malformed payload must be rejected before NumPy allocates pixels")

    monkeypatch.setattr(np, "fromfile", unexpected_read)
    with pytest.raises(ValueError, match="Invalid PFM payload size"):
        read_pfm(path)


def test_detects_file_truncation_during_read(tmp_path, monkeypatch):
    path = tmp_path / "truncated.pfm"
    header = b"Pf\n2 1\n-1\n"
    path.write_bytes(header + b"\0" * 8)
    original_fromfile = np.fromfile

    def truncate_then_read(file, dtype, count):
        with path.open("r+b") as writer:
            writer.truncate(len(header) + 4)
        # Drop bytes buffered while parsing the header, as an actual stream read
        # after concurrent truncation may do.
        position = file.tell()
        file.seek(0)
        file.seek(position)
        return original_fromfile(file, dtype, count=count)

    monkeypatch.setattr(np, "fromfile", truncate_then_read)
    with pytest.raises(ValueError, match="truncated while reading"):
        read_pfm(path)


def test_pixel_read_is_bounded_if_file_grows(tmp_path, monkeypatch):
    path = tmp_path / "growing.pfm"
    path.write_bytes(b"Pf\n2 1\n-1\n" + np.array([1, 2], dtype="<f4").tobytes())
    original_fromfile = np.fromfile

    def append_then_read(file, dtype, count):
        with path.open("ab") as writer:
            writer.write(b"\0" * 100)
        return original_fromfile(file, dtype, count=count)

    monkeypatch.setattr(np, "fromfile", append_then_read)
    result = read_pfm(path)
    np.testing.assert_array_equal(result, np.array([[[1], [2]]], dtype=np.float32))
