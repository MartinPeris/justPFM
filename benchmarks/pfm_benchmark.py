"""Opt-in Linux PFM timings against the installed package, with JSON results."""

import argparse
import contextlib
import hashlib
import io
import json
import os
import platform
import resource
import subprocess
import sys
import tempfile
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

import numpy as np

from justpfm import justpfm as implementation
from justpfm import read_pfm, write_pfm


def positive_int(value):
    """Argparse validator for nonempty images and repeated measurements."""
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def nonnegative_int(value):
    """Allow skipping warmup for smoke runs."""
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return parsed


def make_pixels(case):
    """Use identical nonuniform values for contiguous and strided inputs."""
    shape = tuple(case["shape"])
    pixels = np.arange(np.prod(shape), dtype=np.float32).reshape(shape)
    pixels %= 257
    pixels -= 128
    pixels = pixels.astype(case["dtype"], copy=False)
    if case["layout"] == "strided":
        backing_shape = (shape[0], shape[1] * 2) + shape[2:]
        backing = np.empty(backing_shape, dtype=pixels.dtype)
        view = backing[:, ::2]
        view[...] = pixels
        return view
    return pixels


def write_fixture(path, pixels, scale):
    """Build an independent bottom-first PFM outside the measured region."""
    height, width = pixels.shape[:2]
    magic = "PF" if pixels.ndim == 3 else "Pf"
    endian = pixels.dtype.str[0]
    signed_scale = -scale if endian == "<" else scale
    with path.open("wb") as file:
        file.write(f"{magic}\n{width} {height}\n{signed_scale}\n".encode())
        pixels[::-1].tofile(file)


def check_written_file(path, pixels, scale):
    """Check header, scale, and raw pixel order independently of the reader."""
    with path.open("rb") as file:
        assert file.readline().strip() == (b"PF" if pixels.ndim == 3 else b"Pf")
        assert file.readline().strip() == (
            f"{pixels.shape[1]} {pixels.shape[0]}".encode()
        )
        signed_scale = float(file.readline())
        assert abs(signed_scale) == scale
        assert (signed_scale < 0) == (pixels.dtype.str[0] == "<")
        values = np.fromfile(file, dtype=pixels.dtype)
    np.testing.assert_array_equal(values, pixels[::-1].ravel())


def run_worker(case, directory):
    """Each case has its own process, so peak RSS is not shared across cases."""
    pixels = make_pixels(case)
    scale = case["scale"]
    with tempfile.TemporaryDirectory(prefix="justpfm-bench-", dir=directory) as temp:
        path = Path(temp) / "image.pfm"
        if case["operation"] == "read":
            write_fixture(path, pixels, scale)

            def operation():
                return read_pfm(path)

            def validate(result):
                expected = (pixels * scale).reshape(*pixels.shape[:2], -1)
                np.testing.assert_array_equal(result, expected)

        else:
            # Precreate the destination: every sample measures replacement.
            write_fixture(path, pixels, scale)

            def operation():
                return write_pfm(path, pixels, scale=scale)

            def validate(_result):
                check_written_file(path, pixels, scale)

        validate(operation())
        for _ in range(case["warmup"]):
            result = operation()
            del result
        samples = []
        for _ in range(case["repeats"]):
            start = time.perf_counter()
            result = operation()
            elapsed = time.perf_counter() - start
            samples.append(elapsed)
            # Checking and freeing the returned array are outside the timer.
            validate(result)
            del result
        allocation = {}
        if case.get("measure_allocations") and case["operation"] == "write":
            # Separate from timing: input creation and validation are untraced.
            tracemalloc.start()
            try:
                operation()
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            validate(None)
            allocation["write_traced_peak_bytes"] = peak
        result = dict(case)
        result.update(allocation)
        result.update(
            input_strides_bytes=list(pixels.strides),
            input_c_contiguous=bool(pixels.flags.c_contiguous),
            payload_bytes=int(pixels.nbytes),
            file_bytes=path.stat().st_size,
            samples_seconds=samples,
            median_seconds=median(samples),
            payload_mib_per_second=pixels.nbytes / (1024**2) / median(samples),
            process_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        )
        return result


def environment(directory):
    """Record enough environment detail to interpret a run without guessing."""
    cpuinfo = Path("/proc/cpuinfo").read_text()
    cpu_model = next(
        (
            line.split(":", 1)[1].strip()
            for line in cpuinfo.splitlines()
            if line.startswith("model name")
        ),
        "unknown",
    )
    config = io.StringIO()
    with contextlib.redirect_stdout(config):
        np.show_config()
    root = Path(__file__).resolve().parents[1]
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True
    )
    status = subprocess.run(
        ["git", "status", "--short"], cwd=root, capture_output=True, text=True
    )
    filesystem = os.statvfs(directory)
    source = Path(implementation.__file__)
    return {
        "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "python_executable": sys.executable,
        "numpy": np.__version__,
        "numpy_config": config.getvalue(),
        "os": platform.platform(),
        "machine": platform.machine(),
        "cpu_model": cpu_model,
        "cpu_count": os.cpu_count(),
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "host_byte_order": sys.byteorder,
        "library_module": str(source),
        "library_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "git_revision": revision.stdout.strip() if revision.returncode == 0 else None,
        "git_status": status.stdout.strip() if status.returncode == 0 else None,
        "temporary_parent": str(Path(directory).resolve()),
        "filesystem_block_size": filesystem.f_bsize,
        "memory_metric": (
            "Linux process-lifetime peak RSS in KiB, including fixture generation, "
            "correctness checks, warmup and all timed calls; not per-call allocation "
            "or system memory use, and excludes filesystem cache."
        ),
        "allocation_metric": (
            "Optional tracemalloc peak during one additional write after timings; "
            "excludes input creation and validation. Includes Python and NumPy "
            "allocations exposed to tracemalloc, not all native memory or OS cache."
        ),
        "cache_policy": (
            "Warm/cache-eligible files: fixture creation, validation and warmup "
            "precede timings. No cache eviction, fsync, or durability measurement. "
            "Writes replace an existing file atomically; reads include allocation "
            "and optional scaling. Validation and result disposal are not timed."
        ),
    }


def main():
    """Run every selected case serially and save raw samples plus medians."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", type=positive_int, default=[1024, 2048])
    parser.add_argument("--repeats", type=positive_int, default=5)
    parser.add_argument("--warmup", type=nonnegative_int, default=1)
    parser.add_argument(
        "--byte-order", choices=["native", "little", "big"], default="native"
    )
    parser.add_argument("--temp-dir", type=Path, default=Path(tempfile.gettempdir()))
    parser.add_argument("--output", type=Path, default=Path("benchmark-results.json"))
    parser.add_argument(
        "--measure-allocations",
        action="store_true",
        help="measure traced peak allocation in a separate, untimed write",
    )
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("this benchmark records Linux-specific CPU and RSS information")
    if args.worker:
        print(json.dumps(run_worker(json.loads(args.worker), args.temp_dir)))
        return
    dtype = np.dtype({"native": "=f4", "little": "<f4", "big": ">f4"}[args.byte_order])
    report = {
        "schema_version": 1,
        "environment": environment(args.temp_dir),
        "cases": [],
    }
    for size in args.sizes:
        for channels in [1, 3]:
            shape = [size, size] if channels == 1 else [size, size, channels]
            for operation in ["read", "write"]:
                for layout in (
                    ["contiguous", "strided"]
                    if operation == "write"
                    else ["contiguous"]
                ):
                    for scale in [1.0, 2.0]:
                        case = dict(
                            shape=shape,
                            dtype=dtype.str,
                            operation=operation,
                            layout=layout,
                            scale=scale,
                            repeats=args.repeats,
                            warmup=args.warmup,
                            measure_allocations=args.measure_allocations,
                        )
                        command = [
                            sys.executable,
                            str(Path(__file__).resolve()),
                            "--temp-dir",
                            str(args.temp_dir),
                            "--worker",
                            json.dumps(case),
                        ]
                        completed = subprocess.run(
                            command, check=True, stdout=subprocess.PIPE, text=True
                        )
                        measured = json.loads(completed.stdout)
                        report["cases"].append(measured)
                        print(
                            f"{shape} {operation} {layout} scale={scale:g}: "
                            f"{measured['median_seconds'] * 1000:.3f} ms, "
                            f"{measured['payload_mib_per_second']:.1f} MiB/s",
                            file=sys.stderr,
                        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
