# Development

Runtime code is in `custom_components/desloc/`: `api.py` implements requests and
parsing, `coordinator.py` handles polling and command confirmation, `config_flow.py`
handles setup/reauthentication, and entity modules expose state. Mimic is a
development dependency only.

## Validation

Use Linux and Python 3.14:

```sh
uv venv --python 3.14 .venv-ha
uv pip install --python .venv-ha/bin/python -r requirements-dev.txt
.venv-ha/bin/python -m pytest -q
```

Tests use synthetic data, never call DESLOC, and never move a physical lock. They
include real Home Assistant flow/platform loading, invalid authentication,
timeouts, stale reports, and ensuring failed commands are not retried.

On macOS, assertions passed but Python crashed during finalization with 3.14.2
and 3.14.7. This remains unresolved. Linux runs complete normally and are the
runtime validation target.

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
