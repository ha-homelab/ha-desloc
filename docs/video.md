# Interface overview video

[Watch or download the 30-second MP4](media/desloc-overview.mp4).

The README embeds the [looping GIF version](media/desloc-overview.gif) directly.
It preserves all six scenes and their five-second reading time, with no audio.
For a non-animated reference, use the [screenshot walkthrough](screenshots.md)
or the transcript below.

The silent video presents real, cropped Home Assistant screenshots with English
captions. It is an edited screenshot walkthrough, not a continuous recording or
a demonstration of physical lock movement. The empty PIN form is not submitted.

Captured October 1, 2026 with **Home Assistant 2026.9.1**, **DESLOC integration
0.3.0**, and **DESLOC Lock Card 0.1.1**. The source screenshots are in the
[integration gallery](screenshots.md) and
[card gallery](https://github.com/ha-homelab/ha-desloc-card/blob/main/docs/screenshots.md).

## Transcript

1. **00:00–00:05 — Set up DESLOC.** Choose email sign-in or reuse an existing app
   session. A new sign-in can invalidate the phone app session.
2. **00:05–00:10 — Every discovered lock, automatically.** C100 Plus is tested;
   other models are experimental. Discovery runs during setup or reconfiguration.
3. **00:10–00:15 — See reported state at a glance.** Bolt state, battery, and
   Wi-Fi appear in one dashboard card. Cloud reports may be cached; this is not
   a door-open sensor.
4. **00:15–00:20 — Configure the card visually.** Choose a lock, display name,
   and optional sensors. The card uses Home Assistant entities, not DESLOC
   credentials.
5. **00:20–00:25 — Add a permanent PIN user.** Open **Settings → Devices &
   services → DESLOC → Configure**. Submitting creates permanent access; the
   form shown is empty.
6. **00:25–00:30 — DESLOC for Home Assistant.** An unofficial cloud integration
   and optional dashboard card. Install both as HACS custom repositories; they
   are not yet included in the default HACS catalog. C100 Plus is physically
   tested; other models remain experimental.

The closing scene links to the
[integration](https://github.com/ha-homelab/ha-desloc) and
[card](https://github.com/ha-homelab/ha-desloc-card).

## Media details

- H.264 MP4, 1280 × 720, 30 frames per second, exactly 30 seconds, no audio track.
- GIF preview: 1280 × 720, six frames held for five seconds each, a 30-second
  infinite loop, approximately 566 KiB. It uses an optimized 256-color palette.
- Original UI crops retain their contents; titles and captions sit outside them.
- Composed locally with FFmpeg and the
  [video-use](https://github.com/browser-use/video-use/tree/9575612f066aa517354790a645fd90f9f95a743b)
  workflow. Each scene is rendered separately and joined without re-encoding.
- Reviewed the start, end, every cut boundary, and representative middle frames.
  The screenshots and video contain no account credentials, PINs, server
  addresses, or private device identifiers.

For installation and current limitations, use the [README](../README.md).
Version numbers and HACS status in the video describe the capture date.
