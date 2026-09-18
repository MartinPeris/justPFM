"""In-memory codecs agree with independent PFM bytes and filesystem contracts."""

import struct
from pathlib import Path

import numpy as np
import pytest

from justpfm import decode_pfm, encode_pfm, justpfm, read_pfm, write_pfm


@pytest.mark.parametrize("shape", [(3, 5), (3, 5, 1), (3, 5, 3)])
@pytest.mark.parametrize("endian", ["<", ">"])
@pytest.mark.parametrize("scale", [0.5, 1, 2])
@pytest.mark.parametrize("layout", ["c", "fortran", "reversed", "strided"])
def test_codec_binary_oracle_and_file_equivalence(
    tmp_path, shape, endian, scale, layout
):
    data = (
        np.arange(np.prod(shape), dtype=np.float32).reshape(shape).astype(endian + "f4")
    )
    if layout == "fortran":
        data = np.asfortranarray(data)
    elif layout == "reversed":
        data = data[::-1, ::-1]
    elif layout == "strided":
        data = data[:, ::2]
    original = data.tobytes()
    data.flags.writeable = False
    height, width = data.shape[:2]
    magic = "PF" if len(shape) == 3 and shape[2] == 3 else "Pf"
    signed_scale = -scale if endian == "<" else scale
    header = f"{magic}\n{width} {height}\n{signed_scale}\n".encode()
    values = [float(v) for row in reversed(data) for v in row.flat]
    expected = header + struct.pack(endian + str(data.size) + "f", *values)
    encoded = encode_pfm(data, scale=scale)
    assert isinstance(encoded, bytes)
    assert encoded == expected
    assert data.tobytes() == original
    path = tmp_path / "image.pfm"
    write_pfm(path, data, scale=scale)
    assert path.read_bytes() == encoded
    decoded = decode_pfm(expected, max_pixels=height * width)
    assert decoded.shape == (height, width, 3 if magic == "PF" else 1)
    assert decoded.dtype == np.dtype(endian + "f4")
    assert decoded.flags.writeable
    assert decoded.strides[0] < 0
    np.testing.assert_array_equal(decoded, (data * scale).reshape(decoded.shape))
    np.testing.assert_array_equal(decoded, read_pfm(path))


@pytest.mark.parametrize("factory", [bytes, bytearray])
@pytest.mark.parametrize("scale", [1, 2])
@pytest.mark.parametrize("endian", ["<", ">"])
def test_decoded_pixels_are_independent_and_always_writable(factory, scale, endian):
    signed_scale = -scale if endian == "<" else scale
    payload = factory(
        f"Pf\n2 1\n{signed_scale}\n".encode() + struct.pack(endian + "2f", 1, 2)
    )
    before = bytes(payload)
    first = decode_pfm(payload)
    second = decode_pfm(payload)
    first[...] = 99
    assert bytes(payload) == before
    if isinstance(payload, bytearray):
        payload[:] = b"changed"  # No exported view survives to prevent resizing.
    np.testing.assert_array_equal(second[..., 0], [[scale, 2 * scale]])
    second[...] = -1
    assert np.all(first == 99)


@pytest.mark.parametrize("payload", [None, "Pf\n1 1\n-1\n", 123, memoryview(b"x")])
def test_decode_rejects_unsupported_types(payload):
    with pytest.raises(TypeError, match="bytes or bytearray"):
        decode_pfm(payload)


@pytest.mark.parametrize("limit", [True, False, 0, -1, 1.0, "2", np.int64(2)])
def test_decode_rejects_invalid_limits(limit):
    with pytest.raises(ValueError, match="max_pixels"):
        decode_pfm(b"", max_pixels=limit)


@pytest.mark.parametrize(
    "contents",
    [
        b"",
        b"Pf",
        b"Pf\n",
        b"Pf\n1 1",
        b"Pf\n1 1\n-1",
        b"PX\n1 1\n-1\n",
        b"Pf\n0 1\n-1\n",
        b"Pf\n-1 1\n-1\n",
        b"Pf\n1 1 1\n-1\n",
        b"Pf\n1 1\n0\n",
        b"Pf\n1 1\nnan\n",
        b"Pf\n1 1\ninf\n",
        b"Pf\n1 1\n-1\n",
        b"Pf\n1 1\n-1\nxxx",
        b"Pf\n1 1\n-1\n" + b"\0" * 5,
        b"Pf\n1000000000000 1000000000000\n-1\n",
    ],
)
def test_malformed_bytes_match_file_errors_before_pixel_allocation(
    tmp_path, monkeypatch, contents
):
    path = tmp_path / "invalid.pfm"
    path.write_bytes(contents)
    with pytest.raises(ValueError) as file_error:
        read_pfm(path)

    def unexpected_allocation(*args, **kwargs):
        pytest.fail("Invalid data must be rejected before raster allocation")

    monkeypatch.setattr(np, "frombuffer", unexpected_allocation)
    with pytest.raises(ValueError) as byte_error:
        decode_pfm(contents)
    assert str(byte_error.value) == str(file_error.value)


@pytest.mark.parametrize("index", [0, 1, 2, None])
@pytest.mark.parametrize("length", [4096, 4097])
def test_decode_header_boundaries(index, length):
    lines = [b"Pf", b"1 1", b"-1"]
    for i in range(3):
        if index is None or index == i:
            lines[i] += b" " * (length - len(lines[i]) - 1)
    payload = b"\n".join(lines) + b"\n" + struct.pack("<f", 2)
    if length == 4097:
        with pytest.raises(ValueError, match="header line exceeds"):
            decode_pfm(payload)
    else:
        np.testing.assert_array_equal(decode_pfm(payload), [[[2]]])


def test_decode_limit_precedes_allocation_and_counts_pixels(monkeypatch):
    payload = b"PF\r\n3 2\r\n-1\r\n" + b"\0" * 72
    assert decode_pfm(payload, max_pixels=6).shape == (2, 3, 3)

    def unexpected_allocation(*args, **kwargs):
        pytest.fail("Pixel limit must precede raster allocation")

    monkeypatch.setattr(np, "frombuffer", unexpected_allocation)
    with pytest.raises(ValueError, match="exceeds max_pixels"):
        decode_pfm(payload, max_pixels=5)


@pytest.mark.parametrize("dtype", ["<f4", ">f4"])
def test_nonfinite_pixel_bits_and_scale_tolerance(dtype):
    bits = np.array(
        [0, 0x80000000, 0x7FC00001, 0x7F800001, 0x7F800000, 0xFF800000],
        dtype=dtype[0] + "u4",
    )
    data = bits.view(dtype).reshape(2, 3)
    encoded = encode_pfm(data, scale=1 + 1e-10)
    result = decode_pfm(encoded)
    assert result.dtype == data.dtype
    assert result[..., 0].tobytes() == data.tobytes()
    assert encoded.split(b"\n", 3)[3] == data[::-1].tobytes()


@pytest.mark.parametrize("scale", [0, -1, np.nan, np.inf, -np.inf])
def test_encoder_rejects_invalid_scale(scale):
    with pytest.raises(ValueError, match="scale must be positive and finite"):
        encode_pfm(np.ones((2, 3), dtype=np.float32), scale=scale)


@pytest.mark.parametrize(
    "data",
    [
        np.ones((2, 3), dtype=np.float64),
        np.ones((2, 3, 2), dtype=np.float32),
        np.empty((0, 3), dtype=np.float32),
    ],
)
def test_encoder_rejects_invalid_pixels(data):
    with pytest.raises(ValueError):
        encode_pfm(data)


def test_codecs_do_not_use_filesystem(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("In-memory codecs must not use filesystem I/O")

    monkeypatch.setattr(justpfm, "open", forbidden, raising=False)
    monkeypatch.setattr(justpfm, "NamedTemporaryFile", forbidden)
    monkeypatch.setattr(np, "fromfile", forbidden)
    data = np.ones((2, 3), dtype=np.float32)
    np.testing.assert_array_equal(decode_pfm(encode_pfm(data))[..., 0], data)


@pytest.mark.parametrize(
    "path",
    sorted((Path(__file__).parent / "fixtures/netpbm").glob("*.pfm")),
    ids=lambda p: p.name,
)
def test_decode_independent_netpbm_fixtures(path):
    np.testing.assert_array_equal(decode_pfm(path.read_bytes()), read_pfm(path))
