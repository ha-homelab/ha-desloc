# OpenSSF Passing evidence

This is a source-backed work record for the [OpenSSF Best Practices Passing
criteria](https://www.bestpractices.dev/en/criteria/0). It does not assert that a
badge has been awarded. The partial [machine-readable assessment](../.bestpractices.json)
leaves unverified criteria unknown.

## Available evidence

- Purpose, installation and operating limitations: [README](../README.md).
- Public Git source, commit history and change proposals: [ha-homelab/ha-desloc](https://github.com/ha-homelab/ha-desloc).
- Bug reports and retained discussion: [issues](https://github.com/ha-homelab/ha-desloc/issues).
- Contribution requirements, test policy and test invocation: [CONTRIBUTING](../CONTRIBUTING.md).
- Private reporting process and response policy: [SECURITY](../SECURITY.md).
- Trust boundaries, source references and negative-test evidence: [security design](security-design.md).
- Build/test automation: [workflow](../.github/workflows/ci.yml) and [actual run results](https://github.com/ha-homelab/ha-desloc/actions).
- Project license: [MIT](../LICENSE); third-party terms still apply.

## Initial scanner inventory — 2026-10-08

The authenticated GitHub inventory found 10 open code-scanning alerts
(including Scorecard policy findings) and 0 open Dependabot alerts.
This is a dated baseline, not a statement about the post-merge state. A scanner
configuration error or disabled scanner must not be recorded as zero findings.
Check [Code scanning](https://github.com/ha-homelab/ha-desloc/security/code-scanning) and
[Dependabot](https://github.com/ha-homelab/ha-desloc/security/dependabot) after the changed default branch is
analyzed.

## Unresolved criteria and applicability

[CodeQL alert #10](https://github.com/ha-homelab/ha-desloc/security/code-scanning/10)
(weak-sensitive-data-hashing) was reviewed and dismissed as “won't fix” on
2026-10-17 for explicit vendor-protocol compatibility. The required fast digest
is a temporary outbound password-equivalent sent only through verified,
fixed-origin TLS; the integration stores the returned session credentials,
not a password-verifier database. Replacing the transform locally would break
login. This disposition does not make the digest a safe password KDF or repair
vendor-side password handling; the documented protocol limitations remain.

On 2026-10-16 the maintainer confirmed that the same secure-design/common-error
knowledge and absence of outside-GitHub bug, enhancement and vulnerability
reports over the preceding 12 months apply to this project. The current public
GitHub issue inventory contains no non-PR reports, and private vulnerability
reporting is enabled. These are dated observations, not promises about future
reports. Do not transfer another project's test results or badge identifier.

The 2026-10-17 authenticated scanner inventory has no open CodeQL findings and
four open Scorecard process recommendations. The deliberate RSA-2047 fixture
in the actual-client TLS regression is separately marked as test use; the
production client must reject it before sending HTTP. No analysis rule was
disabled. An empty CodeQL inventory does not prove every runtime or release-tool
dependency is free from vulnerabilities.

Version 0.4.0 has published change notes and source-bound release provenance.
Its release states that it does not establish new physical-device testing or a
security fix. Complete runtime cryptographic qualification, dependency review,
whole-source coverage and per-language analysis remain separate work. The
[actual-client TLS regression](../tests/test_tls.py) now checks exact RSA-2047
rejection at the leaf, intermediate and trusted root and RSA-2048 acceptance
under TLS 1.2 and 1.3. The [security profile](security-design.md) states its
trust and runtime limits; it does not resolve the vendor protocol weakness.

[Governance](../GOVERNANCE.md), [conduct rules](../CODE_OF_CONDUCT.md), and the
[roadmap](../ROADMAP.md) document current responsibilities and limitations.
There is still no backup maintainer or one-week access-recovery arrangement.

Record each completed analysis with its source SHA, commands/tool versions,
result and material limitations. Add the repository's actual badge only after
its own public assessment is saved and verified.

## Source warnings and credential scan (2026-10-16)

Ruff 0.16.5 reports no Pyflakes findings for maintained Python source, tests and
release helpers with `ruff check --select F --ignore-noqa .`; the same check is
required in CI with hashed installation artifacts. This does not resolve the
vendor protocol weakness or upstream deprecation warnings.

A full-history Gitleaks 8.30.1 scan after unshallowing the repository inspected
52 commits (about 1.88 MB) using its default rules and `git --log-opts=--all`.
The one finding was manually reviewed: `tests/test_pin_users.py:42` in commit
`18f2df7259a00c4a0ade29efa1621c18f288fd2c` is the expected encrypted output
for the public synthetic test PIN, synthetic guest and mocked HTTP response.
It is not an account password or token. No private credential was identified;
no detector, path or commit was excluded to obtain that conclusion. This
bounded scan is not a guarantee that arbitrary secrets are detectable.
