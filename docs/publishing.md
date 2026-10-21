# HACS and Home Assistant Core

## Default HACS catalog

The [integration submission](https://github.com/hacs/default/pull/11471) was
merged on October 20, 2026. Install the integration by searching for **DESLOC**
in HACS; see the [installation guide](../README.md#installation).

The separate dashboard card is not yet included in the default catalog. Its
[submission](https://github.com/hacs/default/pull/11473) remains pending; install
it through the [card's custom repository instructions](https://github.com/ha-homelab/ha-desloc-card#install-through-hacs).

HACS validation and Hassfest must continue to pass without ignored errors.
Catalog inclusion is distinct from Home Assistant Core inclusion or endorsement;
see the official [submission process](https://www.hacs.xyz/docs/publish/include/).

The unofficial cloud API, account-verification requirements, and model-specific
testing limits must remain prominent.
Independent concurrent authentication and broader testing would improve
readiness for general users. The observed session-conflict limitation and
interactive reauthentication requirement must be disclosed.

## Custom repository fallback

The project uses `custom_components/desloc/`, root `hacs.json`, a versioned
manifest, code owner, issue tracker, and local brand icon. Its public GitHub URL
can still be added as a HACS custom repository if needed, but this is no longer
the normal installation path for the integration. See the official
[integration requirements](https://www.hacs.xyz/docs/publish/integration/) and
[general requirements](https://www.hacs.xyz/docs/publish/start/).

## Home Assistant Core

Core inclusion is a separate contribution process. This custom integration is
not ready for submission. First establish maintainable authentication/renewal,
extract the protocol client into a separately maintained Python library, expand
tests and diagnostics, verify additional model/region compatibility, and meet current integration
quality and documentation requirements.

Consult the official [contribution documentation](https://developers.home-assistant.io/docs/creating_integration_file_structure/)
and [integration quality scale](https://developers.home-assistant.io/docs/integration_quality_scale/).
The current project remains an independently distributed custom integration.

## Versioned source releases

The shared [release strategy](../RELEASING.md) and
[packaging runbook](release-packaging.md) define beta/RC artifacts, manifest
versions, receipts and acceptance. This lifecycle does not submit the integration
to HACS/Core or certify a physical lock. The established HACS source-download
mode remains unchanged; use the published `ha-desloc.zip` for exact new candidate
acceptance, since GitHub source archives retain the committed base metadata.
