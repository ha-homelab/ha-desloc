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
full release comment. `python3 scripts/check_ci_actions.py` checks this in CI.
Run its regression cases with
`python3 -m unittest discover -s scripts -p 'test_ci_actions.py'`.

CodeRabbit autofix requests use the `californiantiramisu` automation account,
which needs repository Write access. A posted command alone is not proof of
success: inspect the CodeRabbit response and resulting commits.
