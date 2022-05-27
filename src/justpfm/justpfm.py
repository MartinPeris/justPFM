"""A small Python module to read/write PFM (Portable Float Map) images"""

from math import isclose
from pathlib import Path
from sys import byteorder
from typing import Tuple

import numpy as np


def write_pfm(file_name: Path, data: np.ndarray, scale: float = 1) -> None:
    """
    Writes the data into the file in PFM format
    """
    if isclose(scale, 0.0):
        raise ValueError("0 is not a valid value for scale")
    if not _is_valid_shape(data):
        raise ValueError("data has invalid shape: " + str(data.shape))
    if data.dtype != "float32":
        raise ValueError("data must be float32: " + str(data.dtype))

    identifier = _get_pfm_identifier_from_data(data)
    width, height = _get_pfm_width_and_height_from_data(data)
    flipped_data = np.flipud(data)
    scale *= _get_pfm_endianness_from_data(data)

    with open(file_name, "wb") as file:
        file.write(identifier.encode())
        file.write((f"\n{width} {height}\n").encode())
        file.write((f"{scale}\n").encode())
        flipped_data.tofile(file)


def _get_pfm_identifier_from_data(data: np.ndarray) -> str:
    """Get the pfm identifier depending on the number of channels on the
    data object
    """
    identifier = "Pf"
    if len(data.shape) == 3 and data.shape[2] == 3:
        identifier = "PF"
    return identifier


def _is_valid_shape(data: np.ndarray) -> bool:
    """Return true if the shape of the data is valid"""
    if len(data.shape) == 2:
        return True

    if len(data.shape) == 3:
        if data.shape[2] == 1 or data.shape[2] == 3:
            return True
    return False


def _get_pfm_width_and_height_from_data(data: np.ndarray) -> Tuple[int, int]:
    """Return the width and height of the matrix in the proper order"""
    height, width = data.shape[:2]
    return width, height


def _get_pfm_endianness_from_data(data: np.ndarray) -> float:
    """Return 1 if bigendian, -1 if little endian data"""
    endianness = data.dtype.byteorder
    return (
        -1 if endianness == "<" or (endianness == "=" and byteorder == "little") else 1
    )


def read_pfm(file_name: Path) -> np.ndarray:
    """Read a file in PFM format into data"""
    with open(file_name, "rb") as file:
        channels = _get_pfm_channels_from_line(file.readline())
        width, height = _get_pfm_width_and_height_from_line(file.readline())
        scale, endianness = _get_pfm_scale_and_endianness_from_line(file.readline())
        data = np.fromfile(file, endianness + "f")
        shape = (height, width, channels)
        data = np.reshape(data, shape)
        data = np.flipud(data)
        if not isclose(scale, 1.0):
            data *= scale
        return data


def _get_pfm_channels_from_line(line: bytes) -> int:
    """Returns the number of channels of the data based on the PFM identifier"""
    identifier = line.rstrip().decode("UTF-8")
    channels = 0
    if identifier == "Pf":
        channels = 1
    elif identifier == "PF":
        channels = 3
    else:
        raise ValueError("Not a valid PFM identifier")
    return channels


def _get_pfm_width_and_height_from_line(line: bytes) -> Tuple[int, int]:
    """Parses the width and height from the PFM header"""
    decoded_line = line.rstrip().decode("UTF-8")
    items = decoded_line.split()
    if len(items) == 2:
        width = int(items[0])
        height = int(items[1])
    else:
        raise ValueError("Not a valid PFM header")
    return width, height


def _get_pfm_scale_and_endianness_from_line(line: bytes) -> Tuple[float, str]:
    """Parse the scale and endianness from the PFM header"""
    decoded_line = line.rstrip().decode("UTF-8")
    scale = float(decoded_line)
    if isclose(scale, 0.0):
        raise ValueError("0 is not a valid value for scale")
    endianness = ""
    if scale < 0:
        endianness = "<"
        scale = -scale
    else:
        endianness = ">"
    return scale, endianness
