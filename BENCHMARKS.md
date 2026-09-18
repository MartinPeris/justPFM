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

The README badges summarize **justPFM 1.2.0**, installed from PyPI and measured
on 2026-09-18. [Raw JSON](benchmarks/results/linux-1.2.0-2026-09-18.json) includes
24 cases, seven timing samples per case, and separate write-allocation probes.
The benchmark worktree was clean at release revision
`39f0ccb768464202aad81b7eab87cba47dc3e36d`; the installed module's SHA-256 matches
that revision's source and is recorded in the artifact.

Environment: AMD Ryzen 9 7940HS, 16 logical CPUs; Linux 7.0.0-30 on x86-64;
Python 3.12.3; NumPy 2.5.3; native little-endian float32; `/tmp` on ext4
(`/dev/nvme0n1p2`). Two warmups and seven samples followed the correctness call.
CPU frequency, other host workloads, and caches were not isolated or reset.
These remain warm/cache-eligible measurements with atomic writes and no `fsync`.

Values are median milliseconds, with logical throughput in MiB/s in parentheses.
Write columns use scale 1; the raw artifact also includes scale 2. The badges
select the 2048² RGB, scale-1 read and contiguous-write cells.

| Image | Payload | Read, scale 1 | Read, scale 2 | Write, contiguous | Write, strided |
| --- | --- | --- | --- | --- | --- |
| 1024² grayscale | 4 MiB | 0.625 (6403) | 0.541 (7391) | 1.734 (2307) | 2.037 (1964) |
| 1024² RGB | 12 MiB | 1.825 (6577) | 1.769 (6785) | 4.474 (2682) | 7.987 (1502) |
| 2048² grayscale | 16 MiB | 2.284 (7005) | 2.081 (7690) | 5.782 (2767) | 7.047 (2270) |
| 2048² RGB | 48 MiB | 7.100 (6761) | 9.207 (5213) | 16.510 (2907) | 32.070 (1497) |

These are single-host observations, not portable guarantees or CI thresholds.
Small differences from historical read timings do not establish a regression
or improvement. See the controlled [bulk writer comparison](#bulk-writer-comparison)
for the optimization's before/after measurements.

To reproduce this baseline, use the benchmark driver from tag `v1.2.0` and a
Python 3.12 environment with the released package and measured NumPy version:

```bash
python -m pip install justpfm==1.2.0 numpy==2.5.3
python benchmarks/pfm_benchmark.py \
  --sizes 1024 2048 --repeats 7 --warmup 2 --measure-allocations \
  --output /tmp/justpfm-1.2.0-baseline.json
```

## Historical baseline before bulk writes


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

## Bulk writer comparison

The writer now copies noncontiguous, bottom-first pixels into a reusable row
buffer before bulk serialization. Its pixel scratch allocation is bounded by
**the larger of 8 MiB and one row**, and smaller images allocate only their
payload size. An unusually wide row can exceed 8 MiB. Arrays already contiguous
in file order (for example, an unscaled read result written back) go directly to
`tofile` without a pixel buffer. Input pixels and byte order remain unchanged.

A full contiguous copy was also explored: it removed the serialization bottleneck
but required an extra full-image allocation (48 MiB for 2048² RGB). The reusable
buffer retains substantial speed gains with bounded scratch space. This choice
does not claim that 8 MiB is optimal on every machine; filesystem cache, image
layout and size affect timings. Atomic replacement and error cleanup are retained.

### Measured before and after

The [before artifact](benchmarks/results/bulk-write-before-2026-09-18.json) measures
library revision `16d301f1814ef6bb17896265025d76c2a5f41c81`; the
[after artifact](benchmarks/results/bulk-write-after-2026-09-18.json) measures
`5b6dc39f97f2b68b780f51ecb96137e8e6cbaaa0`. Both use the benchmark driver from the
latter revision, seven samples, two warmups, and identical 32², 1024² and 2048²
cases. The baseline worktree's modified benchmark driver is recorded in its
`git_status`; its installed library is unmodified. Each artifact includes the
installed library's source hash.

These are one sequential before/after run on the same Linux host described above:
AMD Ryzen 9 7940HS, Python 3.12.3, NumPy 2.5.3, native little-endian float32,
`/tmp` on ext4/NVMe. The warm/cache-eligible and non-durable-write limitations
above still apply; timings are not portable guarantees. Correctness checks are
outside the timed region. Table values are scale-1 **median milliseconds**;
the raw results include grayscale, scale 2, every timing sample, and reads.

| Image | Input | Before ms | After ms | Speedup | After traced peak MiB |
| --- | --- | --- | --- | --- | --- |
| 32² RGB | contiguous | 0.276 | 0.181 | 1.53× | 0.018 |
| 32² RGB | strided | 0.254 | 0.235 | 1.08× | 0.018 |
| 1024² RGB | contiguous | 43.593 | 4.620 | 9.44× | 7.999 |
| 1024² RGB | strided | 42.160 | 7.870 | 5.36× | 7.999 |
| 2048² RGB | contiguous | 159.028 | 17.173 | 9.26× | 7.999 |
| 2048² RGB | strided | 161.830 | 33.044 | 4.90× | 7.999 |

The 32² cases show no slowdown in this run, but sub-millisecond differences are
particularly noisy. Read code is unchanged; incidental read timing differences
are not claimed as an improvement. These results support the bulk-write approach,
not a mandatory CI timing threshold.

### Reproduce the comparison and allocations

Use separate worktrees and installed-wheel environments for the two revisions.
Copy `benchmarks/pfm_benchmark.py` from the optimized revision into the baseline
worktree so both runs have identical instrumentation. In each worktree, run:

```bash
tox run -e py
.tox/py/bin/python benchmarks/pfm_benchmark.py \
  --sizes 32 1024 2048 --repeats 7 --warmup 2 --measure-allocations \
  --output /tmp/justpfm-comparison.json
```

Use distinct output filenames for each revision, run them serially, and repeat
in reverse order when evaluating sensitivity to machine state. Use
`--byte-order big` to compare nonnative-endian data on this host.

`--measure-allocations` adds one separate write **after** the timing samples.
Only that write runs under `tracemalloc`; input construction and correctness
validation are excluded. `write_traced_peak_bytes` includes Python and NumPy
allocations exposed to tracemalloc, including the scratch buffer. It is not
whole-process RSS, OS cache use, or proof that all native allocations are traced.
The buffer's roughly 8 MiB traced peak on large images agrees with its configured
bound; small Python/I/O allocations can bring the total slightly above 8 MiB.
Process-lifetime RSS also includes this extra call when allocation tracing is
enabled and remains unsuitable for isolating writer allocation.
