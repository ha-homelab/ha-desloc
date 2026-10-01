# Changelog

## 0.2.0 — 2026-10-01

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
