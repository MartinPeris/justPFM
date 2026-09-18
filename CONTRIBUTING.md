# Development and quality checks

Use Python 3.12 for the complete developer harness. The library's advertised
Python 3.7–3.14 versions are also tested separately in CI.

## Set up once per clone

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
pre-commit install --install-hooks
```

Keep `.venv` available: the installed Git hook uses its Python interpreter.
The first run downloads isolated tooling and test dependencies. Subsequent runs
reuse those environments, but package builds can still require network access.

## Run the same checks as CI

```bash
pre-commit run --all-files
```

The hook runs `tox run`, which executes all three environments:

| Environment | Required checks |
| --- | --- |
| `lint` | Ruff lint, import ordering, and formatting; failures block commits |
| `py` | Build and install a wheel, run pytest, require 100% statement and branch coverage |
| `package` | Build an sdist, build a wheel from it, validate both artifacts with `twine check --strict` |

During `git commit`, pre-commit temporarily stashes unstaged changes so checks
see the staged contents of tracked files. The entire harness runs even for a
documentation-only commit, with no automatic source edits. A nonzero result
aborts the commit. Stage all new files that belong to your change before running
the checks; local untracked files are not part of the commit.

Git does not install hooks when cloning. Every contributor must run the setup
above. Local hooks can be bypassed with Git's `--no-verify` or pre-commit's
`SKIP`, so CI is the independent enforcement layer.

## Fix a failure

Read the failing environment's output. To apply formatting and safe lint fixes:

```bash
tox run -e lint  # Creates the lint environment, even if checks fail.
.tox/lint/bin/ruff check --fix .
.tox/lint/bin/ruff format .
pre-commit run --all-files
```

Review and stage the fixes before retrying the commit. On Windows, the Ruff
executable is under `.tox/lint/Scripts/` instead.

To run only the tests while developing:

```bash
tox run -e py
```

Coverage includes every installed `justpfm` module and branches. The terminal
report identifies missing lines and branches; `coverage.xml` is also produced
and uploaded by CI. Add behavior-focused tests for new code instead of lowering
the threshold or adding exclusions. The tests use temporary files and import
`justpfm` from the installed wheel, without adding `src` to Python's import path.
A passing 100% coverage report does not prove all inputs are correct; independent
binary fixtures and nonuniform images check behavior beyond line execution.

Tool versions are centralized in `tox.ini` and `requirements-dev.txt`; the hook
also pins tox and virtualenv to bootstrap its isolated environment. Update
those pins together. Virtualenv 20.36.1 includes the directory-creation security
fix. CI runs tox under Python 3.12 and selects each target test interpreter
separately. Python 3.7 remains a supported target, but its compatible seed
packages are no longer bundled. That compatibility job enables seed downloads
and selects pip 24.0, setuptools 68.0.0, and wheel 0.42.0 explicitly. For local
Python 3.7 tests, use the same environment variables:

```bash
VIRTUALENV_DOWNLOAD=true VIRTUALENV_PIP=24.0 \
VIRTUALENV_SETUPTOOLS=68.0.0 VIRTUALENV_WHEEL=0.42.0 \
JUSTPFM_TEST_PYTHON=python3.7 tox run -r -e py
```

Recreate environments with `tox run -r` when diagnosing dependency changes. Transitive and runtime dependencies are resolved by pip;
these pins are not a complete dependency lockfile.

## CI and merge protection

The `Quality` workflow runs the identical pre-commit command on Python 3.12,
plus installed-wheel tests and coverage on Python 3.7–3.14. All checks are
blocking, and the stable **Quality gate** job fails if any prerequisite fails or
is cancelled. CI runs on pushes and pull requests without path filters.

In GitHub's branch protection or ruleset settings for `main`, require the
**Quality gate** status check before merging, preferably with the branch up to
date. The workflow alone does not configure repository protection. At the time
this harness was introduced, `main` had no branch protection.


## Release validation

The `Release` workflow calls the same `Quality` workflow, including all Python
compatibility tests, for the triggering commit. Its distribution job depends
on the complete quality workflow succeeding. Both checks and builds explicitly
check out `github.sha`, so a passing check on a different commit cannot authorize
publication. A failure or cancellation prevents building and publishing.

Workflow pull requests and manual runs perform a dry run: quality checks,
source/wheel builds, strict metadata validation, and artifact upload. The PyPI
publish step runs only on a `release: published` event. Use the manual `Release`
workflow on a feature branch to exercise the path without publishing a package.
Release changes should be merged before creating the release tag; publication
uses the workflow from that release commit.


See [SUPPORT.md](SUPPORT.md) for the compatibility policy. Test-tool pins in
`tox.ini` select legacy versions on Python 3.7–3.9 and current versions on
Python 3.10–3.14. Both tracks run the same tests and 100% coverage gate. Update
Hypothesis pins in the test extra together with tox so installation paths agree.
