"""Regressions for scale validation and portable float32 byte order."""

import struct

import numpy as np
import pytest

from justpfm.justpfm import read_pfm, write_pfm


@pytest.mark.parametrize("scale", [-1.0, -0.5, 0.0, -0.0, np.nan, np.inf, -np.inf])
@pytest.mark.parametrize("existing", [False, True])
def test_invalid_write_scale_preserves_destination(tmp_path, scale, existing):
    path = tmp_path / "image.pfm"
    if existing:
        path.write_bytes(b"existing image")
    with pytest.raises(ValueError, match="scale must be positive and finite"):
        write_pfm(path, np.array([[1, 2]], dtype="float32"), scale=scale)
    if existing:
        assert path.read_bytes() == b"existing image"
    else:
        assert not path.exists()


@pytest.mark.parametrize("scale", [b"nan", b"NaN", b"inf", b"-inf", b"0", b"-0"])
def test_invalid_header_scale(tmp_path, scale):
    path = tmp_path / "invalid.pfm"
    path.write_bytes(b"Pf\n1 1\n" + scale + b"\n" + struct.pack("<f", 1))
    with pytest.raises(ValueError, match="PFM scale must be finite and nonzero"):
        read_pfm(path)


@pytest.mark.parametrize("endian,sign", [("<", -1), (">", 1)])
@pytest.mark.parametrize("shape", [(2, 3), (2, 3, 1), (2, 3, 3)])
@pytest.mark.parametrize("scale", [0.5, 1.0, 2.0])
def test_write_explicit_byte_order(tmp_path, endian, sign, shape, scale):
    data = (np.arange(np.prod(shape)).reshape(shape) - 4.5).astype(endian + "f4")
    original = data.copy()
    path = tmp_path / "image.pfm"

    write_pfm(path, data, scale=scale)

    identifier, dimensions, scale_line, payload = path.read_bytes().split(b"\n", 3)
    assert identifier == (b"PF" if shape == (2, 3, 3) else b"Pf")
    assert dimensions == b"3 2"
    assert float(scale_line) == sign * scale
    assert struct.unpack(endian + "f" * data.size, payload) == tuple(data[::-1].ravel())
    np.testing.assert_array_equal(read_pfm(path), (data * scale).reshape(2, 3, -1))
    np.testing.assert_array_equal(data, original)
    assert data.dtype == original.dtype


@pytest.mark.parametrize("endian,scale", [("<", b"-1"), (">", b"1")])
def test_rewrite_independent_file(tmp_path, endian, scale):
    source = tmp_path / "source.pfm"
    destination = tmp_path / "copy.pfm"
    contents = b"Pf\n3 2\n" + scale + b"\n" + struct.pack(endian + "6f", *range(6))
    source.write_bytes(contents)

    write_pfm(destination, read_pfm(source))

    assert destination.read_bytes() == contents


@pytest.mark.parametrize("endian", ["<", ">"])
def test_nonfinite_pixels_remain_supported(tmp_path, endian):
    data = np.array([[np.nan, np.inf, -np.inf]], dtype=endian + "f4")
    path = tmp_path / "pixels.pfm"
    write_pfm(path, data)
    np.testing.assert_array_equal(read_pfm(path)[..., 0], data)
