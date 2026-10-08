# Security design and verification

## Scope and trust boundaries

The project provides the unofficial Home Assistant integration for DESLOC cloud-controlled locks.

The integration can operate a physical lock. Protect Home Assistant config entries, app sessions and backups. Cloud requests use verified HTTPS to a fixed origin and refuse redirects; errors must omit credentials and raw vendor bodies. The vendor login protocol hashes password plus a fixed suffix with SHA-256. This fast deterministic transform is a protocol requirement, not a modern password-storage KDF; changing it locally breaks vendor authentication and does not fix the vendor protocol.

## Supported HTTPS runtime profile

The integration obtains Home Assistant's standard verified aiohttp session.
Its supported TLS profile keeps CA and hostname verification enabled, minimum
TLS 1.2 and OpenSSL security level 2 or higher. It does not install a custom
trust manager, lower the host's cipher policy or disable certificate checks.
Use a maintained Home Assistant/Python installation; custom session overrides
or a vendor-weakened TLS runtime fall outside this profile.

The actual `DeslocClient._raw_request` path through `async_get_clientsession`
was tested with Home Assistant 2026.10.0, CPython 3.14.7, aiohttp 3.14.4 and
OpenSSL 3.6.4. Under TLS 1.2 and 1.3, synthetic trusted chains with RSA 1024-bit
leaf, intermediate or root keys were rejected before HTTP headers/body or the
session token reached the server. Strong RSA 2048-bit chains succeeded. Each
fixture also completed a normally trusted, hostname-checked handshake with a
separate test-only lower-security client. The test changed only the API origin
and trust bundle to loopback fixtures; it blocked DNS discovery and made no
vendor request or physical lock operation.

Inspect the context inside the **actual Home Assistant Python environment**:

```sh
python - <<'PYTHON'
import ssl, sys
from importlib.metadata import version
from homeassistant.util.ssl import get_default_context
context = get_default_context()
print("Home Assistant", version("homeassistant"), "aiohttp", version("aiohttp"))
print(sys.version, ssl.OPENSSL_VERSION, sep="\n")
print("security_level", context.security_level, "minimum_tls", context.minimum_version.name)
assert context.security_level >= 2
assert context.minimum_version >= ssl.TLSVersion.TLSv1_2
assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
PYTHON
```

This local command checks settings without contacting DESLOC. It does not
upgrade the host or certify a vendor service, a different interpreter or a
published installation. TLS transport protection does not repair the vendor's
fixed-suffix password transform or make its fixed AES wrapper secret; the
protocol limitation below remains open.

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
