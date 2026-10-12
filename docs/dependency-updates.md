# CI dependency updates

GitHub Actions and reusable workflows use the shared Renovate preset from
[venus-os-ci-toolkit](https://github.com/victron-venus/venus-os-ci-toolkit/blob/main/docs/DEPENDENCY_UPDATES.md).
The central runner requires both `renovate.json` in this repository and an entry
in its `renovate-repositories.json` allowlist. CI updates arrive together in a
`renovate/ci-workflows` PR; automatic merging is disabled.

Dependabot Actions PRs are disabled using a zero PR limit and an explicit ignore
rule. Vulnerability alerts and any existing application-package updates remain
enabled. Old standalone Actions PRs should be closed once a grouped PR supersedes
them.

All CodeQL steps, including SARIF uploads, must use the same immutable SHA and
full release comment. Use block-form CodeQL steps: the guard parses executable
YAML steps and rejects compact flow mappings that Renovate cannot reliably
update with their release comments. Comments and shell examples are ignored.
A complete version token may be followed by explanatory text.

To run the same validation locally:

```sh
python3 -m venv .venv-ci
.venv-ci/bin/python -m pip install --require-hashes -r scripts/requirements-ci.txt
.venv-ci/bin/python -m unittest discover -s scripts -p 'test_ci_actions.py'
.venv-ci/bin/python scripts/check_ci_actions.py
```

CodeRabbit autofix requests use the `californiantiramisu` automation account,
which needs repository Write access. A posted command alone is not proof of
success: inspect the CodeRabbit response and resulting commits.
