# Netpbm interoperability fixtures

The twelve `.pfm` files in this directory were produced by the **actual
`pamtopfm` executable**, not by justPFM or a Python PFM encoder. The original
ASCII PGM/PPM inputs describe nonuniform 3-by-2 images; their small integer
samples and maxval 16 give exactly representable normalized float32 values.
Each image has little- and big-endian variants with header magnitudes 0.5, 1,
and 2. The ordinary unit suite reads every fixture without requiring Netpbm.

## Provenance and license

Generated on Linux x86-64 with Ubuntu 24.04 packages `netpbm` and
`libnetpbm11t64`, both version `2:11.05.02-1.1build1`. Output from
`pamtopfm -version`:

```text
pamtopfm: Using libnetpbm from Netpbm Version: Netpbm 11.5.2
pamtopfm: Built from source dated 2024-03-31 17:09:47
pamtopfm: Built by Debian
```

Package source: [Ubuntu netpbm-free 11.05.02](https://launchpad.net/ubuntu/+source/netpbm-free/2:11.05.02-1.1build1).
The source images and generated fixtures are original test data provided under
this repository's [MIT license](../../../LICENSE). No Netpbm executables or
source code are vendored. Netpbm has component-specific licenses; the producing
`converter/other/pamtopfm.c` is designated public domain in the package's
`/usr/share/doc/netpbm/copyright` (Bryan Henderson, 2000, 2004, 2008).

## Reproduction

Install Netpbm using your distribution's package manager, then from the
repository root run:

```bash
pamtopfm -version
python tests/fixtures/netpbm/generate.py
python tests/fixtures/netpbm/generate.py --check
```

The generator calls the external executable for all twelve combinations,
using commands such as:

```bash
pamtopfm -endian=little -scale=0.5 tests/fixtures/netpbm/grayscale.pgm \
  > tests/fixtures/netpbm/grayscale-little-scale-0.5.pfm
pamtopfm -endian=big -scale=2 tests/fixtures/netpbm/rgb.ppm \
  > tests/fixtures/netpbm/rgb-big-scale-2.pfm
```

`--check` regenerates in memory and requires byte-for-byte agreement without
modifying files. Tool errors or changed output fail the check. The `interop`
tox target runs this verification and tests actual `pfmtopam` decoding of files
written by justPFM. It prints both converter versions. It deliberately fails
if either converter is missing instead of silently skipping interoperability.

The original generation used packages downloaded and extracted into a temporary
directory with `apt download netpbm libnetpbm11t64` and `dpkg-deb -x`, rather than
a global installation. The extracted `usr/bin` was added to `PATH` and
`usr/lib/x86_64-linux-gnu` to `LD_LIBRARY_PATH`; tox passes that library path to
the live checks. CI uses the Ubuntu 24.04 package installation and reports its
version in the job log.

## Scale conventions: an observed interoperability limit

Let `n` be a PNM input sample divided by its maxval, and `s` the positive header
scale magnitude. Netpbm's `pamtopfm -scale=s` stores `n * s`. Its `pfmtopam`
reader divides stored samples by `s` to recover `n`. In contrast, justPFM's
established API stores its input samples unchanged and **multiplies** stored
samples by `s` on reading. Thus justPFM reads these particular generated files
as `n * s * s`.

At `s = 1`, both implementations recover the same pixels, orientations,
channels, and byte orders. Nonunit-scale tests explicitly check each
implementation's convention; they do not claim identical intensity
interpretation. For interchange with Netpbm, use header magnitude 1 and put the
desired normalized values directly in the raster. This testing change preserves
justPFM's existing scale contract.

Live writer tests supply `n * s` to justPFM and verify that Netpbm returns `n`,
quantized to its default PAM maxval 255. Expected samples come directly from the
ASCII source images, with nearest-integer conversion (ties rounded up). Values
stay in range, so clipping cannot conceal mistakes in orientation or channels.

Primary references:

- [PFM format and row order](https://netpbm.sourceforge.net/doc/pfm.html)
- [pamtopfm options](https://netpbm.sourceforge.net/doc/pamtopfm.html)
- [pfmtopam options](https://netpbm.sourceforge.net/doc/pfmtopam.html)
- [Upstream pamtopfm.c, writePfmRow](https://svn.code.sf.net/p/netpbm/code/trunk/converter/other/pamtopfm.c)
- [Upstream pfmtopam.c, makePamRow](https://svn.code.sf.net/p/netpbm/code/trunk/converter/other/pfmtopam.c)
