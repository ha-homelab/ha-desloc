# Maintenance roadmap

This roadmap covers October 2026 through October 2027. It describes priorities,
not delivery dates or unverified device support.

- Preserve fixed-origin verified HTTPS, sanitized errors, rate limiting and
  explicit handling of uncertain lock-command results. Never automatically
  retry physical lock or unlock commands.
- Keep Home Assistant compatibility, locked test dependencies, translation
  parity and protocol regression tests current.
- Extend exact certificate-key boundary tests across the actual supported Home
  Assistant transport and review release-tool dependencies independently.
- Track the vendor's fast password transform and fixed-key wrapper openly.
  Adopt stronger authentication only when a compatible documented or observed
  vendor protocol exists; local wire changes alone cannot repair the service.
- Improve whole-source coverage and security-analysis evidence, while keeping
  synthetic tests separate from explicit physical-device acceptance.
- Establish an actual backup maintainer and access-recovery procedure before
  claiming continuity. No such arrangement exists today.

New lock models require sanitized protocol evidence and physical-device
verification. Offline lock operation, undocumented endpoint guesses and a
guarantee of vendor-cloud availability are outside the current scope.
