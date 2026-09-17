# Development and quality checks

Use Python 3.12 for the complete developer harness. The library's advertised
Python 3.7–3.12 versions are also tested separately in CI.

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
those pins together. The virtualenv pin preserves Python 3.7 test support; CI
runs tox under Python 3.12 and selects each target test interpreter separately. Recreate environments with `tox run -r` when diagnosing
dependency changes. Transitive and runtime dependencies are resolved by pip;
these pins are not a complete dependency lockfile.

## CI and merge protection

The `Quality` workflow runs the identical pre-commit command on Python 3.12,
plus installed-wheel tests and coverage on Python 3.7–3.12. All checks are
blocking, and the stable **Quality gate** job fails if any prerequisite fails or
is cancelled. CI runs on pushes and pull requests without path filters.

The proposed `main` protection requires the **Quality gate** check from the
GitHub Actions app, with branches up to date before merging. It applies to
repository administrators and disables force pushes and branch deletion. Once
applied, local hook bypasses do not bypass this server-side check requirement.
The live settings change is pending owner approval; a merged policy file alone
does not enable protection.

The intended settings are recorded in
[.github/branch-protection.json](.github/branch-protection.json). An administrator
can inspect the active settings with:

```bash
gh api repos/MartinPeris/justPFM/branches/main/protection
```

The JSON file documents the policy; changing it in a PR does not automatically
change GitHub settings. Apply updates deliberately through branch protection
settings or the API, preserving any additional protections added since this
policy was recorded. Administrators can still change the protection policy;
it is not an immutable security boundary.
