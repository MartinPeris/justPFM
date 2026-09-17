# justPFM
A small Python module to read/write PFM (Portable Float Map) images

## Install

```bash
pip install justpfm
```

## Usage

```python
import numpy as np
from justpfm import justpfm

# Write a test PFM file
data_to_write = np.ones((5, 5), dtype="float32")
justpfm.write_pfm(file_name="test.pfm", data=data_to_write)

# Read the test PFM file
read_data = justpfm.read_pfm(file_name="test.pfm")
```

That's it!

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and commit-hook installation.
Run `pre-commit run --all-files` to execute the same lint, formatting, tests,
100% statement/branch coverage, and packaging gates used by CI.
