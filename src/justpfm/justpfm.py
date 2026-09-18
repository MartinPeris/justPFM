"""A small Python module to read/write PFM (Portable Float Map) images"""

from __future__ import annotations

from math import isclose, isfinite
from os import PathLike, chmod, fstat, replace
from pathlib import Path
from stat import S_IMODE, S_ISREG
from sys import byteorder
from tempfile import NamedTemporaryFile
from typing import Any, BinaryIO, Optional, Tuple, Union

import numpy as np
import numpy.typing as npt

_MAX_HEADER_LINE_BYTES = 4096


def write_pfm(
    file_name: Union[str, PathLike[str]],
    data: npt.NDArray[np.float32],
    scale: float = 1,
) -> None:
    """
    Write float32 pixels to a str or path-like destination; return None.

    Accept positive (H, W), (H, W, 1), or (H, W, 3) shapes in either byte
    order, including strided arrays and nonfinite pixels. Scale must be positive
    and finite: it is recorded in the header without changing stored samples.
    Reading applies that magnitude to samples. Invalid data/scale raise ValueError;
    filesystem failures raise OSError. Rows are stored bottom-first.

    Atomically replace the destination after closing the file.

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


def _get_pfm_identifier_from_data(data: npt.NDArray[Any]) -> str:
    """Get the pfm identifier depending on the number of channels on the
    data object
    """
    identifier = "Pf"
    if len(data.shape) == 3 and data.shape[2] == 3:
        identifier = "PF"
    return identifier


def _is_valid_shape(data: npt.NDArray[Any]) -> bool:
    """Return true if the shape of the data is valid"""
    if 0 in data.shape:
        return False
    if len(data.shape) == 2:
        return True

    if len(data.shape) == 3:
        if data.shape[2] == 1 or data.shape[2] == 3:
            return True
    return False


def _get_pfm_width_and_height_from_data(data: npt.NDArray[Any]) -> Tuple[int, int]:
    """Return the width and height of the matrix in the proper order"""
    height, width = data.shape[:2]
    return width, height


def _get_pfm_endianness_from_data(data: npt.NDArray[Any]) -> float:
    """Return 1 if bigendian, -1 if little endian data"""
    endianness = data.dtype.byteorder
    return (
        -1 if endianness == "<" or (endianness == "=" and byteorder == "little") else 1
    )


def read_pfm(
    file_name: Union[str, PathLike[str]], *, max_pixels: Optional[int] = None
) -> npt.NDArray[np.float32]:
    """Read a str or path-like PFM file as an (H, W, C) float32 array.

    C is 1 for grayscale or 3 for RGB. The dtype retains the file byte order;
    top-first rows have negative strides. Use np.ascontiguousarray(result,
    dtype=np.float32) when native byte order and contiguous storage are needed.
    Samples are multiplied by the positive header scale magnitude, except scales
    math.isclose to 1 (relative tolerance 1e-9). Nonfinite pixels are accepted;
    scaling follows NumPy float32 arithmetic.
    Invalid headers, dimensions, scales, or payload lengths raise ValueError;
    filesystem failures raise OSError. Payload size is checked before allocation.
    Each of the three header lines must end in a newline and fit in 4096 bytes,
    including that newline. max_pixels optionally bounds H * W before allocation;
    supply a positive built-in int (not bool), or None for no pixel-count limit.
    Invalid limits and images exceeding the limit raise ValueError.
    """
    if max_pixels is not None:
        if isinstance(max_pixels, bool) or not isinstance(max_pixels, int):
            raise ValueError("max_pixels must be a positive integer or None")
        if max_pixels <= 0:
            raise ValueError("max_pixels must be a positive integer or None")
    with open(file_name, "rb") as file:
        channels = _get_pfm_channels_from_line(_read_pfm_header_line(file))
        width, height = _get_pfm_width_and_height_from_line(_read_pfm_header_line(file))
        if max_pixels is not None and width * height > max_pixels:
            raise ValueError(f"PFM image exceeds max_pixels limit of {max_pixels}")
        scale, endianness = _get_pfm_scale_and_endianness_from_line(
            _read_pfm_header_line(file)
        )
        sample_count = width * height * channels
        expected_bytes = sample_count * 4
        remaining_bytes = fstat(file.fileno()).st_size - file.tell()
        if remaining_bytes != expected_bytes:
            raise ValueError(
                f"Invalid PFM payload size: expected {expected_bytes} bytes, "
                f"got {remaining_bytes}"
            )
        data: npt.NDArray[np.float32] = np.fromfile(
            file, endianness + "f", count=sample_count
        )
        if data.size != sample_count:
            raise ValueError("PFM payload was truncated while reading")
        shape = (height, width, channels)
        data = np.reshape(data, shape)
        data = np.flipud(data)
        if not isclose(scale, 1.0):
            data *= scale
        return data


def _read_pfm_header_line(file: BinaryIO) -> bytes:
    """Read a newline-terminated header line using a bounded buffer."""
    line = file.readline(_MAX_HEADER_LINE_BYTES + 1)
    if len(line) > _MAX_HEADER_LINE_BYTES:
        raise ValueError("PFM header line exceeds 4096 bytes")
    if not line.endswith(b"\n"):
        raise ValueError("Truncated PFM header: missing newline")
    return line


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
