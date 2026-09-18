# Changelog

## 1.2.0.post1 — 2026-09-18

- Refresh the packaged README performance badges with the recorded 1.2.0
  baseline: 7.100 ms read and 16.510 ms write for the documented 2048² RGB
  workload. Include raw measurements, reproduction details, and release
  maintenance guidance.
- Documentation-only post-release; library behavior, dependencies, and Python
  support are unchanged from 1.2.0.

## 1.2.0 — 2026-09-18

- Add `encode_pfm` and `decode_pfm` for complete PFM bytes, without filesystem
  access or additional dependencies. Share validation and scale semantics with
  the file APIs; decoded arrays are always writable and independent of the input.
- Keep optimized filesystem I/O and atomic replacement intact.
- Add README badges for CI, coverage requirements, package information, and
  recorded benchmark results.

### Upgrade notes

- This is an additive release; existing file APIs remain compatible. Python
  3.7–3.14 and NumPy >=1.21 remain supported.
- In-memory encoding returns a complete `bytes` object. Decoding accepts `bytes`
  or `bytearray`, supports `max_pixels`, and allocates an independent pixel array.
  Use the file APIs when avoiding a complete in-memory PFM payload is important.

## 1.1.0 — 2026-09-18

### Performance

- Serialize PFM writes in bulk through a reusable buffer. Pixel scratch space is
  bounded by the larger of 8 MiB and one row; pixels already contiguous in file
  order are written directly.
- On the recorded Linux benchmark, 48 MiB RGB writes improved from 159 to 17 ms
  for contiguous input (9.3×) and from 162 to 33 ms for strided input (4.9×).
  These are warm/cache-eligible, non-fsync measurements on one host. See
  [BENCHMARKS.md](BENCHMARKS.md#bulk-writer-comparison) for raw results and reproduction.

### Features and fixes since 1.0.0

- Export `read_pfm` and `write_pfm` from the package root, with public type
  annotations and a packaged `py.typed` marker. The original
  `from justpfm import justpfm` import remains supported.
- Add the optional keyword-only `max_pixels` read limit and bounded header reads.
- Correct nonsquare image handling and support both float32 byte orders,
  noncontiguous arrays, and path-like filenames.
- Validate dimensions, scales, dtypes, and exact payload length before processing;
  detect truncated raster reads and reject malformed files consistently.
- Save through a sibling temporary file and atomically replace the destination.
  Failed saves preserve the existing destination and clean up temporary files.
- Add property tests, independent Netpbm fixtures and interoperability checks,
  strict typing, package checks, and enforced 100% statement/branch coverage.

### Compatibility and upgrade notes

- Python 3.7–3.14 is supported and tested on Linux. NumPy remains required;
  its minimum version is now 1.21.
- Each of the three header lines must end in a newline and fit within 4096 bytes.
  Invalid inputs that previously slipped through may now raise `ValueError`.
  Scale magnitudes must be positive and finite when writing, and finite and
  nonzero in a file header. NaN and infinite pixel values remain supported.
- New files use private permissions (`0600` on POSIX). Existing regular-file
  permission bits are retained. Saving to a symlink replaces that directory
  entry rather than its target; ownership and other metadata are not preserved.
  The destination directory must allow temporary files and replacement.
- Atomic replacement does not guarantee power-loss durability. Reads still
  return `(H, W, C)` arrays with top-first rows, generally with negative row
  strides, and multiply samples by the header scale magnitude. Use scale 1 for
  neutral intensity interchange with Netpbm, whose nonunit-scale convention
  differs. See [API.md](API.md) for the complete contract.

## 1.0.0 — 2022-05-30

- Initial public release.
