"""Documented imports, path inputs, and output memory contract."""

import numpy as np
import pytest

from justpfm import justpfm, read_pfm, write_pfm


def test_public_exports_preserve_legacy_imports():
    assert read_pfm is justpfm.read_pfm
    assert write_pfm is justpfm.write_pfm


@pytest.mark.parametrize("as_string", [False, True])
@pytest.mark.parametrize("endian", ["<", ">"])
def test_output_layout_and_path_inputs(tmp_path, as_string, endian):
    path = tmp_path / "contract.pfm"
    filename = str(path) if as_string else path
    pixels = np.arange(12, dtype=np.float32).reshape(3, 4).astype(endian + "f4")
    assert write_pfm(filename, pixels) is None
    result = read_pfm(filename)
    assert result.shape == (3, 4, 1)
    assert result.dtype == np.dtype(endian + "f4")
    assert result.strides[0] < 0
    assert not result.flags.c_contiguous
    np.testing.assert_array_equal(result[..., 0], pixels)
    contiguous = np.ascontiguousarray(result, dtype=np.float32)
    assert contiguous.flags.c_contiguous
    assert contiguous.dtype.isnative
    np.testing.assert_array_equal(contiguous, result)
