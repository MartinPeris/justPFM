"""Exercise public I/O against independent PFM bytes, not just round trips."""

import struct
from sys import byteorder

import numpy as np
import pytest

from justpfm.justpfm import (
    _get_pfm_endianness_from_data,
    read_pfm,
    write_pfm,
)


@pytest.mark.parametrize("shape", [(2, 3), (2, 3, 1), (2, 3, 3)])
@pytest.mark.parametrize("scale", [1.0, 0.5, 2.0])
def test_nonuniform_round_trip(tmp_path, shape, scale):
    data = np.arange(np.prod(shape), dtype="float32").reshape(shape) - 4.5
    original = data.copy()
    path = tmp_path / "image.pfm"

    write_pfm(path, data, scale)
    result = read_pfm(path)

    expected = (data * scale).reshape(2, 3, -1)
    assert result.shape == expected.shape
    assert result.dtype.kind == "f" and result.dtype.itemsize == 4
    np.testing.assert_array_equal(result, expected)
    np.testing.assert_array_equal(data, original)


@pytest.mark.parametrize("channels,identifier", [(1, b"Pf"), (3, b"PF")])
@pytest.mark.parametrize("endian,sign", [("<", -1), (">", 1)])
@pytest.mark.parametrize("scale", [1.0, 0.25])
def test_read_independent_file(tmp_path, channels, identifier, endian, sign, scale):
    # File rows are bottom-to-top; channel values are interleaved.
    values = [float(i) - 2.5 for i in range(6 * channels)]
    header = identifier + b"\n3 2\n" + str(sign * scale).encode() + b"\n"
    path = tmp_path / "independent.pfm"
    path.write_bytes(header + struct.pack(endian + "f" * len(values), *values))

    expected = np.array(values, dtype="float32").reshape(2, 3, channels)[::-1]
    np.testing.assert_array_equal(read_pfm(path), expected * scale)


@pytest.mark.parametrize("shape,identifier", [((2, 3), b"Pf"), ((2, 3, 3), b"PF")])
def test_writer_header_and_pixel_order(tmp_path, shape, identifier):
    data = np.arange(np.prod(shape), dtype="float32").reshape(shape)
    path = tmp_path / "written.pfm"
    write_pfm(path, data, scale=0.5)

    magic, dimensions, scale_line, payload = path.read_bytes().split(b"\n", 3)
    assert magic == identifier
    assert dimensions == b"3 2"
    assert float(scale_line) == (-0.5 if byteorder == "little" else 0.5)
    endian = "<" if byteorder == "little" else ">"
    values = struct.unpack(endian + "f" * data.size, payload)
    assert values == tuple(data[::-1].ravel())


@pytest.mark.parametrize("endian,expected", [("<", -1), (">", 1)])
def test_explicit_array_byte_order(endian, expected):
    assert (
        _get_pfm_endianness_from_data(np.ones((2, 3), dtype=endian + "f4")) == expected
    )


@pytest.mark.parametrize("shape", [(), (3,), (2, 3, 2), (2, 3, 4), (2, 3, 1, 1)])
def test_reject_invalid_shapes_without_creating_file(tmp_path, shape):
    path = tmp_path / "invalid.pfm"
    with pytest.raises(ValueError, match="invalid shape"):
        write_pfm(path, np.ones(shape, dtype="float32"))
    assert not path.exists()


@pytest.mark.parametrize("dtype", ["float64", "int32", "uint8"])
def test_reject_invalid_dtype_without_creating_file(tmp_path, dtype):
    path = tmp_path / "invalid.pfm"
    with pytest.raises(ValueError, match="must be float32"):
        write_pfm(path, np.ones((2, 3), dtype=dtype))
    assert not path.exists()


@pytest.mark.parametrize(
    "contents",
    [
        b"",
        b"P6\n3 2\n-1\n",
        b"Pf\n3\n-1\n",
        b"Pf\nwidth height\n-1\n",
        b"Pf\n3 2\n0\n",
        b"Pf\n3 2\ninvalid\n",
        b"Pf\n3 2\n-1\n",  # Missing pixels.
        b"Pf\n3 2\n-1\n" + struct.pack("<5f", *range(5)),
        b"Pf\n3 2\n-1\n" + struct.pack("<7f", *range(7)),
    ],
)
def test_reject_malformed_file(tmp_path, contents):
    path = tmp_path / "invalid.pfm"
    path.write_bytes(contents)
    with pytest.raises(ValueError):
        read_pfm(path)


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_pfm(tmp_path / "missing.pfm")


def test_noncontiguous_input(tmp_path):
    data = np.arange(24, dtype="float32").reshape(4, 6)[::2, ::2]
    assert not data.flags.c_contiguous
    path = tmp_path / "strided.pfm"
    write_pfm(path, data)
    np.testing.assert_array_equal(read_pfm(path)[..., 0], data)


def test_special_pixel_values(tmp_path):
    data = np.array([[np.nan, np.inf, -np.inf], [-0.0, 1.5, -2.5]], dtype="float32")
    path = tmp_path / "special.pfm"
    write_pfm(path, data)
    result = read_pfm(path)[..., 0]
    np.testing.assert_array_equal(result, data)
    assert np.signbit(result[1, 0])
