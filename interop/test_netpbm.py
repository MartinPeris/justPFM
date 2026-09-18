"""Live writer interoperability; invoked explicitly by tox -e interop and CI."""

import subprocess
from pathlib import Path

import numpy as np
import pytest

from justpfm import write_pfm

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "netpbm"


@pytest.mark.parametrize(
    "name,extension,channels", [("grayscale", "pgm", 1), ("rgb", "ppm", 3)]
)
@pytest.mark.parametrize("dtype", ["<f4", ">f4"])
@pytest.mark.parametrize("scale", [0.5, 1, 2])
def test_netpbm_reads_justpfm_output(tmp_path, name, extension, channels, dtype, scale):
    fields = (FIXTURES / (name + "." + extension)).read_text().split()
    width, height, maxval = map(int, fields[1:4])
    normalized = np.array(fields[4:], dtype=np.float32).reshape(height, width, channels)
    normalized /= maxval
    # Netpbm divides by the header scale, so provide its expected stored samples.
    # Supplying scale=1 is the convention-neutral interchange path.
    samples = (normalized * scale).astype(dtype)
    path = tmp_path / "from-justpfm.pfm"
    write_pfm(path, samples, scale=scale)
    result = subprocess.run(["pfmtopam", str(path)], check=True, capture_output=True)
    header, raster = result.stdout.split(b"ENDHDR\n", 1)
    lines = header.decode("ascii").splitlines()
    assert lines[0] == "P7"
    attributes = dict(line.split(maxsplit=1) for line in lines[1:])
    assert attributes == {
        "WIDTH": str(width),
        "HEIGHT": str(height),
        "DEPTH": str(channels),
        "MAXVAL": "255",
        "TUPLTYPE": "GRAYSCALE" if channels == 1 else "RGB",
    }
    pixels = np.frombuffer(raster, dtype=np.uint8).reshape(height, width, channels)
    # PAM converts normalized floats to nearest integer, with ties rounded up.
    expected = np.floor(normalized.astype(np.float64) * 255 + 0.5).astype(np.uint8)
    np.testing.assert_array_equal(pixels, expected)
