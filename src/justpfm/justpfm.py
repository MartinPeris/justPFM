"""A small Python module to read/write PFM (Portable Float Map) images"""

from __future__ import annotations

from io import BytesIO
from math import isclose, isfinite
from os import PathLike, chmod, fstat, replace
from pathlib import Path
from stat import S_IMODE, S_ISREG
from sys import byteorder
from tempfile import NamedTemporaryFile
from typing import IO, Any, BinaryIO, Optional, Tuple, Union

import numpy as np
import numpy.typing as npt

_MAX_HEADER_LINE_BYTES = 4096
_WRITE_BUFFER_BYTES = 8 * 1024 * 1024


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
    header = _encode_pfm_header(data, scale)
    flipped_data = np.flipud(data)

    destination = Path(file_name)
    temporary = NamedTemporaryFile(
        mode="wb", dir=destination.parent, prefix=".justpfm-", delete=False
    )
    try:
        with temporary as file:
            file.write(header)
            _write_pfm_payload(file.file, flipped_data)
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


def encode_pfm(data: npt.NDArray[np.float32], scale: float = 1) -> bytes:
    """Encode an image to complete PFM bytes without accessing the filesystem.

    Accept the same shapes, float32 byte orders, layouts and scale as write_pfm.
    Scale is recorded in the header without multiplying pixels. Input data is
    unchanged. The returned bytes own the complete encoded image; constructing
    them also temporarily allocates a full serialized pixel payload.
    """
    header = _encode_pfm_header(data, scale)
    return header + np.flipud(data).tobytes(order="C")


def _encode_pfm_header(data: npt.NDArray[np.float32], scale: float) -> bytes:
    """Validate writer inputs and format a shared header for file and byte APIs."""
    if not isfinite(scale) or scale <= 0:
        raise ValueError("scale must be positive and finite")
    if not _is_valid_shape(data):
        raise ValueError("data has invalid shape: " + str(data.shape))
    if data.dtype.kind != "f" or data.dtype.itemsize != 4:
        raise ValueError("data must be float32: " + str(data.dtype))

    identifier = _get_pfm_identifier_from_data(data)
    width, height = _get_pfm_width_and_height_from_data(data)
    scale *= _get_pfm_endianness_from_data(data)

    return f"{identifier}\n{width} {height}\n{scale}\n".encode()


def _write_pfm_payload(file: IO[bytes], data: npt.NDArray[np.float32]) -> None:
    """Serialize in bulk, using at most one row or 8 MiB of pixel scratch space."""
    if data.flags.c_contiguous:
        data.tofile(file)
        return
    row_bytes = data[0].size * data.dtype.itemsize
    rows = max(1, _WRITE_BUFFER_BYTES // row_bytes)
    buffer = np.empty((min(rows, data.shape[0]),) + data.shape[1:], dtype=data.dtype)
    for start in range(0, data.shape[0], rows):
        source = data[start : start + rows]
        block = buffer[: source.shape[0]]
        np.copyto(block, source)
        block.tofile(file)


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
    _validate_max_pixels(max_pixels)
    with open(file_name, "rb") as file:
        shape, scale, endianness = _read_pfm_header(file, max_pixels)
        sample_count = shape[0] * shape[1] * shape[2]
        _validate_payload_size(fstat(file.fileno()).st_size - file.tell(), sample_count)
        data: npt.NDArray[np.float32] = np.fromfile(
            file, endianness + "f", count=sample_count
        )
        if data.size != sample_count:
            raise ValueError("PFM payload was truncated while reading")
        return _finish_pfm_read(data, shape, scale)


def decode_pfm(
    payload: Union[bytes, bytearray], *, max_pixels: Optional[int] = None
) -> npt.NDArray[np.float32]:
    """Decode complete PFM bytes into independent, writable (H, W, C) pixels.

    Accept bytes or bytearray; other types raise TypeError. Apply the same header,
    payload, scale and pixel-limit validation as read_pfm before pixel allocation.
    Preserve file byte order and return top-first rows with negative row strides.
    Always copy pixels, including for scale 1: the result never aliases payload.
    The caller retains ownership of payload and must not mutate it during decoding.
    The encoded input and decoded pixel allocation coexist in memory.
    """
    _validate_max_pixels(max_pixels)
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("payload must be bytes or bytearray")
    # Three bounded header lines plus one byte to detect an oversized last line.
    # Do not copy the full encoded image merely to parse its header.
    with BytesIO(payload[: 3 * _MAX_HEADER_LINE_BYTES + 1]) as header:
        shape, scale, endianness = _read_pfm_header(header, max_pixels)
        offset = header.tell()
    sample_count = shape[0] * shape[1] * shape[2]
    _validate_payload_size(len(payload) - offset, sample_count)
    data: npt.NDArray[np.float32] = np.frombuffer(
        payload, dtype=endianness + "f", count=sample_count, offset=offset
    ).copy()
    return _finish_pfm_read(data, shape, scale)


def _validate_max_pixels(max_pixels: Optional[int]) -> None:
    """Reject invalid limits before opening files or parsing bytes."""
    if max_pixels is not None:
        if isinstance(max_pixels, bool) or not isinstance(max_pixels, int):
            raise ValueError("max_pixels must be a positive integer or None")
        if max_pixels <= 0:
            raise ValueError("max_pixels must be a positive integer or None")


def _read_pfm_header(
    file: BinaryIO, max_pixels: Optional[int]
) -> Tuple[Tuple[int, int, int], float, str]:
    """Read bounded header lines and enforce the pixel limit before raster access."""
    channels = _get_pfm_channels_from_line(_read_pfm_header_line(file))
    width, height = _get_pfm_width_and_height_from_line(_read_pfm_header_line(file))
    if max_pixels is not None and width * height > max_pixels:
        raise ValueError(f"PFM image exceeds max_pixels limit of {max_pixels}")
    scale, endianness = _get_pfm_scale_and_endianness_from_line(
        _read_pfm_header_line(file)
    )
    return (height, width, channels), scale, endianness


def _validate_payload_size(remaining_bytes: int, sample_count: int) -> None:
    """Reject missing or extra pixels before allocating a decoded array."""
    expected_bytes = sample_count * 4
    if remaining_bytes != expected_bytes:
        raise ValueError(
            f"Invalid PFM payload size: expected {expected_bytes} bytes, "
            f"got {remaining_bytes}"
        )


def _finish_pfm_read(
    data: npt.NDArray[np.float32], shape: Tuple[int, int, int], scale: float
) -> npt.NDArray[np.float32]:
    """Restore row order and apply scale once to independently owned pixels."""
    data = np.flipud(np.reshape(data, shape))
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
