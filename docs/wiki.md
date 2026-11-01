# Maintaining the project wiki

The public guide is at <https://ha-homelab.github.io/ha-desloc/>. Its source is
`wiki/`; generated pages and shared assets are in `site/`. It covers both the
integration and companion card in 24 languages.
Existing Markdown documentation remains available at its original URLs.

## Preview and validate

```sh
python3 scripts/build_wiki.py
python3 scripts/test_wiki_locales.py
python3 scripts/build_wiki.py --check
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

## Translations

`wiki/languages.json` uses the same 24-language catalog as the integration, card,
HA OTTPlay and ZAC93 projects: `en`, `ar`, `bn`, `cs`, `de`, `es`, `fa`, `fr`,
`he`, `hi`, `id`, `it`, `ja`, `ko`, `nl`, `pl`, `pt`, `ru`, `th`, `tr`, `uk`,
`vi`, `zh-Hans`, and `zh-Hant`. The shared list is maintained in the
[organization language catalog](https://github.com/ha-homelab/.github/blob/main/languages.json).

English remains at the root URL. Every other complete guide is at `/<language>/`
under the project base, for example `/ha-desloc/fr/`. The native-name language
picker is available without JavaScript. With JavaScript, switching languages
preserves the current section. Arabic, Hebrew and Persian use RTL prose; code
and technical identifiers keep their LTR order. Search, diagram labels,
metadata, accessibility text, theme controls and clipboard feedback are included.
There is no runtime translation service, automatic language redirect or remote
font dependency. Linked technical references, screenshots and videos retain
their original English content; the reference section states that boundary.

To update content:

1. Edit canonical messages in `wiki/locales/en.json`; keep existing keys stable.
   `mNNN` messages contain complete HTML fragments and `aNNN` are plain text
   attributes. Edit `wiki/template.html` only for shared structure. Do not edit
   generated `site/**/index.html` files directly.
2. Translate every changed message in each locale JSON. Preserve all tags,
   attributes, links, `<code>` contents, model names, versions, feature caveats
   and named placeholders such as `{count}`. Translate whole sentences rather
   than concatenating fragments. Keep HACS product search names recognizable.
3. After reviewing the complete locale against English, set its `source_sha256`
   to the SHA-256 of `wiki/locales/en.json`. The hash is a review receipt, not a
   translation mechanism; never refresh it without checking the changes.
4. Run the commands above and commit the source catalogs and regenerated pages
   together. For an intermediate single-language preview, use
   `python3 scripts/build_wiki.py --language fr`. CI always checks all languages.
5. Check long labels and mobile layouts, at least one RTL locale, language links
   with an active section, localized search and the no-JavaScript page.

The generator rejects missing/empty messages, duplicate keys, changed HTML,
links or code examples, missing placeholders, stale source hashes and copied
long English sentences. CI also detects stale generated pages. These checks
do not certify idiomatic language: native-speaker corrections are welcome.

## Design and content contracts

- HTML, CSS and vanilla JavaScript only. No runtime package dependencies,
  external fonts, analytics or remote embedded assets.
- `style.css` owns theme tokens, content and layout. `elevate.css` adds optional
  decoration. Both themes need readable text and visible focus.
- Keep existing section IDs stable. There is one anchor offset, implemented
  with section scroll margins; navigation follows a reading line below the header.
- Keep core instructions in HTML. Search indexes that HTML in the browser and
  never removes sections. Native disclosure widgets work without JavaScript.
- Bump the asset query versions in `wiki/template.html` after changing CSS or
  JavaScript, then regenerate all pages.
- Match the head theme initializer to the CSS palette and `app.js` meta colors.
- Distinguish maintainer validation, community reports and unverified models.
  Document release baselines with dates; never present historical counters or
  screenshots as live status.
- Keep protocol details in the maintained reference documents and link to them.
  Never include captured traffic, credentials or real device identifiers.

## Publication

The existing required PR test workflow runs the generator and wiki checker. It validates local
links and anchors, basic HTML semantics, local-only assets, file budgets and
publication boundaries. It includes regression tests for the checker itself.

The `Publish wiki` workflow runs on relevant changes to `main` and can be
dispatched manually from `main`. It revalidates and uploads **only `site/`**,
then deploys to the `github-pages` environment using GitHub Pages Actions.
Configure repository Pages with **GitHub Actions** as the publishing source.
PRs cannot deploy. The integration release pipeline remains separate.

After publication, verify the Pages deployment revision and the live page plus
its versioned assets. A passing upload alone is not proof of deployment.
