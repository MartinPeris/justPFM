# Python support policy

This project supports standard, GIL-enabled CPython **3.7–3.14**. Python 3.7
compatibility is intentionally retained. Every listed version must pass the
installed-wheel tests and 100% statement and branch coverage on Linux. PyPy,
free-threaded Python, and prereleases are not claimed as tested configurations.
Native Windows/macOS testing is deferred in issue #31; Linux coverage does not
establish platform-specific behavior.

Package metadata retains `>=3.7, <4`. Versions newer than the tested range may
install, but are not supported until added to CI. Classifiers and the matrix
explicitly name every tested version. NumPy is resolved per interpreter so
older Pythons receive compatible versions. Existing published artifacts remain
unchanged; this work does not publish a package or change the minimum Python.

## Legacy and current test tooling

The developer harness runs under Python 3.12, independently of the target test
interpreter. Python 3.7–3.9 use compatible pinned pytest, pytest-cov, coverage,
and Hypothesis releases; Python 3.10–3.14 use newer pins supporting current
interpreters. Both tracks run the same tests and enforce the same coverage gate.
The Hypothesis pins in `pyproject.toml` and `tox.ini` must stay aligned.

Virtualenv remains at patched 20.36.1 to retain legacy target creation. Python
3.7 uses explicitly downloaded compatible seed packages as documented in
CONTRIBUTING. Do not upgrade the builder past its legacy target support without
revalidating all eight interpreters. Test the package wheel, not a source-path
shortcut, when changing dependencies or build configuration.

## Maintaining the range

Review support before each release using the official
[CPython lifecycle](https://devguide.python.org/versions/). Add a new stable
version after the whole harness passes. Remove a listed version only through
an explicit owner-approved change to metadata, CI, and these notes.

As assessed on September 18, 2026, CPython 3.7–3.9 are upstream end-of-life.
Library compatibility testing does not restore interpreter security support;
use a maintained Python for new deployments where possible. Python 3.10 has
upstream security support until October 2026. Python 3.15 is prerelease and is
not in this tested range. These dates guide reviews, not automatic removals.
