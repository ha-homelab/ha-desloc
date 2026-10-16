# Changelog

## [0.4.0] - Unreleased

### Added

- Bundle 24 complete Home Assistant language packs for setup, authentication,
  permanent PIN-user forms, sensor names, and translated command errors.
- Verify every pack through the native Home Assistant translation loader in CI,
  with key/placeholder parity and entity identity/custom-name preservation tests.
- Document language selection, privacy, fallback behavior, and translation contributions.

### Changed

- Distinguish maintainer-tested C100 Plus and community-confirmed D110 Plus in
  every translated setup description; other models remain experimental.
- Attach Home Assistant translation metadata to command and authentication errors
  while preserving their original English diagnostic messages.

### Upgrade

This minor release candidate includes the previous 0.3.5 beta work and adds
localization. Use the existing installation procedure. Existing configuration,
entity IDs, unique IDs, automations, and user-assigned names are preserved.
Sensor default names follow Home Assistant's system language. The PIN form,
command timing, uncertain-result handling, and session lifecycle are unchanged.
The 0.3.5 beta cycle was not published as a stable release.

### Security

Translations are bundled locally and do not send text, credentials, or PINs to
a translation service. Translated messages preserve the existing requirements
to check uncertain command results and to reauthenticate revoked sessions.
This release does not claim new physical-device testing or a security fix.

## [0.3.5] - Unreleased

### Changed

- Update the CodeRabbit reusable workflow revisions while preserving the validated release fuzz configuration.
- Record the additional D110 Plus community report that PIN functionality works, with the reported scope distinguished from maintainer validation.
- Make release packaging guidance follow the committed base version instead of a stale release number.

### Upgrade

This preview prepares the next beta for opt-in testing. Follow the existing installation procedure and retain the previous accepted package for rollback. Install the published `ha-desloc.zip` to test the exact beta metadata; HACS source downloads retain the committed numeric base version. Application behavior and configuration are unchanged.

### Security

These changes update workflow references and documentation. They do not claim a new security fix or additional physical-device validation. Existing quality, security and package checks remain required before publication.

## [0.3.4] - 2026-10-14

### Changed

- Validate each public release candidate with bounded, network-isolated fuzz campaigns against its exact source revision.
- Require positive engine execution counts, instrumented production code and validated seed corpora; retain source-bound reports and diagnostic evidence.
- Run deterministic seed and configuration checks in ordinary CI without starting mutation campaigns on betas.

### Upgrade

Use the existing installation procedure, preserve local configuration and keep the previous accepted package for rollback. This maintenance release updates release validation and does not change the application configuration format. Deployment and applicable device or integration acceptance remain separate from publication.

### Security

RC publication rejects absent or invalid source-bound fuzz reports. The fuzz runner bounds corpus paths, file types and size. No application vulnerability or new target-device acceptance is claimed by these tooling changes.

## [0.3.3]

### Changed

- Document the vendor login digest's offline password-guessing risk, the limits
  of its fixed AES wrapper, and credential/capture handling mitigations. This
  clarifies the existing protocol; it does not change or fix vendor authentication.
- Lock Python dependencies and verify downloaded archive SHA-256 hashes in CI and
  documented installation commands.
- Update the isolated Home Assistant test runtime from 2026.9.1 to 2026.10.0,
  which requires PyJWT 2.15.1 instead of vulnerable PyJWT 2.13.0. See
  [GHSA-ffc3-869f-jxw9](https://github.com/advisories/GHSA-ffc3-869f-jxw9)
  and the related upstream advisories. This changes the synthetic test environment;
  it does not install or upgrade Home Assistant on a user's device. Maintain an
  independently updated, supported Home Assistant installation.

### Added

- Frozen beta/nightly/RC release plans and checksum-bound package receipts.
- Verification of the existing manual-install ZIP layout and embedded candidate version.

### Upgrade

HACS installation remains unchanged. Test exact candidate builds by installing `ha-desloc.zip` manually with its existing `custom_components/desloc` directory. Back up the existing integration directory and Home Assistant configuration, replace the integration files and restart Home Assistant. Preserve the prior accepted ZIP for rollback. The committed manifest uses the numeric base; install the published release asset to obtain its exact candidate metadata.

### Security

Existing Home Assistant tests, HACS/Hassfest checks and code/dependency checks remain required. Release receipts bind the package identity to the source and workflow. Automated validation does not establish cloud account permissions, physical lock operation or safe installation-specific automation behavior.

## 0.3.2 — 2026-10-06

- Display the stable integration as **DESLOC** in Home Assistant, HACS, and the
  English/Russian setup titles, removing the old project-wide experimental label.
- Align the current installation and publishing documentation with that name.
- Keep model-specific compatibility labels and the documented cloud/API limits.

This is a naming and documentation update. Authentication, polling, lock/PIN
commands, entity IDs, and model compatibility are unchanged.

## 0.3.1 — 2026-10-05

- Promote the installed 0.3.1rc1 candidate to stable with unchanged runtime code.
- Clarify PIN preflight failures and recovery when an existing user has no
  confirmed PIN record; never retry or remove an access record automatically.
- Share account polling between locks while requiring fresh command confirmation.
- Back off after HTTP 429 without replaying writes, and sanitize protocol errors.
- Refresh device registry metadata while preserving device identity and custom names.

Validation: 152 automated integration tests. The release candidate was installed
on Home Assistant 2026.9.1, loaded successfully, and completed cloud polling.
Promotion does not claim a new physical lock/unlock or PIN test and does not
change model compatibility.

## 0.3.1rc1 — 2026-10-04

Promote 0.3.1b1 to a release candidate with identical runtime code. The beta
passed 152 synthetic tests; this candidate is intended for Home Assistant
deployment validation. No runtime behavior or model-compatibility changes are
introduced by this promotion.

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
