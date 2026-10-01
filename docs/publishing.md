# HACS and Home Assistant Core

## Custom repository

The project uses `custom_components/desloc/`, root `hacs.json`, a versioned
manifest, code owner, issue tracker, and local brand icon. Its public GitHub URL
can be added as a HACS custom repository. This is separate from default catalog
inclusion or endorsement. See the official
[integration requirements](https://www.hacs.xyz/docs/publish/integration/) and
[general requirements](https://www.hacs.xyz/docs/publish/start/).

## Default HACS catalog

Before submitting, verify custom-repository installation, pass HACS validation
and Hassfest without ignored errors, and publish a GitHub release after those
checks. The owner or a major contributor can then submit a PR to `hacs/default`.
Acceptance and timing belong to its maintainers; see
[the submission process](https://www.hacs.xyz/docs/publish/include/).

Capture-based setup and unknown session lifetime must remain prominent.
Reliable renewal and broader testing would improve readiness for general users.
No default-catalog acceptance is claimed.

## Home Assistant Core

Core inclusion is a separate contribution process. This experimental project is
not ready for submission. First establish maintainable authentication/renewal,
extract the protocol client into a separately maintained Python library, expand
tests and diagnostics, verify model/region scope, and meet current integration
quality and documentation requirements.

Consult the official [contribution documentation](https://developers.home-assistant.io/docs/creating_integration_file_structure/)
and [integration quality scale](https://developers.home-assistant.io/docs/integration_quality_scale/).
The current project remains an independently distributed custom integration.
