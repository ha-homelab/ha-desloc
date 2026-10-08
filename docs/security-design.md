# Security design and verification

## Scope and trust boundaries

The project provides the unofficial Home Assistant integration for DESLOC cloud-controlled locks.

The integration can operate a physical lock. Protect Home Assistant config entries, app sessions and backups. Cloud requests use verified HTTPS to a fixed origin and refuse redirects; errors must omit credentials and raw vendor bodies. The vendor login protocol hashes password plus a fixed suffix with SHA-256. This fast deterministic transform is a protocol requirement, not a modern password-storage KDF; changing it locally breaks vendor authentication and does not fix the vendor protocol.

## Source and operating documentation

- [custom_components/desloc/api.py](../custom_components/desloc/api.py)
- [docs/authentication.md](../docs/authentication.md)
- [docs/protocol.md](../docs/protocol.md)
- [docs/compatibility.md](../docs/compatibility.md)

## Regression evidence

- [tests/test_authentication.py](../tests/test_authentication.py)
- [tests/test_device_mac_boundary.py](../tests/test_device_mac_boundary.py)
- [tests/test_diagnostics.py](../tests/test_diagnostics.py)

Run the documented commands in [CONTRIBUTING.md](../CONTRIBUTING.md) and the
[CI workflow](../.github/workflows/ci.yml). Preserve negative tests for rejected inputs,
unavailable dependencies, authorization failures and cancellation. A passing
test run describes its fixtures and environment; it does not certify every
upstream service, hardware model or production deployment.

## Remaining security assessment

CodeQL alert #10 (weak-sensitive-data-hashing) concerns the required vendor login transform. Keep it visible for protocol review; do not disguise it as a safe password KDF or mark cryptographic weaknesses resolved without evidence.

Report new issues through [SECURITY.md](../SECURITY.md). An OpenSSF assessment
records evidence and applicability; it is not a guarantee that a system is safe.
