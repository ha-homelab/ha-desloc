# DESLOC for Home Assistant

[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/15591/badge)](https://www.bestpractices.dev/projects/15591)
[![Fuzzing: RC only](https://img.shields.io/badge/Fuzzing-RC%20only-blue)](docs/fuzzing.md)

[![Tests](https://github.com/ha-homelab/ha-desloc/actions/workflows/ci.yml/badge.svg)](https://github.com/ha-homelab/ha-desloc/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An **unofficial cloud integration** for locks linked to the
**DESLOC mobile app**. It automatically adds every lock returned by the account
during setup. **C100 Plus is maintainer-tested; D110 Plus and K120 have community
success reports.** It provides lock/unlock controls, reported bolt state, battery
percentage, and Wi-Fi signal in Home Assistant.

This project is independent of DESLOC, Home Assistant, and HACS. It does not
provide local/offline or Bluetooth control. A D110 Plus owner
[reported that it works perfectly](https://github.com/home-assistant/feature-requests/discussions/2138#discussioncomment-18702050).
A second owner [reported that PIN functionality also works](https://github.com/home-assistant/feature-requests/discussions/2138#discussioncomment-18706123).
A K120 owner also [reported working integration and available card entities](https://community.home-assistant.io/t/desloc-smart-locks-custom-integration-and-dashboard-card-model-compatibility-reports/1027056/2).
These reports do not list complete test steps or software/firmware versions;
see [model compatibility](docs/compatibility.md) for the evidence and scope.
Models without maintainer validation still carry an **experimental** runtime
label. Discovery alone does not establish compatibility. TTLock/Tuya accounts
are not supported by this integration.

[![DESLOC integration overview in perspective](docs/images/desloc-hero.png)](docs/images/integration-overview.jpg)

Historical Home Assistant screenshot with integration **0.3.0**, presented in perspective.
Click for the unchanged readable original. [Animated walkthrough](docs/media/desloc-overview.gif).

The silent 30-second animation loops through real Home Assistant screenshots,
including the optional [DESLOC Lock Card](https://github.com/ha-homelab/ha-desloc-card).
See the [screenshot walkthrough](docs/screenshots.md) for authentication,
discovered devices, and the PIN user form.

[Watch the 30-second interface overview](docs/media/desloc-overview.mp4)
(silent, English captions) · [Video transcript](docs/video.md)

## Languages

The integration includes **24 complete language packs** for setup, authentication,
PIN-user forms, sensor names, and command errors. It uses Home Assistant’s native
language selection and English fallback; no translation service is contacted.
Existing entity IDs and custom names are preserved. Documentation and demo media
remain in English. See [languages and translation contributions](docs/i18n.md).

## Status and limitations

The protocol and both command directions were captured from a real C100 Plus
using the iOS app with Bluetooth disabled. Device reads were reproduced with
[littledivy/mimic](https://github.com/littledivy/mimic) and the asynchronous client.
See [CHANGELOG.md](CHANGELOG.md) for physical validation from Home Assistant.
Synthetic tests do not establish physical operation.

**Update 0.2.0 installations to 0.2.1.** Automatic login in 0.2.0 was observed to
conflict with the phone app and repeatedly sign it out. Version 0.2.1 saves and
reuses the authenticated session token and stops on rejection; it never signs
in automatically after a rejected request. A distinct installation ID did not
prevent the observed session conflict.

Email/password login and email-code verification work, but a new login can
invalidate the phone app's session. To use the same account in HA and the app,
import the current app session with the [capture guide](docs/authentication.md).
Signing out or another login can revoke that token. Natural expiry is unmeasured.
Other limitations:

- Device discovery reads 20-entry cursor pages from the app's default group
  (`groupId: 0`). The cursor boundary was checked on a real one-lock account;
  multiple populated pages and accounts spanning multiple groups/homes still
  need community verification. A repeated cursor or 100-page limit is reported
  as an error rather than silently accepting a truncated list.
- Version 0.3.0 adds regular permanent PIN users. Creation through the HA form
  and use at the physical keypad were confirmed on C100 Plus; modification,
  deletion, and schedules are unsupported.
- No activity history, jam detection, or door-open sensor.
- Cloud telemetry can be cached. A cloud response does not prove the lock is
  currently reachable. The undocumented online-status enum is not interpreted.
- Undocumented endpoints may change; other regions and models need verification.

## Architecture

Setup authenticates with DESLOC and adds every returned lock, each with its own
entry and coordinator. Coordinators using the same account session share device
list reads. Normal polling runs once per minute per configured lock.

[![Architecture: HA entities, shared account reads, DESLOC cloud, and the physical lock](docs/diagrams/architecture.svg)](docs/diagrams/architecture.svg)

Each physical command is sent **once**, with result polling and a requirement for
a newer matching state report. Timeouts do not cause automatic command retries.
The [visual process guide](docs/how-it-works.md) explains the path from app
captures to the integration, discovery, commands, and PIN creation. See also the
[command lifecycle diagram](docs/diagrams/command-lifecycle.svg) and
[protocol details](docs/protocol.md).

## Release results

[![v0.4.0: 180 passing tests, 24 language packs, 9,823,752 fuzz executions, and six unchanged release files](docs/diagrams/release-results.svg)](docs/diagrams/release-results.svg)

This **15 October 2026** snapshot describes v0.4.0, not live `main` status.
Read the [results, sources, and release process](docs/release-results.md) for
the evidence behind each count. Synthetic checks do not establish physical
operation or compatibility with every discovered model.

## Requirements

- Home Assistant **2026.9.1 or newer**; 2026.9.1 is the physical validation baseline; the current synthetic CI
  runtime is 2026.10.0. Keep the installed HA instance updated independently.
- Locks already paired with the DESLOC app, with working cloud control.
  C100 Plus is maintainer-tested; D110 Plus and K120 have community success reports;
  see [model compatibility](docs/compatibility.md) for details.
- HTTPS access from Home Assistant to `appadmin.desloc.com`.
  Keep the [verified HTTPS runtime profile](docs/security-design.md#supported-https-runtime-profile);
  the documented local check reports the actual host TLS settings.
- A captured app session, or your DESLOC account email/password and verification email access.

## Installation

### HACS

DESLOC is available in the default HACS catalog. If needed,
[install and configure HACS](https://www.hacs.xyz/docs/use/download/download/)
first. HACS is optional; [manual installation](#manual-installation) works
without it.

1. Open **HACS** and search for **DESLOC**.
2. Open **DESLOC**, choose **Download**, and select the latest stable release.
   Leave beta versions disabled for normal use; do not select a beta, RC,
   nightly, or `main` build.
3. Restart Home Assistant, then open **Settings → Devices & services → Add
   integration → DESLOC**.
4. Complete [configuration](#configuration) below. Every returned lock is added
   automatically; there is no model filter or device chooser.

For updates, download the newer stable version from HACS and restart HA. The
existing entry and entity IDs are retained; you do not need to add it again.

### Manual installation

1. Open [Releases](https://github.com/ha-homelab/ha-desloc/releases/latest) and
   download the latest stable release's **ha-desloc.zip** and **SHA256SUMS**. Verify
   the checksum and extract the ZIP on your
   computer.
2. Locate your HA configuration directory, the one containing
   `configuration.yaml`. On HA OS this is `/config`; for Container installations
   it is the host directory mounted at `/config`.
3. Create `custom_components` there if needed. Copy the extracted
   `custom_components/desloc` directory into it, including all its files and
   subdirectories. The final file must be
   `/config/custom_components/desloc/manifest.json`, without an extra repository
   or `custom_components` directory in between.
4. Restart Home Assistant. Reload your browser if DESLOC does not appear in the
   integration picker.
5. Open **Settings → Devices & services → Add integration → DESLOC**, complete
   the authentication form below. All returned locks are added automatically.

To update a manual installation, back up your configuration, replace only the
`custom_components/desloc` directory with the stable release's copy, and restart
HA. Capture files, certificates, Node.js, mimic, and development tools are not
runtime dependencies. Do not copy this entire development repository into HA.

## Dashboard card

The optional [DESLOC Lock Card](https://github.com/ha-homelab/ha-desloc-card) is
distributed separately and is available in the default HACS catalog. Open
**HACS**, search for **DESLOC Lock Card**, and follow the
[card's installation instructions](https://github.com/ha-homelab/ha-desloc-card#install-through-hacs).
It provides state, battery/RSSI, and lock controls with mandatory unlock
confirmation.

## Configuration

For the same account as your phone, choose **Use a captured app session** and
follow [the capture guide](docs/authentication.md). This reuses the app's token
without signing in again. All returned locks are added automatically, with a
separate integration entry and entities for each lock.

Alternatively choose **Sign in with email and password**. Enter your DESLOC
credentials and any requested email code. The integration adds all returned locks. This new login
can invalidate another session on the same account, including the phone app.

To change the authentication method of an existing entry, open its three-dot
menu under **Settings → Devices & services → DESLOC → Reconfigure**.
The existing lock must be present in the account; existing entry/entity IDs are
retained. The same validated session is applied to the other returned locks, and
new ones are added without another login. Disabled entries remain disabled.

To discover a lock paired after initial setup, run **Reconfigure** on one DESLOC
entry using the current app session (or interactive account login). Discovery
runs during setup/reconfiguration; regular state polling does not create new
entries. Setup and discovery never send unlock, lock, or PIN commands.

HA stores the resulting session token and installation ID. New entries do not
retain the password, its digest, or the one-time code. Protect HA configuration
and backups as credentials. Rejected sessions require interactive
reauthentication; HA never retries login in the background. Existing 0.2.0
account entries must reauthenticate or import the app session during upgrade.

## Entities

- **Lock**: lock/unlock, reported state, and transitions during commands.
- **Battery**: reported percentage.
- **Wi-Fi signal**: RSSI in dBm, a diagnostic entity.
- **Door state code** and **Online status code**: raw diagnostics, disabled by default.

Observed bolt codes are `1` = unlocked and `2` = locked. Other codes are unknown.
Following an uncertain command, old telemetry is not treated as confirmation.
Check the physical lock before deciding whether to issue another command.
Loss of cloud access or removal of the device makes entities unavailable.

## PIN users

In version 0.3.0 or newer, open **Settings → Devices & services → DESLOC** and click
**Configure** (the gear icon beside the entry for the intended lock). The form is titled
**Add a permanent PIN user**. Enter a new, unique **User name**, a **New PIN** of
6–8 digits, and **Repeat PIN**, then choose **Submit**. This creates a regular
user with permanent access to the physical lock. The
integration waits for command completion and checks the installed PIN record;
it does not save the PIN in HA. The PIN is added only to that entry's lock. This
workflow is physically verified on C100 Plus. A D110 Plus owner also reported
working PIN functionality, without detailing HA creation or keypad test steps;
other models retain their experimental runtime status.
See [PIN setup and failure handling](docs/pin-users.md).

## Community model testing

**D110 Plus has community success reports, including PIN functionality.** On October 1, 2026,
[Marty-McFly73 reported successful use](https://github.com/home-assistant/feature-requests/discussions/2138#discussioncomment-18702050)
with their D110 Plus, and [razorbross15-sudo reported that it works including PIN functionality](https://github.com/home-assistant/feature-requests/discussions/2138#discussioncomment-18706123).
The second report does not describe the individual HA creation or keypad test
steps. Neither report provides software/firmware versions. The
[compatibility notes](docs/compatibility.md) distinguish these reports from the
feature-by-feature C100 Plus validation.

On October 19, 2026, a [K120 owner reported working integration and the entities
used by the card](https://community.home-assistant.io/t/desloc-smart-locks-custom-integration-and-dashboard-card-model-compatibility-reports/1027056/2).
The owner used a separate DESLOC account with a shared lock for HA while keeping
the primary account in the phone app. Individual lock/unlock and PIN tests were
not documented; this is a community report, not maintainer validation.

Every lock entity exposes `model_validation: tested` for C100 Plus and
`model_validation: experimental` for other model names. These labels record
maintainer validation, not certification by the vendor. D110 Plus and K120 retain
their experimental runtime label while community reports are recorded in the docs.
Unknown state codes remain
unknown, and a command must receive a fresh matching report to be confirmed.

For another model, report which features work: discovery, reported bolt state,
battery/RSSI, lock/unlock, and PIN creation. Include model, firmware/app versions,
HA version, and a description of any failure. Under **Settings → Devices &
services → DESLOC**, the lock entry's menu offers **Download diagnostics**. The
integration exports an allowlist of model/firmware, availability, telemetry, and
the latest command's phase/outcome and state freshness;
it excludes credentials, PINs, names, MACs, device IDs, and raw responses. Review
the downloaded file before posting it.

If a command times out while battery and Wi-Fi readings remain visible, see
[command uncertainty and diagnostic logging](docs/troubleshooting.md#command-timeout-or-unknown-state).
Cached telemetry does not confirm the physical bolt position.
An accepted command can execute after its cloud result expires. The integration
uses the remaining 45-second command window to check for a newer matching state
without resending the command. A timeout still requires checking the physical
lock before another action.

We will fix models where this API can support them and document or exclude
models whose protocol is incompatible. Please do not assume an untested model
works solely because it appears in HA.

## Documentation and contributions

- [Model compatibility and community reports](docs/compatibility.md)
- [Screenshots and setup walkthrough](docs/screenshots.md)
- [Session capture and cleanup](docs/authentication.md)
- [Protocol, command sequence, and state machine](docs/protocol.md)
- [Create a permanent PIN user](docs/pin-users.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Missing HACS update icon and optional local customization](docs/branding.md)
- [Development and tests](docs/development.md)
- [HACS and Core publication](docs/publishing.md)
- [Contributing](CONTRIBUTING.md) and [security](SECURITY.md)

Never attach raw traffic, tokens, CA keys, account data, serial numbers, or
Home Assistant config-entry contents to public issues. Use synthetic fixtures.

## Credits and license

Capture and protocol reproduction used [littledivy/mimic](https://github.com/littledivy/mimic),
pinned to `8cf998ac0b365806d8e522d34107cc504ecaa345`. The runtime uses Home
Assistant's shared `aiohttp` session; no proxy, mimic, or open app is required
after setup. Source and original project artwork are [MIT-licensed](LICENSE).
DESLOC names and trademarks belong to their respective owners.

## Project maintenance

See [contribution and test requirements](CONTRIBUTING.md), the
[security reporting policy](SECURITY.md), [security design](docs/security-design.md),
and the [OpenSSF evidence and remaining criteria](docs/openssf-evidence.md).

## Release-candidate fuzzing

The actual cloud-device response parser receives synthetic device records and checks normalized identifiers, battery/RSSI ranges and tri-state lock status. No login, PIN generation, encryption operation or lock command is called.

[RC-only fuzzing policy, local reproduction and failure handling](docs/fuzzing.md).

### Testing new release candidates

Install the published `ha-desloc.zip` manually when testing a new beta or RC.
The checked archive contains its frozen candidate metadata; GitHub's automatic
source archives and HACS's existing source-download path retain the committed
base version. HACS stable installation remains unchanged. See
[release packaging and acceptance](docs/release-packaging.md) for exact artifact
checks, version identities and rollback.

## Screenshot artwork

Regenerate the perspective cover with `bash scripts/render-docs-hero.sh`
(ImageMagick 7). It preserves the original screenshot and only adds a geometric
projection and shadow. The linked flat image remains the readable reference.
