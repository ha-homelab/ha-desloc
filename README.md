# DESLOC for Home Assistant

[![Tests](https://github.com/ha-homelab/ha-desloc/actions/workflows/ci.yml/badge.svg)](https://github.com/ha-homelab/ha-desloc/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An **unofficial, experimental cloud integration** for the **DESLOC C100 Plus**
using the DESLOC mobile app. It provides lock/unlock controls, reported bolt
state, battery percentage, and Wi-Fi signal in Home Assistant.

This project is independent of DESLOC, Home Assistant, and HACS. It does not
provide local/offline or Bluetooth control. D110 Plus, B200, TTLock, and other
models have **not** been verified; device selection currently accepts C100 Plus.

## Status and limitations

The protocol and both command directions were captured from a real C100 Plus
using the iOS app with Bluetooth disabled. Device reads were reproduced with
[littledivy/mimic](https://github.com/littledivy/mimic) and the asynchronous client.
See [CHANGELOG.md](CHANGELOG.md) for physical validation from Home Assistant.
Synthetic tests do not establish physical operation.

**Authentication requires an app-session capture; email/password setup is not
implemented.** Independent login, actual session lifetime, and automatic renewal
remain unverified. Logging out of the app was observed to revoke the shared
session. After expiry or revocation, Home Assistant requests a new session from
a fresh capture. Other limitations:

- The observed device-list request covers up to 20 entries; pagination is untested.
- No access-code management, activity history, jam detection, or door-open sensor.
- Cloud telemetry can be cached. A cloud response does not prove the lock is
  currently reachable. The undocumented online-status enum is not interpreted.
- Undocumented endpoints may change; other regions and models need verification.

## Architecture

```mermaid
flowchart LR
    User[Home Assistant user] --> Entities[Lock and sensor entities]
    Entities --> Coordinator[Shared coordinator]
    Coordinator -->|HTTPS status and commands| Cloud[DESLOC cloud]
    Cloud <-->|Vendor device connection| Lock[C100 Plus]
    App[DESLOC mobile app] -.->|Initial session capture| Setup[Configuration flow]
    Setup --> Coordinator
```

Normal polling runs once per minute. Each physical command is sent **once**, with
result polling and a requirement for a newer matching state report. Timeouts do
not cause automatic command retries. See [protocol details](docs/protocol.md).

## Requirements

- Home Assistant **2026.9.1 or newer**; 2026.9.1 is the tested baseline.
- C100 Plus already paired with DESLOC, with working cloud control.
- HTTPS access from Home Assistant to `appadmin.desloc.com`.
- A captured session for your own DESLOC account.

## Installation

### HACS custom repository

This is **not currently listed in the default HACS catalog**.

1. In HACS, open the menu → **Custom repositories**.
2. Add `https://github.com/ha-homelab/ha-desloc`, type **Integration**.
3. Download **DESLOC (experimental)** and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → DESLOC**.

### Manual installation

Download a [release](https://github.com/ha-homelab/ha-desloc/releases) or clone this
repository. Copy only `custom_components/desloc/` into your Home Assistant
configuration's `custom_components/` directory. Restart and add the integration.
Capture files, certificates, and development tools are not runtime dependencies.

## Dashboard card

The optional [DESLOC Lock Card](https://github.com/ha-homelab/ha-desloc-card) is
distributed separately as a HACS **Dashboard** repository. It provides state,
battery/RSSI, and lock controls with mandatory unlock confirmation.

## Configuration

Use [the capture guide](docs/authentication.md) to create the private
`.private/ha-session.json` file. Enter its four fields in the setup form:

- **App authorization token**: captured `authorization` header, unchanged.
- **App device ID**: captured `deviceid` identifying the phone's app installation.
- **App version**: captured `appversion`; tested value `1.2.1`.
- **System type**: captured `systype`; tested iOS value `1`.

Do not add a `Bearer` prefix, use the lock's ID as the app device ID, or substitute
the separate IoT access token. Select the lock after validation. Each config
entry represents one supported lock. Reauthentication retains the same identity.

## Entities

- **Lock**: lock/unlock, reported state, and transitions during commands.
- **Battery**: reported percentage.
- **Wi-Fi signal**: RSSI in dBm, a diagnostic entity.
- **Door state code** and **Online status code**: raw diagnostics, disabled by default.

Observed bolt codes are `1` = unlocked and `2` = locked. Other codes are unknown.
Following an uncertain command, old telemetry is not treated as confirmation.
Check the physical lock before deciding whether to issue another command.
Loss of cloud access or removal of the device makes entities unavailable.

## Documentation and contributions

- [Session capture and cleanup](docs/authentication.md)
- [Protocol, command sequence, and state machine](docs/protocol.md)
- [Troubleshooting](docs/troubleshooting.md)
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
