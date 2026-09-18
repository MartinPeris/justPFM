# Changelog

## 1.1.0 — release candidate

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
  differs. See [README.md](README.md#api-contract) for the complete contract.

## 1.0.0 — 2022-05-30

- Initial public release.
