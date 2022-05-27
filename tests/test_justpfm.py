from pathlib import Path

import numpy as np
import pytest
from src.justpfm.justpfm import (
    _get_pfm_channels_from_line,
    _get_pfm_endianness_from_data,
    _get_pfm_identifier_from_data,
    _get_pfm_scale_and_endianness_from_line,
    _get_pfm_width_and_height_from_data,
    _get_pfm_width_and_height_from_line,
    _is_valid_shape,
    read_pfm,
    write_pfm,
)

PFM_TEST_FILE_PATH: Path = Path("test.pfm")

def test_is_valid_shape(get_ones_matrix):
    """Test that a 2D matrix has valid shape"""
    assert _is_valid_shape(get_ones_matrix) is True


def test_is_valid_shape_1_channel(get_ones_matrix_1_channel):
    """Test taht a 1 channel 2D matrix has a valid shape"""
    assert _is_valid_shape(get_ones_matrix_1_channel) is True


def test_is_valid_shape_3_channel(get_ones_matrix_3_channel):
    """Test that a 3 channel 2D matrix has a valid shape"""
    assert _is_valid_shape(get_ones_matrix_3_channel) is True


def test_invalid_shape_1d():
    """Test that a 1D matrix is not a valid shape"""
    assert not _is_valid_shape(np.ones((5), dtype="float32"))


def test_invalid_shape_2_channel(get_ones_matrix_2_channel):
    """Test that a 2 channel 2D matrix does not have a valid shape"""
    assert _is_valid_shape(get_ones_matrix_2_channel) is False


def test_write_pfm_scale_zero(get_ones_matrix):
    """Test that write_pfm raises an exception when scale is 0"""
    with pytest.raises(ValueError):
        write_pfm(PFM_TEST_FILE_PATH, data=get_ones_matrix, scale=0)


def test_write_pfm_invalid_shape(get_ones_matrix_2_channel):
    """Test that write_pfm raises an exception when invalid shape"""
    with pytest.raises(ValueError):
        write_pfm(PFM_TEST_FILE_PATH, get_ones_matrix_2_channel)


def test_get_pfm_identifier_mono(get_ones_matrix):
    """Get the identifier for a 2D matrix"""
    assert _get_pfm_identifier_from_data(get_ones_matrix) == "Pf"


def test_get_pfm_identifier_1_channel(get_ones_matrix_1_channel):
    """Get the identifier for a 1 channel matrix"""
    assert _get_pfm_identifier_from_data(get_ones_matrix_1_channel) == "Pf"


def test_get_pfm_identifier_3_channel(get_ones_matrix_3_channel):
    """Get the identifier for a 3 channel matrix"""
    assert _get_pfm_identifier_from_data(get_ones_matrix_3_channel) == "PF"


def test_get_pfm_width_and_height():
    """Test that the width and height of a matrix is returned properly"""
    data = np.ones((6, 5, 3), dtype="float32")
    width, height = _get_pfm_width_and_height_from_data(data)
    assert width == 5 and height == 6


def test_get_pfm_endianness_is_little_endian_by_default():
    """Test that the default system is little endian"""
    data = np.ones((6, 5, 3))
    assert _get_pfm_endianness_from_data(data) == -1


def test_get_pfm_channels_from_identifier_mono():
    """Test that the Pf identifier returns 1 channel"""
    assert _get_pfm_channels_from_line(("Pf").encode()) == 1


def test_get_pfm_channels_from_identifier_color():
    """Test that the PF identifier returns 3 channels"""
    assert _get_pfm_channels_from_line(("PF").encode()) == 3


def test_get_pfm_channels_from_identifier_invalid():
    """Test that an invalid Pf identifier raises exception"""
    with pytest.raises(ValueError):
        _get_pfm_channels_from_line(("").encode())


def test_get_pfm_width_and_height_from_line_valid():
    """Test that a valid PFM header can be parsed into width and height"""
    width = 6
    height = 5
    assert _get_pfm_width_and_height_from_line(
        ("%d %d\n" % (width, height)).encode()
    ) == (width, height)


def test_get_pfm_width_and_height_from_line_invalid():
    """Test that an invalid PFM header trows an exception"""
    with pytest.raises(ValueError):
        _get_pfm_width_and_height_from_line(("1").encode())


def test_get_pfm_width_and_height_from_line_invalid_text():
    """Test that an invalid PFM header trows an exception"""
    with pytest.raises(ValueError):
        _get_pfm_width_and_height_from_line(("blah blah").encode())


def test_get_pfm_scale_and_endianness_from_line_positive():
    """Test that a valid scale big endian can be parsed from the PFM header"""
    assert _get_pfm_scale_and_endianness_from_line(("1.0").encode()) == (1.0, ">")


def test_get_pfm_scale_and_endianness_from_line_negative():
    """Test that a valid scale little endian can be parsed from the PFM header"""
    assert _get_pfm_scale_and_endianness_from_line(("-1.0").encode()) == (1.0, "<")


def test_get_pfm_scale_and_endianness_from_line_invalid():
    """Test that an invalid scale raises an exception"""
    with pytest.raises(ValueError):
        _get_pfm_scale_and_endianness_from_line(("0.0").encode())


def test_write_pfm_invalid_type():
    """Test that an invalid type matrix rises an exception"""
    with pytest.raises(ValueError):
        write_pfm(PFM_TEST_FILE_PATH, np.ones((5, 5), dtype="float64"))


def test_write_and_read_pfm(get_ones_matrix_1_channel):
    """Test write pfm"""
    write_pfm(PFM_TEST_FILE_PATH, get_ones_matrix_1_channel, 1.0)
    data = read_pfm(PFM_TEST_FILE_PATH)
    data_comparison = data == get_ones_matrix_1_channel
    PFM_TEST_FILE_PATH.unlink(missing_ok=True)
    assert data_comparison.all()


def test_write_and_read_pfm_scale(get_ones_matrix_1_channel):
    """Test write pfm"""
    write_pfm(PFM_TEST_FILE_PATH, get_ones_matrix_1_channel, 0.5)
    data = read_pfm(PFM_TEST_FILE_PATH)
    data_comparison = data == get_ones_matrix_1_channel * 0.5
    PFM_TEST_FILE_PATH.unlink(missing_ok=True)
    assert data_comparison.all()
