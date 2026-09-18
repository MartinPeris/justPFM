"""A small Python module to read/write PFM (Portable Float Map) images"""

from math import isclose, isfinite
from os import chmod, fstat, replace
from pathlib import Path
from stat import S_IMODE, S_ISREG
from sys import byteorder
from tempfile import NamedTemporaryFile
from typing import Tuple

import numpy as np


def write_pfm(file_name: Path, data: np.ndarray, scale: float = 1) -> None:
    """
    Write PFM data, atomically replacing the destination after closing the file.

    A sibling temporary file is removed on failure, preserving any existing
    destination. Existing regular file permissions are preserved; new files
    have private permissions (0600 on POSIX). A destination symlink is replaced,
    leaving its target intact. Other metadata, including ownership, is not copied.
    Atomic replacement does not guarantee durability after a power failure.
    """
    if not isfinite(scale) or scale <= 0:
        raise ValueError("scale must be positive and finite")
    if not _is_valid_shape(data):
        raise ValueError("data has invalid shape: " + str(data.shape))
    if data.dtype.kind != "f" or data.dtype.itemsize != 4:
        raise ValueError("data must be float32: " + str(data.dtype))

    identifier = _get_pfm_identifier_from_data(data)
    width, height = _get_pfm_width_and_height_from_data(data)
    flipped_data = np.flipud(data)
    scale *= _get_pfm_endianness_from_data(data)

    destination = Path(file_name)
    temporary = NamedTemporaryFile(
        mode="wb", dir=destination.parent, prefix=".justpfm-", delete=False
    )
    try:
        with temporary as file:
            file.write(identifier.encode())
            file.write((f"\n{width} {height}\n").encode())
            file.write((f"{scale}\n").encode())
            flipped_data.tofile(file)
        try:
            destination_stat = destination.lstat()
        except FileNotFoundError:
            pass
        else:
            if S_ISREG(destination_stat.st_mode):
                chmod(temporary.name, S_IMODE(destination_stat.st_mode))
        replace(temporary.name, destination)
    finally:
        try:
            # Windows cannot unlink read-only files after a failed replacement.
            chmod(temporary.name, 0o600)
            Path(temporary.name).unlink()
        except FileNotFoundError:
            pass


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
    if 0 in data.shape:
        return False
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
        sample_count = width * height * channels
        expected_bytes = sample_count * 4
        remaining_bytes = fstat(file.fileno()).st_size - file.tell()
        if remaining_bytes != expected_bytes:
            raise ValueError(
                f"Invalid PFM payload size: expected {expected_bytes} bytes, "
                f"got {remaining_bytes}"
            )
        data = np.fromfile(file, endianness + "f", count=sample_count)
        if data.size != sample_count:
            raise ValueError("PFM payload was truncated while reading")
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
    if width <= 0 or height <= 0:
        raise ValueError("PFM width and height must be positive")
    return width, height


def _get_pfm_scale_and_endianness_from_line(line: bytes) -> Tuple[float, str]:
    """Parse the scale and endianness from the PFM header"""
    decoded_line = line.rstrip().decode("UTF-8")
    scale = float(decoded_line)
    if not isfinite(scale) or scale == 0:
        raise ValueError("PFM scale must be finite and nonzero")
    endianness = ""
    if scale < 0:
        endianness = "<"
        scale = -scale
    else:
        endianness = ">"
    return scale, endianness
