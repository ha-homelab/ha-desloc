# Changelog

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
