"""Regenerate fixtures with the real Netpbm pamtopfm executable on PATH."""

import argparse
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="compare output without changing fixtures"
    )
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent
    subprocess.run(["pamtopfm", "-version"], check=True)
    for name, extension in [("grayscale", "pgm"), ("rgb", "ppm")]:
        for endian in ["little", "big"]:
            for scale in ["0.5", "1", "2"]:
                source = directory / (name + "." + extension)
                target = directory / f"{name}-{endian}-scale-{scale}.pfm"
                result = subprocess.run(
                    ["pamtopfm", f"-endian={endian}", f"-scale={scale}", str(source)],
                    check=True,
                    stdout=subprocess.PIPE,
                )
                if args.check:
                    if result.stdout != target.read_bytes():
                        raise SystemExit(f"Netpbm output differs from {target.name}")
                else:
                    target.write_bytes(result.stdout)
                print(target.name)


if __name__ == "__main__":
    main()
