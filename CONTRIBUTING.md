# Contributing

Open focused issues and pull requests. Run the Linux tests described in
[development](docs/development.md). Keep documentation and diagrams in English.

Protocol changes require sanitized evidence and tests for success, pending,
failure, and ambiguous state. New models require physical-device verification.
Never add automatic retries of lock/unlock requests.

Do not commit private captures, account sessions, CA material, identifiers, or
household configuration. Use synthetic fixtures. Read [SECURITY.md](SECURITY.md)
before reporting vulnerabilities.
