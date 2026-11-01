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

On the same date, **razorbross15-sudo** added a
[second success report](https://github.com/home-assistant/feature-requests/discussions/2138#discussioncomment-18706123),
explicitly stating that D110 Plus works including PIN functionality.

These are positive owner reports for D110 Plus, including PIN functionality.
They do not describe the individual HA user-creation or keypad test steps, both
lock command directions, or each sensor. Firmware, region, Home Assistant
version, and exact installed integration version were not provided.

The reports are recorded here without changing command handling or extending
maintainer validation. The current integration still exposes
`model_validation: experimental` for D110 Plus; `tested` identifies the model
validated directly by the maintainer. These labels are not vendor certification.

## K120 — community-reported working

On **October 19, 2026**, **Chief915E** [reported that the integration works with
their K120 and exposes the entities used by the DESLOC Lock Card](https://community.home-assistant.io/t/desloc-smart-locks-custom-integration-and-dashboard-card-model-compatibility-reports/1027056/2).

The owner shared the lock from their primary DESLOC account to a second account
and signed into the HA integration with the second account. They reported that
both the phone app and HA remained usable without importing the primary
account's session. This is one owner's account-sharing report, not a verified
replacement for the [captured-session flow](authentication.md) in every region
or account configuration. Shared-account permissions may differ.

That October 19 report does not document separate lock/unlock or PIN-creation/
keypad tests, firmware, or exact HA/integration versions.

On **October 31, 2026**, **ESchmitt0602** supplied a
[more detailed K120 report](https://github.com/ha-homelab/ha-desloc/issues/103):

- Discovery in HA, both lock and unlock, accurate reported lock state and battery
  percentage worked on **HA Core 2026.10.4**.
- K120 firmware: **`AAN_L003_A01_29260129`**; Wi-Fi firmware: **`27500`**.
- The owner shared their K120 and K140 Plus to a second, regular DESLOC account
  used by HA. Their primary account remained usable in the phone app at the same
  time without conflicts.
- **PIN creation was not tested** because the second account lacked elevated
  privileges. Wi-Fi signal reporting was not separately confirmed.

The installation used HA OS 18.4, Supervisor 2026.10.5 and Frontend 20260930.5.
The exact integration version was not specified; the DESLOC app was described
by a date rather than an unambiguous version number. These are owner reports,
not maintainer validation. K120 retains `model_validation: experimental`.

## K140 Plus — community-reported working

On **October 31, 2026**, **ESchmitt0602** filed a
[K140 Plus report](https://github.com/ha-homelab/ha-desloc/issues/104). It records
the **same household and test session** as the K120 report above, separately
for the second model; it is not an independent second-owner confirmation.

Discovery, lock, unlock, accurate reported lock state and battery percentage
worked on **HA Core 2026.10.4** with firmware **`AAN_Z001_A03_29260907`** and
Wi-Fi firmware **`27500`**. Both locks used the second account described above.
**PIN creation was not tested**, and Wi-Fi signal reporting was not separately
confirmed. The exact integration version was not supplied.

K140 Plus retains `model_validation: experimental` pending physical maintainer
validation. Shared-account permissions and session behavior can vary; these
reports do not guarantee the same result for every account or region.

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
