# Contributing

Open focused issues and pull requests. Run the Linux tests described in
[development](docs/development.md). Keep documentation and diagrams in English.

Protocol changes require sanitized evidence and tests for success, pending,
failure, and ambiguous state. New models require physical-device verification.
Never add automatic retries of lock/unlock requests.

Do not commit private captures, account sessions, CA material, identifiers, or
household configuration. Use synthetic fixtures. Read [SECURITY.md](SECURITY.md)
before reporting vulnerabilities.

See [governance](GOVERNANCE.md), the [Code of Conduct](CODE_OF_CONDUCT.md), and the
[maintenance roadmap](ROADMAP.md) for project roles, private conduct reporting,
decision-making and current priorities.

## Test and security review policy

Behavior changes require automated regression coverage, or a documented reason
and reproducible manual procedure when automation is infeasible. Update affected
user/API documentation and release notes. Keep assertions and static-analysis
checks enabled, resolve new warnings, and explain any remaining warning in the
PR. Use the private process in SECURITY.md for vulnerabilities. Required checks
and independent review must pass before merging; do not bypass protections.

For the public `main` branch, the required `CI gate` aggregates the test suite,
HACS/Hassfest validation, CodeQL, dependency review, and workflow and release
contracts. The PR must be up to date with `main`, have at least one independent
approval covering the latest push, and have no unresolved review threads.
New commits invalidate stale approvals; administrators follow the same merge
requirements.

The existing shared CodeRabbit workflow requests code review. CodeRabbit can
approve after it has reviewed the latest commit, its comments are resolved,
and its pre-merge checks pass. Authors cannot force approval or resolve all
CodeRabbit comments with `@coderabbitai approve` or `@coderabbitai resolve` on
their own PRs. A green status or a `COMMENTED` review is not an approval.
Trusted-author metadata alone is not grounds for approving a change.

## Reproducible Python dependencies

The `.in` files declare direct dependencies. The corresponding `.txt` files pin
all resolved dependencies and approved archive SHA-256 hashes across supported
platforms. Install with `--require-hashes`; do not remove this check to work around
a missing archive. Review dependency updates and regenerate the locks with:

```sh
uv pip compile requirements-dev.in --generate-hashes --universal --python-version 3.14.2 --output-file requirements-dev.txt
```

Run the documented tests in a fresh virtual environment after updating a lock.
The isolated Home Assistant test runtime is 2026.10.0 and requires Python
3.14.2 or newer. Updating these test dependencies does not upgrade an installed
Home Assistant instance.
