# Security

This integration can operate a physical lock through the user's DESLOC account.
Treat app sessions and Home Assistant backups as credentials. The runtime uses
verified HTTPS to a fixed origin, refuses redirects, and omits credentials and
raw server bodies from errors.

Never publish captures, tokens, CA keys, account data, or config-entry contents.
Remove the temporary capture profile/proxy after setup. If a session is exposed,
use vendor account controls and contact DESLOC for revocation guidance; this
project has not established a revocation API.

Report vulnerabilities through GitHub's private vulnerability reporting when
available. Otherwise contact the maintainer via their GitHub profile to arrange
a private channel before sharing sensitive details. Do not publish working
tokens or authenticated unlock requests in issues.

Only the latest release receives fixes. Unknown session lifetime and changes to
the undocumented cloud API remain experimental limitations.
