# Python support policy

This development branch supports standard, GIL-enabled CPython **3.10–3.14**.
Every listed version must pass the installed-wheel tests and 100% statement
and branch coverage on Linux. PyPy, free-threaded Python, and prereleases are
not claimed as tested configurations. Native Windows/macOS testing is deferred
in issue #31; Linux coverage is not evidence of platform-specific validation.

## Compatibility change

The next release containing this change requires **Python 3.10 or newer**.
Python 3.7–3.9 are no longer installation targets. Existing published artifacts
are unchanged; users who need those versions must keep using a compatible
older release. No package is published by this policy change.

Package metadata requires `>=3.10, <4`. Versions newer than the tested range may
install, but they are not supported until added to CI. Classifiers and the CI
matrix explicitly name each tested version. NumPy is resolved per interpreter
so older supported Pythons can use their compatible NumPy release.

## Maintaining the range

Review the range when preparing each release, using the official
[CPython lifecycle](https://devguide.python.org/versions/). Add a new stable
Python version only after the entire harness passes. Prefer versions receiving
upstream security updates, but remove support only through an explicit reviewed
change to metadata, CI, and these notes—not automatically by calendar date.

As assessed on September 18, 2026, Python 3.10 remains in upstream security
support until October 2026. Review that floor at the next release after its
end of life. Python 3.15 is prerelease and is not in the supported matrix.

Developer tooling runs on Python 3.12. Bootstrap, test, and package-check tools
are pinned; update the matching pins together. The linter remains configured
for conservative Python 3.7-compatible syntax, which is valid throughout the
supported range; the policy does not require gratuitous source rewrites.
