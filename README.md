# justPFM

A small NumPy-based Python module to read and write Portable Float Map images.

[![CI and tests on main](https://img.shields.io/github/actions/workflow/status/MartinPeris/justPFM/quality.yml?branch=main&event=push&label=CI%20%26%20tests)](https://github.com/MartinPeris/justPFM/actions/workflows/quality.yml?query=branch%3Amain+event%3Apush)
[![Coverage gate: 100% statements and branches](https://img.shields.io/badge/coverage%20gate-100%25%20statements%20%2B%20branches-brightgreen)](CONTRIBUTING.md#run-the-same-checks-as-ci)
[![PyPI version](https://img.shields.io/pypi/v/justpfm)](https://pypi.org/project/justpfm/)
[![Supported Python: 3.7–3.14](https://img.shields.io/badge/Python-3.7%E2%80%933.14-blue)](SUPPORT.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

[![Read baseline: 7.100 ms](https://img.shields.io/badge/read%20baseline-7.100%20ms-blue)](BENCHMARKS.md#recorded-baseline)
[![Write baseline: 16.510 ms](https://img.shields.io/badge/write%20baseline-16.510%20ms-blue)](BENCHMARKS.md#recorded-baseline)

CI/tests tracks the latest `main` push through the [full quality harness](CONTRIBUTING.md#ci-and-merge-protection).
Coverage is the required threshold; measured reports are in each CI run's
`coverage` artifact. PyPI shows the published release; Python support describes
this repository revision.

Performance badges show **justPFM 1.2.0 baseline medians (2026-09-18)**, not live CI results:
2048 × 2048 RGB float32 (48 MiB), scale 1, native byte order, contiguous write
input, on Linux with an AMD Ryzen 9 7940HS. These are warm/cache-eligible reads
and atomic writes without `fsync`. See [benchmark details](BENCHMARKS.md#recorded-baseline)
for the measured revision, environment, raw samples, and reproduction commands.

## Install

Supported Python versions: **3.7–3.14**. See [SUPPORT.md](SUPPORT.md) for the
compatibility policy and interpreter-specific test tooling.

```bash
pip install justpfm
```

## Usage

```python
from pathlib import Path

import numpy as np
from justpfm import read_pfm, write_pfm

# Grayscale: the first array axis is height, and rows are top-first.
path = Path("grayscale.pfm")
pixels = np.arange(15, dtype=np.float32).reshape(3, 5)
write_pfm(path, pixels)
loaded = read_pfm(path)
assert loaded.shape == (3, 5, 1)
np.testing.assert_array_equal(loaded[..., 0], pixels)

# RGB uses the last axis for red, green, and blue.
rgb = np.zeros((3, 5, 3), dtype=np.float32)
rgb[..., 0] = 1
write_pfm("rgb.pfm", rgb, scale=0.5)
np.testing.assert_array_equal(read_pfm("rgb.pfm"), rgb * 0.5)
```

The existing `from justpfm import justpfm` import remains supported.

## API contract

`write_pfm(file_name, data, scale=1) -> None`

- `file_name` accepts a string or a filesystem path object such as `pathlib.Path`.
- `data` must be a NumPy float32 array with positive height and width, shaped
  `(H, W)`, `(H, W, 1)`, or `(H, W, 3)`. Both little- and big-endian float32
  dtypes are supported, including noncontiguous arrays. Pixel NaNs and infinities
  are allowed.
- `scale` must be positive and finite. The writer stores the original pixel
  samples and records the scale in the header. The header sign describes the
  array's byte order; callers supply only the magnitude.
- Rows are written bottom-first as required by PFM.

`read_pfm(file_name, *, max_pixels=None) -> numpy.ndarray`

- Returns float32 pixels shaped `(H, W, C)`, where `C` is 1 for grayscale or 3
  for RGB. The returned dtype retains the file's byte order.
- Applies the header scale magnitude to pixel values, except magnitudes within
  `math.isclose(scale, 1.0)` (relative tolerance `1e-9`). Thus nonunit write scales
  generally change values when read back; scaling uses float32 arithmetic and
  may overflow or underflow for extreme values.
- Returns top-first rows using a view with negative row strides. For native
  byte order and contiguous storage, use
  `np.ascontiguousarray(loaded, dtype=np.float32)`. Use `loaded[..., 0]` to remove
  the grayscale channel axis.
- Requires positive dimensions, a finite nonzero header scale, and exactly the
  expected raster bytes. It checks the file size before allocating pixel data
  and limits reads to the declared number of samples.
- Each of the three header lines must end in a newline and occupy at most
  **4096 bytes including the newline**. Overlong and truncated headers raise
  `ValueError`; header reads use bounded buffers.
- Set the keyword-only `max_pixels` argument to a positive built-in integer to
  reject images whose `H * W` exceeds that limit before allocating their raster.
  The default `None` imposes no pixel-count limit. Booleans, other types, zero,
  and negative limits raise `ValueError` before the file is opened. The limit
  counts pixels rather than channel samples, so RGB and grayscale images of
  equal dimensions have the same pixel count.

Invalid shapes, dtypes, dimensions, scales, headers, and payload lengths raise
`ValueError`. Filesystem failures such as missing files or denied access raise
`OSError` subclasses. Both functions operate on filesystem files, not in-memory
file-like objects. Sufficient memory is still required. For untrusted files,
choose a pixel limit appropriate for the application, for example:

```python
loaded = read_pfm("upload.pfm", max_pixels=4_000_000)
```

The raster needs 4 bytes per grayscale pixel or 12 bytes per RGB pixel. This
limit bounds that allocation, not total process memory, application copies, or
other overhead. With `max_pixels=None`, large valid images remain supported.

### Interchange with Netpbm

Use `scale=1` to exchange normalized pixel intensities with Netpbm. Its
`pfmtopam` reader divides samples by the header magnitude, while justPFM
multiplies by it. Nonunit scales therefore have different intensity semantics.
The tests use files generated by the actual Netpbm implementation and verify
both directions; [fixture provenance and examples](tests/fixtures/netpbm/README.md)
document the difference.

### In-memory PFM data

`encode_pfm(data, scale=1) -> bytes` returns a complete PFM image, including its
header. `decode_pfm(payload, *, max_pixels=None) -> numpy.ndarray` accepts complete
`bytes` or `bytearray` input. These functions perform no filesystem or network I/O,
so applications can supply bytes obtained through their own HTTP, archive, or
cloud-storage libraries without adding those dependencies to justPFM.

```python
import numpy as np
from justpfm import decode_pfm, encode_pfm

pixels = np.arange(15, dtype=np.float32).reshape(3, 5)
payload = encode_pfm(pixels, scale=0.5)
restored = decode_pfm(payload, max_pixels=15)
np.testing.assert_array_equal(restored[..., 0], pixels * 0.5)
restored[0, 0, 0] = 42  # Always writable; does not change payload.
```

Encoding accepts the same shapes, float32 byte orders, layouts and positive finite
scale as `write_pfm`. It records scale without multiplying samples. Decoding
shares `read_pfm`'s header limits, exact payload validation, scale interpretation,
and pixel limit. It returns `(H, W, C)` float32 pixels in the file's byte order,
with top-first rows and negative row strides. Invalid PFM data raises
`ValueError`; a payload type other than `bytes` or `bytearray` raises `TypeError`.

Decoded pixels are always independently owned and writable, even for immutable
input and scale 1. Changing either a mutable input buffer or the returned pixels
after decoding cannot affect the other. Do not mutate an input buffer during a
call. Memory views and generic file-like objects are not accepted by these APIs.
Both functions are also available through `from justpfm import justpfm`.

The encoded buffer and decoded pixels coexist in memory. Encoding returns a
full-image byte string and temporarily allocates a serialized payload as well;
it does not have the filesystem writer's bounded scratch-memory guarantee.
`max_pixels` limits decoded pixel allocation, not the size of the input buffer
already supplied by the caller. Filesystem APIs continue using their direct
bulk I/O and atomic replacement paths.

### Saving files

Writes use a temporary file in the destination directory, then atomically replace
its directory entry after writing and closing. A failed write preserves an
existing destination and cleans up the temporary file. The destination directory
must permit creating temporary files and replacing entries.

Existing regular file permission bits are preserved. New files have private
permissions (`0600` on POSIX). A destination symlink is replaced with a regular
file; its target is left unchanged. Other metadata, including ownership, is not
copied. Atomic replacement does not guarantee durability after a power failure.

Writes use bulk serialization with reusable pixel scratch space bounded by the
larger of 8 MiB and one image row. Data already contiguous in file order needs
no pixel scratch buffer. See the [before/after measurements](BENCHMARKS.md#bulk-writer-comparison)
for the speed and memory tradeoff.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and commit-hook installation.
Run `pre-commit run --all-files` to execute the same lint, formatting, tests,
100% statement/branch coverage, and packaging gates used by CI.

Property tests vary dimensions, pixel values, array layout, byte order, scale,
and malformed payload sizes. They also check the reader against independently
encoded binary fixtures. Local and CI runs use the same deterministic Hypothesis
profile: 60 examples per property, no example database, and no timing deadline.
Health checks remain enabled. Hypothesis uses `6.79.4` on Python 3.7–3.9 and
`6.168.0` on Python 3.10–3.14, with matching pins in the test extra and tox.
Each interpreter runs the same properties; deterministic examples are repeatable
within its pinned toolchain, not guaranteed identical across Hypothesis versions.
