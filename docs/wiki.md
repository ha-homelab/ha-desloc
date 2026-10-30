# Maintaining the project wiki

The public guide is at <https://ha-homelab.github.io/ha-desloc/>. Its source is
`site/` in this repository; it covers both the integration and companion card.
Existing Markdown documentation remains available at its original URLs.

## Preview and validate

```sh
python3 scripts/check_wiki.py --self-test
python3 scripts/check_wiki.py
node --check site/assets/app.js
python3 -m http.server 4173 --bind 127.0.0.1 --directory site
```

Open <http://127.0.0.1:4173>. Check desktop and narrow mobile layouts in light and
dark themes. Check the complete system → light → dark → system theme cycle,
navigation, search, copy controls, expanded troubleshooting answers, reduced
motion, and the page with JavaScript disabled. Content must remain readable
without scripts. The hero and compact card are explicitly illustrative;
neither connects to a device.

## Design and content contracts

- HTML, CSS and vanilla JavaScript only. No runtime package dependencies,
  external fonts, analytics or remote embedded assets.
- `style.css` owns theme tokens, content and layout. `elevate.css` adds optional
  decoration. Both themes need readable text and visible focus.
- Keep existing section IDs stable. There is one anchor offset, implemented
  with section scroll margins; navigation follows a reading line below the header.
- Keep core instructions in HTML. Search indexes that HTML in the browser and
  never removes sections. Native disclosure widgets work without JavaScript.
- Bump the asset query versions in `index.html` after changing CSS or JavaScript.
- Match the head theme initializer to the CSS palette and `app.js` meta colors.
- Distinguish maintainer validation, community reports and unverified models.
  Document release baselines with dates; never present historical counters or
  screenshots as live status.
- Keep protocol details in the maintained reference documents and link to them.
  Never include captured traffic, credentials or real device identifiers.

## Publication

The existing required PR test workflow runs the wiki checker. It validates local
links and anchors, basic HTML semantics, local-only assets, file budgets and
publication boundaries. It includes regression tests for the checker itself.

The `Publish wiki` workflow runs on relevant changes to `main` and can be
dispatched manually from `main`. It revalidates and uploads **only `site/`**,
then deploys to the `github-pages` environment using GitHub Pages Actions.
Configure repository Pages with **GitHub Actions** as the publishing source.
PRs cannot deploy. The integration release pipeline remains separate.

After publication, verify the Pages deployment revision and the live page plus
its versioned assets. A passing upload alone is not proof of deployment.
