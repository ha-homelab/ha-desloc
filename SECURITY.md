# Security

This integration can operate a physical lock through the user's DESLOC account.
Treat app sessions and Home Assistant backups as credentials. The runtime uses
verified HTTPS to a fixed origin, refuses redirects, and omits credentials and
raw server bodies from errors.

Never publish captures, tokens, CA keys, account data, or config-entry contents.
Remove the temporary capture profile/proxy after setup. If a session is exposed,
use vendor account controls and contact DESLOC for revocation guidance; this
project has not established a revocation API.

Report vulnerabilities through the
[private vulnerability reporting form](https://github.com/ha-homelab/ha-desloc/security/advisories/new).
Do not publish working tokens or authenticated unlock requests in issues.

Only the latest release receives fixes. Unknown session lifetime and changes to
the undocumented cloud API remain experimental limitations.

## Response commitments

Maintainers aim to acknowledge private reports within 14 days; follow up
privately if there is no response. Triage confirmed issues by impact, prioritize
critical defects, and coordinate remediation/disclosure with the reporter.
Security changes must have release notes with affected versions and upgrade
actions. Fixes target the current default branch and latest release, rather than
unmaintained historical versions. These are project policies, not assertions
about the existence or response times of past reports.

See [security design](docs/security-design.md) for project-specific trust boundaries.
