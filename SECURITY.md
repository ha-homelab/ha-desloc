# Security

This integration can operate a physical lock through the user's DESLOC account.
Treat app sessions and Home Assistant backups as credentials. The runtime uses
verified HTTPS to a fixed origin, refuses redirects, and omits credentials and
raw server bodies from errors.

Never publish captures, tokens, CA keys, account data, or config-entry contents.
Remove the temporary capture profile/proxy after setup. If a session is exposed,
use vendor account controls and contact DESLOC for revocation guidance; this
project has not established a revocation API.

The vendor's password-login protocol uses a fast SHA-256 digest with a fixed
suffix. Anyone who obtains that digest can attempt offline password guessing;
the protocol's public fixed AES key does not protect a captured login body.
Use a strong, unique account password and retain verified HTTPS. The integration
does not log the password/digest or save them in config entries. A compatible
server-side protocol change is needed to remove this limitation. See the
[authentication protocol and mitigations](docs/protocol.md#authentication).

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
