# Changelog

## 0.3.1b1 — 2026-10-04

- Distinguish busy, unavailable, and failed preflight PIN requests from writes
  whose completion is uncertain.
- Explain when an existing user has no confirmed PIN record. Existing-user
  checks never attach a PIN, retry creation, or delete a user automatically.
- Share complete device-list snapshots and in-flight requests between locks
  using the same saved session. Command confirmation requests fresh data.
- Pause requests after HTTP 429 without replaying lock or PIN writes, and
  classify non-JSON responses as protocol errors.
- Refresh device names, models, and firmware in the HA device registry while
  preserving identifiers and user-assigned names.

This is a prerelease for opt-in testing. These changes are validated with
synthetic tests; they do not add new physical-device compatibility claims.

## 0.3.0 — 2026-10-01

- Add all account-returned locks automatically during setup/reconfiguration,
  keeping a separate entry per lock and preserving existing entities.
- Admit other model names for community testing, label them experimental, and
  provide allowlisted compatibility diagnostics without credentials or identity.
- Add an administrator settings form to create a regular permanent PIN user.
- Validate name/PIN before writes, reject duplicate names, and never retain PINs
  in configuration or entity state.
- Create the user and encrypted PIN once, then wait for command completion and
  verify the resulting user/PIN record. Report uncertain partial completion
  without automatic retries or deletion.
- Serialize access changes with lock/unlock commands for the same lock.

Validation: 112 tests pass on Linux/Home Assistant 2026.9.1, with HACS and
Hassfest validation passing. The full exchange was captured during real app
creation with Bluetooth disabled. The user then created a new user through the
HA Configure form and confirmed that its PIN works at the physical keypad.
Mixed-model discovery, peer reauthentication, duplicate prevention, pagination,
and diagnostic privacy are covered by synthetic tests. The pagination cursor
boundary was also probed read-only on the real account. Physical validation
by the maintainer remains limited to C100 Plus.

Community follow-up, October 1, 2026: a D110 Plus owner
[reported successful use](https://github.com/home-assistant/feature-requests/discussions/2138#discussioncomment-18702050).
The report did not provide individual feature results or version details; see
[model compatibility](docs/compatibility.md). Runtime labels and behavior are
unchanged by this documentation update.

## 0.2.1 — 2026-10-01

- Fix repeated mobile-app sign-outs caused by automatic HA re-login after 401.
- Save the authenticated session token during setup and reuse it on reload.
  New entries no longer retain the password-equivalent digest.
- Stop on authentication rejection and request interactive reauthentication.
  Neither the rejected request nor login is retried in the background.
- Require reauthentication for legacy 0.2.0 digest entries, without logging in
  during upgrade. Importing the app session preserves the existing lock/entities.
- Explain the observed same-account session conflict in setup and documentation.

Validation: 69 tests pass on Linux/Home Assistant 2026.9.1, including token reuse
on reload, no login after session rejection, and safe handling of old entries.
The user confirmed the phone stopped signing out with the competing HA login
disabled. HA was then restored by importing the current phone session.

## 0.2.0 — 2026-10-01

Superseded by 0.2.1: the renewal behavior below was found to conflict with the
mobile app's session. Update before using the same account in both clients.

- Add email/password setup and email verification for a new HA installation.
- Store a password-equivalent digest and stable installation ID; never retain
  the plaintext password or verification code.
- Renew rejected sessions for reads, serialize concurrent logins, and never
  replay a physical command after authentication failure.
- Add reconfiguration from captured sessions while preserving the selected
  lock and entity IDs; keep captured-session setup as a fallback.
- Report CAPTCHA, account, verification, and clock errors without server bodies.

Validation: 66 synthetic tests pass on Linux/Home Assistant 2026.9.1, including
the real HA migration/reload path and preservation of entity IDs. The password
transformation matches an observed iOS login. A real account completed password
and email-code setup in HA; reloading the integration logged in again without
another code. Natural token expiry remains unobserved.
A second HA service cycle using account authentication received fresh `unlocked`
and then `locked` reports. Human confirmation of that cycle is pending.

## 0.1.0 — 2026-10-01

- Initial experimental C100 Plus cloud integration.
- Lock/unlock, command-result polling, and fresh-state confirmation.
- Battery, RSSI, and optional raw diagnostics.
- UI setup and same-device session reauthentication.
- Local capture tools using littledivy/mimic.
- English documentation and Mermaid diagrams.

Validation: 48 synthetic tests pass on Linux/Home Assistant 2026.9.1; HACS and
Hassfest pass. Installed through a live HA configuration flow. A real HA service
cycle completed both directions with fresh cloud states (`unlocked`, then
`locked`). Human confirmation of that HA-initiated physical cycle is pending.
Earlier app-initiated cycles were physically confirmed.

The optional companion dashboard card is available separately at
[ha-homelab/ha-desloc-card](https://github.com/ha-homelab/ha-desloc-card).
