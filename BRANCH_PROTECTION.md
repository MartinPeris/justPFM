# Branch protection

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
