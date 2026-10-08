# Development

Runtime code is in `custom_components/desloc/`: `api.py` implements requests and
parsing, `coordinator.py` handles polling and command confirmation, `config_flow.py`
handles setup/reauthentication, and entity modules expose state. Mimic is a
development dependency only.

`account.py` shares the transport and a complete device-list snapshot between
loaded lock entries with identical saved session credentials, including the app
installation ID and request headers. Normal polls reuse the snapshot for at most
five seconds and share an in-flight paginated read. Lock command confirmation
bypasses the cache and waits for a request started after confirmation polling
begins; an older in-flight read cannot confirm the command. A cancelled waiter
does not cancel other locks' shared read. Unloading the last entry, including
failed setup, releases the session and any remaining request task.

HTTP 429 pauses new requests from the shared session for 60 seconds. It never
replays a lock command, user creation, or PIN write. A rejected authentication
session remains blocked even when a successful device snapshot was cached.
Changing saved credentials creates a separate session during reauthentication.

## Validation

Use Linux and Python 3.14.2 or newer. The locked synthetic test runtime is
Home Assistant 2026.10.0:

```sh
uv venv --python 3.14 .venv-ha
uv pip install --python .venv-ha/bin/python --require-hashes -r requirements-dev.txt
.venv-ha/bin/python -m pytest -q
```

Tests use synthetic data, never call DESLOC, and never move a physical lock. They
include real Home Assistant flow/platform loading, invalid authentication,
timeouts, stale reports, and ensuring failed commands are not retried.

The current locked Home Assistant 2026.10.0 environment also completes all 152
synthetic tests on macOS with Python 3.14.7. Earlier runs with Home Assistant
2026.9.1 crashed during interpreter finalization on macOS; that outcome was not
reproduced with the updated lock. Linux CI remains the required runtime target.
Third-party `backoff` deprecation warnings about Python 3.16 remain visible; they
do not affect the supported Python 3.14 test runtime.

An optional helper tests in an existing HA container that already has pytest:

```sh
.venv-ha/bin/python scripts/verify_ha_runtime.py \
  --context YOUR_CONTEXT --namespace YOUR_NAMESPACE --pod YOUR_HA_POD
```

Only source, synthetic tests, and a pure-Python test plugin are transferred to a
temporary directory. It does not read `/config`, install packages, restart HA,
transfer account sessions, or issue device commands. Temporary files are removed.

## Protocol research

Follow [the capture guide](authentication.md), then use:

```sh
.venv/bin/python scripts/capture.py mimic hosts
.venv/bin/python scripts/capture.py mimic learn appadmin.desloc.com
.venv/bin/python scripts/inspect_capture.py
```

Keep even structural inspection output private: paths may contain identifiers.
Do not feed authenticated captures to hosted code generators. These tools do not
use mimic's external AI generation feature.

New models need observed requests, responses, and physical state confirmation.
Do not guess endpoints or numeric state mappings. Main-session renewal is
separate from the observed IoT-token exchange.
