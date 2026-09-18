# PFM performance measurements

The opt-in Linux benchmark measures installed-package reads and atomic writes
for grayscale and RGB float32 images. It compares scale 1 with scale 2 and
contiguous write inputs with column-strided views containing identical pixels.
It does not change the library or impose timing thresholds on commits or CI.
Ruff checks the benchmark code as part of the regular quality harness.

## Reproduce

From a clone with the developer tools installed as described in CONTRIBUTING:

```bash
tox run -e py
.tox/py/bin/python benchmarks/pfm_benchmark.py \
  --sizes 1024 2048 --repeats 5 --warmup 1 \
  --output /tmp/justpfm-results.json
```

The first command builds and installs the current library wheel. The benchmark
imports that installed package; rerun `tox run -e py` after library changes.
Use `--temp-dir /path/to/filesystem` to select storage and `--byte-order big`
to measure nonnative-endian files on a little-endian host. Defaults use native
byte order. Every case runs serially in a separate Python process and removes
its temporary PFM files on normal completion or exceptions.

A quick correctness smoke run exercises all 12 grayscale/RGB, scale, operation,
and input-layout combinations with tiny images:

```bash
.tox/py/bin/python benchmarks/pfm_benchmark.py \
  --sizes 8 --repeats 1 --warmup 0 --output /tmp/justpfm-smoke.json
.tox/py/bin/python benchmarks/pfm_benchmark.py \
  --sizes 8 --repeats 1 --warmup 0 --byte-order big \
  --output /tmp/justpfm-smoke-big.json
```

Use ordinary Python execution, without `-O`, so header assertions remain active.
The script uses Python 3.7-compatible syntax and standard-library facilities;
NumPy and the installed library are its only package dependencies. The full
harness currently provides its Python 3.12 environment for these examples.

## What the numbers measure

Each case creates an independent PFM fixture, performs an untimed correctness
call, runs the requested warmups, and records every sample with
`time.perf_counter()`. Read outputs are compared with expected pixel values.
Written headers and bottom-first payloads are checked independently of the
library reader. Validation and disposal of returned arrays happen outside the
timed region. Strided inputs select every second column from a backing array
with twice the logical width; their logical pixel values and payload sizes
match contiguous inputs. Reads use identical contiguous fixtures because a
file does not retain its source array's strides.

These are **warm/cache-eligible I/O measurements**. Fixture creation,
validation, and warmup populate caches; the benchmark neither evicts the OS
page cache nor measures cold reads. Writes include temporary-file creation,
serialization, closing, permissions, and atomic replacement of an existing
file, but no `fsync`. Throughput is logical pixel payload MiB divided by elapsed
seconds, not sustained storage bandwidth or durable-write throughput.

JSON records shapes, dtype/byte order, input strides, payload and file sizes,
raw samples, medians, throughput, Python/NumPy/OS/CPU details, affinity, source
revision, and installed-library source hash. Linux `ru_maxrss` records each
worker's lifetime peak RSS in KiB. That peak includes fixture construction,
validation allocations, warmup, and all samples; it excludes OS filesystem
cache. It is **not** the reader/writer's allocation requirement. Separate worker
processes prevent peaks from earlier cases carrying into later cases.

## Recorded baseline

[Raw JSON, 2026-09-18](benchmarks/results/linux-2026-09-18.json) contains all
24 cases and five individual timings per case. Measured library revision:
`d29455646534ce4357f022b83fae0caa18c75a9b`; benchmark files were untracked at
measurement time, as recorded in the artifact. The installed module hash is
included to identify the exact measured implementation.

Environment: AMD Ryzen 9 7940HS, 16 logical CPUs; Linux 7.0.0-30 on x86-64;
Python 3.12.3; NumPy 2.5.3; native little-endian float32. Temporary files were
under `/tmp` on the host's ext4 `/dev/nvme0n1p2` filesystem. One warmup and five
samples followed the initial correctness call. CPU affinity/frequency, other
host workloads, and caches were not isolated or reset.

Values below are median milliseconds, with logical throughput in MiB/s in
parentheses. Write columns use scale 1; the raw artifact also includes scale 2.

| Image | Payload | Read, scale 1 | Read, scale 2 | Write, contiguous | Write, strided |
| --- | --- | --- | --- | --- | --- |
| 1024² grayscale | 4 MiB | 0.666 (6006) | 0.742 (5393) | 12.942 (309) | 13.472 (297) |
| 1024² RGB | 12 MiB | 1.953 (6143) | 2.223 (5397) | 41.791 (287) | 42.130 (285) |
| 2048² grayscale | 16 MiB | 2.309 (6929) | 2.769 (5779) | 51.038 (313) | 52.128 (307) |
| 2048² RGB | 48 MiB | 6.932 (6924) | 8.513 (5638) | 158.395 (303) | 181.506 (264) |

Read scaling added about 11–23% to these medians. Writes were much slower than
cached reads, and contiguous inputs did not eliminate that difference. The
writer flips rows before NumPy serialization, so even a contiguous caller
array is serialized through a negative-row-stride view. This makes write
serialization a useful candidate for profiling; the measurements alone do
not establish which implementation change would improve it.

The largest case's measured process peaks were about 344 MiB for reads and
contiguous writes and 392 MiB for strided writes. Validation itself creates
large temporary arrays, and strided setup requires a larger backing array;
these values cannot justify a library memory optimization or an allocation
limit. Use a separate allocation-focused experiment for that question.

The largest writes varied enough across scale/layout cases that these five
samples do not justify automatically copying strided input. Scale is only
written into the header, so write-time differences between scale 1 and 2
should not be interpreted as pixel-scaling costs. Repeat full runs on the
intended hardware and storage, and investigate durable or cold I/O separately
before choosing an optimization. This baseline makes no throughput promise.
