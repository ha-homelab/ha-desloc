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

CodeQL alert #10 (weak-sensitive-data-hashing) concerns the required vendor login transform. Keep it visible for protocol review; do not disguise it as a safe password KDF or mark cryptographic weaknesses resolved without evidence.

On 2026-10-16 the maintainer confirmed that the same secure-design/common-error
knowledge and absence of outside-GitHub bug, enhancement and vulnerability
reports over the preceding 12 months apply to this project. The current public
GitHub issue inventory contains no non-PR reports, and private vulnerability
reporting is enabled. These are dated observations, not promises about future
reports. Do not transfer another project's test results or badge identifier.

The current scanner inventory has five open entries: the vendor password-hash
CodeQL warning and four Scorecard process recommendations. There are zero open
Dependabot alerts; this does not prove every runtime or release-tool dependency
is free from vulnerabilities. The password-transform warning remains open.

Version 0.4.0 has published change notes and source-bound release provenance.
Its release states that it does not establish new physical-device testing or a
security fix. Complete runtime cryptographic qualification, dependency review,
whole-source coverage and per-language analysis remain separate work. The
existing RSA1024 rejection tests do not establish the exact RSA2048 minimum at
every boundary; no new test result is asserted by this documentation update.

[Governance](../GOVERNANCE.md), [conduct rules](../CODE_OF_CONDUCT.md), and the
[roadmap](../ROADMAP.md) document current responsibilities and limitations.
There is still no backup maintainer or one-week access-recovery arrangement.

Record each completed analysis with its source SHA, commands/tool versions,
result and material limitations. Add the repository's actual badge only after
its own public assessment is saved and verified.
