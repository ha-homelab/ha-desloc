# Model compatibility

The integration automatically adds every lock returned by a DESLOC app account
during setup or reconfiguration. Evidence below distinguishes maintainer checks
from community reports. The project uses an undocumented cloud API, and results
can vary by model, firmware, account, and region.

## C100 Plus — maintainer-tested

The maintainer's installation has physically verified lock/unlock and creation
of a permanent PIN user through the Home Assistant form, including use of that
PIN at the keypad. Discovery, reported bolt state, battery, and Wi-Fi signal
were also observed. The tested baseline is Home Assistant 2026.9.1 with
integration 0.3.0. See the [changelog](../CHANGELOG.md#030--2026-10-01) and
[PIN workflow](pin-users.md).

## D110 Plus — community-reported working

On **October 1, 2026**, **Marty-McFly73** posted this
[success report](https://github.com/home-assistant/feature-requests/discussions/2138#discussioncomment-18702050)
after being invited to try the integration:

> Amazing! Thank you again for this. So far so good with my D110 plus. Works perfectly!

This is a positive real-owner compatibility report for D110 Plus. The comment
does not identify which individual features were tested. In particular, it does
not separately confirm PIN creation or keypad use, both lock command
directions, or each sensor. Firmware, region, Home Assistant version, and exact
installed integration version were not provided.

The report is recorded here without changing command handling or promoting
untested features. The current integration still exposes
`model_validation: experimental` for D110 Plus; `tested` identifies the model
validated directly by the maintainer. These labels are not vendor certification.

## Other models

Other account-returned DESLOC models are added for community testing. Discovery
alone does not establish working state reporting, commands, or PIN management.
Locks using TTLock or Tuya accounts are outside this integration's scope.

## Share a result

Use the [model compatibility issue form](https://github.com/ha-homelab/ha-desloc/issues/new?template=model-compatibility.yml).
Include the model, firmware, integration/HA/app versions, and which features
you actually tested: discovery, reported state, battery, Wi-Fi, lock, unlock,
and PIN creation/keypad use. Mark the rest as untested.

For failures, describe the error and steps to reproduce it. Do not post PINs,
tokens, account credentials, private device identifiers, or raw captures. We
will use reports to improve compatibility and document or exclude models that
cannot be supported through this API.
