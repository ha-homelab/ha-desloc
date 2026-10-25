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

The CI source-warning check uses hash-locked Ruff 0.16.5 and checks all maintained
Python files, including tests and release helpers, with `--select F --ignore-noqa`.
Pyflakes error and warning findings must be resolved before merging; the command
exits nonzero for any finding and does not accept inline suppression comments.
Run it in an isolated environment:

```sh
python3 -m venv .venv-ci
.venv-ci/bin/python -m pip install --require-hashes -r scripts/requirements-lint.txt
.venv-ci/bin/python -m ruff check --select F --ignore-noqa .
```

This is a source-warning baseline. Third-party deprecations and security-analysis
findings are tracked separately and are not declared resolved by a clean Ruff run.

Use Linux and Python 3.14.2 or newer. The Home Assistant version and its
dependencies for synthetic tests are pinned in
[`requirements-dev.txt`](../requirements-dev.txt):

```sh
uv venv --python 3.14 .venv-ha
uv pip install --python .venv-ha/bin/python --only-binary=:all: --require-hashes -r requirements-build.txt
uv pip install --python .venv-ha/bin/python --only-binary=:all: --no-binary=homeassistant,pyric --no-build-isolation --require-hashes -r requirements-dev.txt
uv pip check --python .venv-ha/bin/python
.venv-ha/bin/python -m pytest -q
```

Tests use synthetic data, never call DESLOC, and never move a physical lock. They
include real Home Assistant flow/platform loading, invalid authentication,
timeouts, stale reports, and ensuring failed commands are not retried.

An earlier snapshot of the locked Home Assistant 2026.10.0 environment completed
152 synthetic tests on macOS with Python 3.14.7. The subsequent v0.4.0 release
validation completed 180 tests in Linux CI; see the [release results](release-results.md). Earlier runs with Home Assistant
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

### Temporary upstream test baseline

The test environment uses the unmodified official Home Assistant source at
[`ae6f8602aab71b21505ff0974e7440fbff4aac21`](https://github.com/home-assistant/core/commit/ae6f8602aab71b21505ff0974e7440fbff4aac21),
which identifies itself as **2026.11.0.dev0**. This is an unreleased development
snapshot, not a stable Home Assistant release or a recommendation to upgrade
your installed system. It includes the upstream
[Pillow 13 dependency update](https://github.com/home-assistant/core/pull/188252).
The published Home Assistant 2026.10.4 package still requires Pillow 12.3.0.

The source archive and complete dependency closure have SHA-256 hashes in
[`requirements-dev.txt`](../requirements-dev.txt). The build backend is separately
hash-locked in [`requirements-build.txt`](../requirements-build.txt). We explicitly
use **setuptools 84.1.0 instead of the source snapshot's declared 84.0.0**, to fix
[GHSA-xmj3-9gf7-h52w](https://github.com/advisories/GHSA-xmj3-9gf7-h52w).
This is a build-only override, as permitted by
[PEP 517](https://peps.python.org/pep-0517/#recommendations-for-build-frontends-non-normative),
not a claim that 84.1.0 satisfies upstream's exact build pin. The official source
archive remains unchanged. Install the approved backend first, then use
`--no-build-isolation` to prevent an implicit, unverified build dependency
installation. All other dependencies must use binary wheels except
the existing PyRIC 0.1.6.3 dependency, which only publishes a source archive.
That hash-locked archive uses the same setuptools backend without additional
build dependencies. Only Home Assistant and PyRIC may be built from source.
Runtime dependency resolution and `pip check` remain
enabled; no Home Assistant runtime dependency metadata or Pillow requirement is
overridden.

When updating the build backend, rebuild Home Assistant and PyRIC without cached
wheels (`--no-cache-dir` with pip, or `--no-cache` with uv). Compare the installed
package source/data and runtime dependency metadata with the previous build,
then run `pip check` and the full test suite. A successful cached install alone
does not verify a new source build.

All existing tests still run against real Home Assistant. Current CI establishes
compatibility with this pinned snapshot. The
[last successful released-HA test run](https://github.com/ha-homelab/ha-desloc/actions/runs/40151456021)
used Home Assistant 2026.10.3; it is historical evidence, not ongoing stable-version
coverage. The snapshot change affects only development and CI: it does not
upgrade an installed Home Assistant instance or add Pillow to the DESLOC package.

When a published Home Assistant release supports the fixed Pillow version,
replace the source URL in [`requirements-dev.in`](../requirements-dev.in) with
that exact release. Regenerate the
[hash-locked dependencies](../CONTRIBUTING.md#reproducible-python-dependencies),
install them in a fresh environment, and run dependency compatibility checks,
the full synthetic Linux test suite and required CI before merging. Remove the
separate source-build setup only when it is no longer needed. Never force a
Pillow version that conflicts with Home Assistant's package metadata.

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
