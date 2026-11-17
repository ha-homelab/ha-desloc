# DESLOC for Home Assistant — documentation index

This index covers the unofficial DESLOC integration for cloud-controlled locks:
how it talks to the vendor service, how to capture a session and create PIN users,
and the release, security and evidence records around it. The illustrated public
guide is the [project wiki](https://ha-homelab.github.io/ha-desloc/); see
[maintaining the project wiki](wiki.md) for how that site is built.

## Get started

- [How DESLOC reaches Home Assistant](how-it-works.md): the path from app protocol
  to lock entities, with the [command lifecycle diagram](diagrams/command-lifecycle.svg).
- [Capture your DESLOC session](authentication.md): importing the app session with
  your own account and device.
- [Model compatibility](compatibility.md): firmware and per-model scope.
- [Screenshot walkthrough](screenshots.md) and the
  [30-second interface overview video](video.md).

## Configure

- [Create a permanent PIN user](pin-users.md).
- [DESLOC icons in Home Assistant and HACS](branding.md).
- [Languages and translation contributions](i18n.md).

## Reference

- [Observed protocol](protocol.md): the cloud protocol as observed on C100 Plus
  and DESLOC iOS 1.2.1, with synthetic IDs.
- [Diagram sources](diagrams/README.md): editable SVG assets.
- [Security design and verification](security-design.md), including the
  [supported HTTPS runtime profile](security-design.md#supported-https-runtime-profile).

## Troubleshoot

- [Troubleshooting](troubleshooting.md): branding, authentication and update-entity
  symptoms.

## Development

- [Development](development.md): module layout in `custom_components/desloc/`.
- [CI dependency updates](dependency-updates.md).

## Evidence and release

- [Release results: integration v0.4.0](release-results.md) and the
  [release-results diagram](diagrams/release-results.svg).
- [DESLOC integration 0.3.3b1](RELEASE-0.3.3b1.md): the opt-in beta record.
- [Integration release packaging](release-packaging.md).
- [HACS and Home Assistant Core submission](publishing.md).
- [OpenSSF Passing evidence](openssf-evidence.md) and
  [release-candidate fuzz testing](fuzzing.md).

Shared repository policy (`release-workflow.md`, `quality.md`,
`openssf-evidence.md`, `runner-preflight.md`, `release-read-safety.md`,
`VERSIONING.md`) comes from the shared release toolkit and is summarized rather
than repeated here.

Every recorded result covers the exact version and lock model it names. Do not
generalize a beta or a single-device test to another firmware build.
