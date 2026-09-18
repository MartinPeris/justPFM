"""Downstream typing smoke check against the installed wheel."""

from pathlib import Path

import numpy as np
import numpy.typing as npt

from justpfm import decode_pfm, encode_pfm, justpfm, read_pfm, write_pfm

pixels: npt.NDArray[np.float32] = np.ones((2, 3), dtype=np.float32)
write_pfm(Path("example.pfm"), pixels, scale=0.5)
loaded: npt.NDArray[np.float32] = read_pfm("example.pfm", max_pixels=100)
legacy: npt.NDArray[np.float32] = justpfm.read_pfm(Path("example.pfm"))

encoded: bytes = encode_pfm(pixels, scale=0.5)
decoded: npt.NDArray[np.float32] = decode_pfm(encoded, max_pixels=100)
mutable: npt.NDArray[np.float32] = decode_pfm(bytearray(encoded))
