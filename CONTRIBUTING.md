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
and the review policy must pass before merging; do not bypass protections.

For the public `main` branch, the required `CI gate` aggregates the test suite,
HACS/Hassfest validation, CodeQL, dependency review, and workflow and release
contracts. The PR must be up to date with `main`, pass `Review policy`, and have
no unresolved review threads. Administrators follow the same merge requirements.

`Review policy` normally requires a formal approval for the current head commit
from CodeRabbit or a collaborator with write, maintain, or admin access, other
than the PR author. An active request for changes blocks the policy. A new push
requires a new approval; a comment alone does not supersede a review decision.

The one exception is a verified CodeRabbit quota refusal: its latest status on
the current head must be `success` with the exact description `Review rate limited`,
published by the authentic CodeRabbit bot. This permits merging without a new
approval when the review allowance is exhausted. The status description explicitly
records the exception; it does not claim that a review occurred. Required CI and
resolved review threads still apply. Older quota signals, unknown errors, and
unverified identities do not qualify. A newer CodeRabbit status replaces the
old quota signal.

Changes to the review-event listener require a real approval; they cannot use
the quota exception. A scheduled reconciliation recovers missed events, but
status updates are asynchronous. Open PRs must use distinct head commits because
a commit status cannot represent separate reviews of the same commit.

The policy is a pinned shared workflow running from trusted base-branch code.
It reads live GitHub metadata and never executes PR code. Native approval-count
and last-push-approval rules cannot express this conditional exception, so the
required policy check replaces them. Reviewer independence is checked against
the PR author; this does not assert that the reviewer was not the last pusher.

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
