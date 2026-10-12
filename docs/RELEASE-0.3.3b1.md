# DESLOC integration 0.3.3b1

## Changes

This opt-in beta qualifies the current source with the updated CI and locked development dependencies. The lock-control behavior is unchanged from the previous stable release. The package reports a distinct prerelease version so beta and stable installations remain identifiable.

## Upgrade

Keep the current stable release for normal use. To test this beta, explicitly enable prereleases in HACS and select `0.3.3b1`. For manual installation, open the [versioned beta release](https://github.com/ha-homelab/ha-desloc/releases/tag/v0.3.3b1), download `ha-desloc.zip` and `SHA256SUMS`, verify the checksum, and extract `custom_components/desloc` into the Home Assistant configuration directory. The README links to stable releases, so select this beta page explicitly. Preserve the existing configuration and reload Home Assistant. Downgrading uses the previous stable artifact. No new live-lock acceptance is claimed by this packaging release.

## Security

Keep account sessions, access tokens and private device identifiers out of reports and committed configuration. Existing confirmation, authentication and diagnostic redaction behavior is retained. Verify the release checksums before manual installation.
