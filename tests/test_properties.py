"""Generated public API invariants and independently encoded PFM fixtures."""

import struct
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from justpfm import read_pfm, write_pfm


@st.composite
def images(draw):
    height = draw(st.integers(1, 8))
    width = draw(st.integers(1, 8))
    channels = draw(st.sampled_from([1, 3]))
    values = draw(
        st.lists(
            st.floats(-1e6, 1e6, width=32, allow_subnormal=False),
            min_size=height * width * channels,
            max_size=height * width * channels,
        )
    )
    return np.array(values, dtype=np.float32).reshape(height, width, channels)


@given(
    pixels=images(),
    endian=st.sampled_from(["<", ">"]),
    scale=st.floats(0.125, 8, width=32),
    squeeze=st.booleans(),
    reverse=st.booleans(),
)
def test_generated_round_trips(pixels, endian, scale, squeeze, reverse):
    pixels = pixels.astype(endian + "f4")
    if reverse:
        pixels = pixels[::-1, ::-1]
    source = pixels[..., 0] if squeeze and pixels.shape[2] == 1 else pixels
    with TemporaryDirectory() as directory:
        path = Path(directory) / "roundtrip.pfm"
        write_pfm(path, source, scale=scale)
        result = read_pfm(path)
    assert result.shape == pixels.shape
    assert result.dtype == np.dtype(endian + "f4")
    # Compute the oracle at higher precision, independently of in-place scaling.
    expected = pixels.astype(np.float64) * scale
    np.testing.assert_allclose(result, expected, rtol=1e-6, atol=1e-37)


@given(
    pixels=images(),
    endian=st.sampled_from(["<", ">"]),
    scale=st.sampled_from([0.5, 1, 2]),
)
def test_reader_against_independent_binary_encoder(pixels, endian, scale):
    height, width, channels = pixels.shape
    identifier = "Pf" if channels == 1 else "PF"
    signed_scale = -scale if endian == "<" else scale
    header = f"{identifier}\n{width} {height}\n{signed_scale}\n".encode()
    samples = [float(value) for row in reversed(pixels) for value in row.flat]
    payload = struct.pack(endian + "f" * len(samples), *samples)
    with TemporaryDirectory() as directory:
        path = Path(directory) / "independent.pfm"
        path.write_bytes(header + payload)
        result = read_pfm(path)
    np.testing.assert_array_equal(result, pixels * scale)


@given(
    width=st.integers(1, 16),
    height=st.integers(1, 16),
    channels=st.sampled_from([1, 3]),
    delta=st.integers(-4, 12).filter(lambda value: value != 0),
    suffix=st.binary(min_size=1, max_size=8),
)
def test_malformed_payload_lengths(width, height, channels, delta, suffix):
    identifier = "Pf" if channels == 1 else "PF"
    length = width * height * channels * 4 + delta
    payload = (suffix * (length // len(suffix) + 1))[:length]
    with TemporaryDirectory() as directory:
        path = Path(directory) / "malformed.pfm"
        path.write_bytes(f"{identifier}\n{width} {height}\n-1\n".encode() + payload)
        with pytest.raises(ValueError, match="Invalid PFM payload size"):
            read_pfm(path)
