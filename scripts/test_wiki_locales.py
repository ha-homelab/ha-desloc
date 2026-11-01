#!/usr/bin/env python3
"""Regression tests for complete, reproducible, safe wiki localization."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from build_wiki import ROOT, build, load_sources, read_json, render, validate_messages


class LocalizationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.locales = self.root / "wiki/locales"
        self.locales.mkdir(parents=True)
        self.source = {"m001": '<p>Use <code>compact: true</code> with <a href="#install">installation</a>.</p>',
                       "a001": "Matching guides: {count}."}
        self.french = {"m001": '<p>Utilisez <code>compact: true</code> avec <a href="#install">l’installation</a>.</p>',
                       "a001": "Guides correspondants : {count}."}
        self.languages = [{"code": "en", "label": "English"},
                          {"code": "fr", "label": "Français"},
                          {"code": "ar", "label": "العربية", "dir": "rtl"}]
        self.template = ('<html lang="{{language}}" dir="{{direction}}"><head>'
                         '<link rel="canonical" href="{{canonical}}">{{alternate_links}}'
                         '<link rel="stylesheet" href="{{asset_prefix}}assets/style.css">'
                         '</head><body><summary>{{current_language}}</summary>{{language_links}}'
                         '<p aria-label="{{a001}}">{{m001}}</p></body></html>')
        (self.root / "wiki/template.html").write_text(self.template)
        self.write(self.root / "wiki/languages.json", self.languages)
        self.write(self.locales / "en.json", self.source)
        self.digest = hashlib.sha256((self.locales / "en.json").read_bytes()).hexdigest()
        for code in ("fr", "ar"):
            self.write(self.locales / f"{code}.json", {"source_sha256": self.digest, "messages": self.french})

    def write(self, path, value):
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def test_all_pages_round_trip_and_generated_drift_is_detected(self):
        self.assertEqual(build(self.root), 3)
        self.assertEqual(build(self.root, check=True), 3)
        (self.root / "site/fr/index.html").write_text("outdated")
        with self.assertRaisesRegex(ValueError, "generated pages are stale"):
            build(self.root, check=True)

    def test_missing_keys_empty_messages_and_english_copies_fail(self):
        for broken in ({}, {**self.french, "m001": ""}):
            with self.assertRaises(ValueError):
                validate_messages(self.source, broken, "fr")
        text = {"m001": "Every complete guide must be translated without copying English sentences."}
        with self.assertRaisesRegex(ValueError, "untranslated English"):
            validate_messages(text, text, "fr")

    def test_links_code_markup_and_placeholders_cannot_change(self):
        for original, replacement in (("compact: true", "compact: false"),
                                       ('href="#install"', 'href="https://wrong.example/"'),
                                       ("<p>", '<p onclick="bad()">'),
                                       ("</p>", "</p><script>bad()</script>")):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                validate_messages(self.source, {**self.french,
                    "m001": self.french["m001"].replace(original, replacement)}, "fr")
        with self.assertRaisesRegex(ValueError, "placeholders changed"):
            validate_messages(self.source, {**self.french, "a001": "Guides : {total}."}, "fr")

    def test_stale_translation_requires_review(self):
        self.write(self.locales / "en.json", {**self.source, "a001": "Results: {count}."})
        with self.assertRaisesRegex(ValueError, "stale translation"):
            build(self.root)

    def test_duplicate_json_keys_fail(self):
        path = self.locales / "bad.json"
        path.write_text('{"m001":"first","m001":"last"}')
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            read_json(path)

    def test_rtl_relative_links_hreflang_and_attribute_escaping(self):
        text = render(self.template, self.languages, self.languages[2],
                      {**self.french, "a001": 'An "attribute" & text'})
        self.assertIn('lang="ar" dir="rtl"', text)
        self.assertIn('href="../assets/style.css"', text)
        self.assertIn('href="../" lang="en"', text)
        self.assertIn('href="../fr/" lang="fr"', text)
        self.assertIn('hreflang="x-default"', text)
        self.assertIn('href="https://ha-homelab.github.io/ha-desloc/ar/"', text)
        self.assertIn('aria-label="An &quot;attribute&quot; &amp; text"', text)

    def test_unknown_language_path_and_extra_page_fail(self):
        with self.assertRaisesRegex(ValueError, "unsupported language"):
            build(self.root, only="../../private")
        extra = self.root / "site/removed/index.html"
        extra.parent.mkdir(parents=True)
        extra.write_text("stale page")
        with self.assertRaisesRegex(ValueError, "unlisted wiki pages"):
            build(self.root)


class RepositoryCatalogTests(unittest.TestCase):
    def test_wiki_matches_the_existing_integration_language_catalog(self):
        _, languages, _, _ = load_sources(ROOT)
        integration = {path.stem for path in (ROOT / "custom_components/desloc/translations").glob("*.json")}
        self.assertEqual({language["code"] for language in languages}, integration)
        self.assertEqual({language["code"] for language in languages if language.get("dir") == "rtl"},
                         {"ar", "fa", "he"})


if __name__ == "__main__":
    unittest.main()
