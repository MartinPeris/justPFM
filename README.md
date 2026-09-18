# justPFM

Read and write Portable Float Map (PFM) images as NumPy arrays—from files or bytes.

[![CI and tests on main](https://img.shields.io/github/actions/workflow/status/MartinPeris/justPFM/quality.yml?branch=main&event=push&label=CI%20%26%20tests)](https://github.com/MartinPeris/justPFM/actions/workflows/quality.yml?query=branch%3Amain+event%3Apush)
[![Coverage gate: 100% statements and branches](https://img.shields.io/badge/coverage%20gate-100%25%20statements%20%2B%20branches-brightgreen)](https://github.com/MartinPeris/justPFM/blob/main/CONTRIBUTING.md#run-the-same-checks-as-ci)
[![PyPI version](https://img.shields.io/pypi/v/justpfm)](https://pypi.org/project/justpfm/)
[![Supported Python: 3.7–3.14](https://img.shields.io/badge/Python-3.7%E2%80%933.14-blue)](https://github.com/MartinPeris/justPFM/blob/main/SUPPORT.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/MartinPeris/justPFM/blob/main/LICENSE)

[![Read baseline: 7.100 ms](https://img.shields.io/badge/read%20baseline-7.100%20ms-blue)](https://github.com/MartinPeris/justPFM/blob/main/BENCHMARKS.md#recorded-baseline)
[![Write baseline: 16.510 ms](https://img.shields.io/badge/write%20baseline-16.510%20ms-blue)](https://github.com/MartinPeris/justPFM/blob/main/BENCHMARKS.md#recorded-baseline)

Benchmark badges: **1.2.0, 2026-09-18**, 2048² RGB float32 (48 MiB), scale 1,
native byte order, contiguous write input; Linux / Ryzen 9 7940HS, warm cache,
no `fsync`. [Measurements and methodology](https://github.com/MartinPeris/justPFM/blob/main/BENCHMARKS.md#recorded-baseline).
Coverage badge shows the enforced gate, not a live measurement.

## At a glance

- Grayscale and RGB float32 images, with both byte orders and strided arrays.
- File I/O plus in-memory encoding and decoding; NumPy is the only runtime dependency.
- Atomic file replacement and validated input, with an optional read-size limit.
- Python **3.7–3.14**, type annotations, and MIT license.

## Install

```bash
python -m pip install justpfm
```

## Quick start

```python
import numpy as np
from justpfm import decode_pfm, encode_pfm, read_pfm, write_pfm

pixels = np.arange(15, dtype=np.float32).reshape(3, 5)

# Files: string paths and pathlib.Path are supported.
write_pfm("image.pfm", pixels)
loaded = read_pfm("image.pfm", max_pixels=4_000_000)
print(loaded.shape)  # (3, 5, 1)

# Bytes: useful with your own HTTP, archive, or cloud-storage code.
payload = encode_pfm(pixels)
restored = decode_pfm(payload, max_pixels=4_000_000)
```

| Function | Purpose |
| --- | --- |
| `write_pfm(file_name, data, scale=1)` | Save an array to a file. |
| `read_pfm(file_name, *, max_pixels=None)` | Load an array from a file. |
| `encode_pfm(data, scale=1)` | Encode an array to PFM `bytes`. |
| `decode_pfm(payload, *, max_pixels=None)` | Decode PFM `bytes` or `bytearray`. |

Inputs must be float32 arrays shaped `(H, W)`, `(H, W, 1)`, or `(H, W, 3)`.
Reads return top-first `(H, W, C)` arrays; use `loaded[..., 0]` for 2D grayscale.
For native byte order and contiguous storage, use
`np.ascontiguousarray(loaded, dtype=np.float32)`.

Use the default `scale=1` to preserve values. Other positive finite scales are
recorded on write and multiplied into pixels on read. `max_pixels` limits
`H * W` before pixel allocation; its default is unlimited. In-memory APIs hold
the full PFM payload, and decoding returns writable pixels independent of it.

## Learn more

- [API reference](https://github.com/MartinPeris/justPFM/blob/main/API.md): validation, scaling, array layout, memory, and file permissions.
- [Benchmarks](https://github.com/MartinPeris/justPFM/blob/main/BENCHMARKS.md): raw results, reproduction, and performance tradeoffs.
- [Compatibility](https://github.com/MartinPeris/justPFM/blob/main/SUPPORT.md) and [changelog](https://github.com/MartinPeris/justPFM/blob/main/CHANGELOG.md).
- [Contributing](https://github.com/MartinPeris/justPFM/blob/main/CONTRIBUTING.md): setup, commit hooks, tests, coverage, and releases.
