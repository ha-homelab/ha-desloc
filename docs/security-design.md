# Security design and verification

## Scope and trust boundaries

The project provides the unofficial Home Assistant integration for DESLOC cloud-controlled locks.

The integration can operate a physical lock. Protect Home Assistant config entries, app sessions and backups. Cloud requests use verified HTTPS to a fixed origin and refuse redirects; errors must omit credentials and raw vendor bodies. The vendor login protocol hashes password plus a fixed suffix with SHA-256. This fast deterministic transform is a protocol requirement, not a modern password-storage KDF; changing it locally breaks vendor authentication and does not fix the vendor protocol.

## Supported HTTPS runtime profile

The integration keeps Home Assistant's shared aiohttp session and supplies an
owned SSL context for each DESLOC client. Its trust bundle follows Home
Assistant's `REQUESTS_CA_BUNDLE` override or certifi default. Context creation
runs off the event loop; the shared session and its cached context are not
mutated. The owned context retains normal CA/hostname verification, a minimum
of TLS 1.2, OpenSSL security level 2 or higher, and any stronger default policy.

After the ordinary verified handshake, the client checks **every certificate
in the verified chain**, including the trust anchor, before HTTP data is sent.
RSA moduli must have at least 2048 actual bits; EC keys at least 224 bits; DSA
parameters at least 2048/224 bits. Ed25519 and Ed448 are accepted. Unknown key
formats or a runtime without a verified-chain API fail closed. This extra
check matters because OpenSSL security level 2 alone can accept RSA-2047.

[The regression](../tests/test_tls.py) uses the actual `DeslocClient._raw_request`
through `async_get_clientsession` under TLS 1.2 and 1.3. Trusted RSA-2047 leaf,
intermediate and omitted-from-the-wire root certificates are rejected before
HTTP headers, body or the synthetic session token reaches the server. Strong
RSA-2048 chains succeed. Each fixture first succeeds with a separately verified,
hostname-checked calibration client, priming the shared connection pool; the
strict request cannot reuse that connection. DNS discovery is disabled and all
requests are to numeric loopback. No vendor request or lock operation is part
of the test. The suite also preserves an explicitly stronger TLS 1.3/security
level 3 context and rejects a missing configured trust bundle.

Run `python -m pytest -q tests/test_tls.py` in the hash-pinned Python 3.14
[development environment](../CONTRIBUTING.md). The October 16 local run used
Home Assistant 2026.10.0, aiohttp 3.14.4 and CPython 3.14.7. CI runs the same
regression on Linux. A separate unauthenticated TLS handshake to
`appadmin.desloc.com:443` on 2026-10-17 UTC succeeded with TLS 1.3 and a
three-certificate RSA-2048 chain; it sent no HTTP request or credential.
The result describes that endpoint at that time, not a permanent guarantee. A successful synthetic run does not certify a vendor
service, a different interpreter, or every installation. TLS transport does
not repair the vendor's fixed-suffix password transform or make its fixed AES
wrapper secret; that protocol limitation remains explicitly documented.

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

The required outbound vendor login transform was reviewed under CodeQL alert #10
and retained for protocol compatibility, with an explicit “won't fix” disposition.
The [dated evidence record](openssf-evidence.md#unresolved-criteria-and-applicability)
explains its password-equivalent role inside verified TLS. This is not a safe
password-storage KDF or a repair of vendor-side cryptographic limitations.

Report new issues through [SECURITY.md](../SECURITY.md). An OpenSSF assessment
records evidence and applicability; it is not a guarantee that a system is safe.
