#!/usr/bin/env python3
"""Validate the static wiki before publishing it; requires only Python's stdlib."""

from __future__ import annotations

import argparse
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import re
import tempfile
import unittest
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree


SITE = Path(__file__).resolve().parents[1] / "site"
ORIGIN = "https://ha-homelab.github.io"
BASE_PATH = "/ha-desloc/"
BUDGETS = {".html": 150_000, ".css": 40_000, ".js": 24_000}
FORBIDDEN_PARTS = {".git", ".private", ".env", "__pycache__", "node_modules"}
FORBIDDEN_SUFFIXES = {".pem", ".key", ".har", ".mitm", ".p12", ".pfx", ".pyc"}
CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)


class Page(HTMLParser):
    """Collect publishing contracts without executing scripts or fetching URLs."""

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.references: list[tuple[str, bool]] = []
        self.errors: list[str] = []
        self.tags: Counter[str] = Counter()
        self.meta: dict[str, str] = {}
        self.canonicals: list[str] = []
        self.language = ""
        self.title = ""
        self.in_title = False
        self.feed(source)
        self.close()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        self.tags[tag] += 1
        if len(values) != len(attrs):
            self.errors.append(f"duplicate attribute on <{tag}>")
        if values.get("id"):
            self.ids.append(str(values["id"]))
        if any(key.lower().startswith("on") for key in values):
            self.errors.append(f"inline event handler on <{tag}>")
        if tag in {"base", "iframe", "object", "embed"}:
            self.errors.append(f"unsupported embedded content: <{tag}>")
        if tag == "html":
            self.language = values.get("lang") or ""
        if tag == "title":
            self.in_title = True
        if tag == "meta" and values.get("name"):
            self.meta[str(values["name"])] = values.get("content") or ""
        if tag == "link" and "canonical" in (values.get("rel") or "").split():
            self.canonicals.append(values.get("href") or "")
        elif values.get("href"):
            language_alternate = (tag == "link" and values.get("hreflang")
                                  and "alternate" in (values.get("rel") or "").split())
            self.references.append((str(values["href"]), tag != "a" and not language_alternate))
        for attr in ("src", "poster", "xlink:href"):
            if values.get(attr):
                self.references.append((str(values[attr]), True))
        if values.get("srcset"):
            self.references.extend(
                (item.strip().split()[0], True)
                for item in str(values["srcset"]).split(",") if item.strip()
            )
        if tag == "img" and "alt" not in values:
            self.errors.append("image missing alt text")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title += data


def local_reference(root: Path, page: Path, value: str) -> tuple[Path, str] | None:
    """Resolve local URLs, including project-root URLs used by the 404 page."""
    url = urlsplit(value)
    if url.scheme or url.netloc:
        return None
    url_path = unquote(url.path)
    if url_path.startswith(BASE_PATH):
        target = root / url_path[len(BASE_PATH):]
    elif url_path.startswith("/"):
        raise ValueError(f"URL escapes the project Pages path: {value}")
    else:
        target = page.parent / url_path if url_path else page
    if url_path.endswith("/"):
        target /= "index.html"
    target = target.resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"URL escapes the published site: {value}")
    return target, unquote(url.fragment)


def check_site(root: Path) -> list[str]:
    """Return concrete failures; never read a symlink or anything outside root."""
    errors: list[str] = []
    if root.is_symlink() or not root.is_dir():
        return ["site directory is missing or is a symlink"]
    pages: dict[Path, Page] = {}
    files = sorted(root.rglob("*"))
    for path in files:
        relative = path.relative_to(root)
        if path.is_symlink():
            errors.append(f"{relative}: symlinks cannot be published")
            continue
        if not path.is_file():
            continue
        if any(part in FORBIDDEN_PARTS or part.startswith(".env.") for part in relative.parts):
            errors.append(f"{relative}: private/development file cannot be published")
            continue
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"{relative}: private/capture file cannot be published")
            continue
        budget = BUDGETS.get(path.suffix.lower())
        if budget and path.stat().st_size > budget:
            errors.append(f"{relative}: exceeds {budget:,}-byte budget")
        if path.suffix == ".html":
            try:
                pages[path.resolve()] = Page(path.read_text(encoding="utf-8"))
            except (UnicodeError, ValueError) as exc:
                errors.append(f"{relative}: invalid HTML input: {exc}")
    for required in ("index.html", "404.html", "assets/style.css", "assets/elevate.css", "assets/app.js", "assets/favicon.svg"):
        if not (root / required).is_file():
            errors.append(f"missing required publish file: {required}")
    for path, page in pages.items():
        label = path.relative_to(root.resolve())
        errors.extend(f"{label}: {message}" for message in page.errors)
        duplicates = sorted(key for key, count in Counter(page.ids).items() if count > 1)
        if duplicates:
            errors.append(f"{label}: duplicate IDs: {', '.join(duplicates)}")
        if not page.language or not page.title.strip() or page.tags["title"] != 1:
            errors.append(f"{label}: lang and a nonempty title are required")
        if page.tags["main"] != 1 or page.tags["h1"] != 1:
            errors.append(f"{label}: exactly one main landmark and one h1 are required")
        if not page.meta.get("description") or "width=device-width" not in page.meta.get("viewport", ""):
            errors.append(f"{label}: description and responsive viewport are required")
        page_suffix = "" if label.parent == Path(".") else label.parent.as_posix() + "/"
        canonical = ORIGIN + BASE_PATH + page_suffix
        if page.canonicals != [canonical]:
            errors.append(f"{label}: canonical must point to {canonical}")
        if path.name == "404.html" and "noindex" not in page.meta.get("robots", ""):
            errors.append(f"{label}: 404 page must be noindex")
        for value, embedded in page.references:
            url = urlsplit(value)
            if embedded and (url.scheme or url.netloc):
                errors.append(f"{label}: remote/embedded asset is not allowed: {value}")
                continue
            if url.scheme and url.scheme not in {"https", "mailto", "http"}:
                errors.append(f"{label}: unsupported link scheme: {value}")
                continue
            try:
                target = local_reference(root, path, value)
            except ValueError as exc:
                errors.append(f"{label}: {exc}")
                continue
            if target is None:
                continue
            dest, fragment = target
            if not dest.is_file():
                errors.append(f"{label}: missing local link/asset: {value}")
            elif fragment and dest.suffix == ".html" and fragment not in pages.get(dest, Page("")).ids:
                errors.append(f"{label}: missing anchor: {value}")
    for path in files:
        if path.suffix != ".css" or path.is_symlink() or not path.is_file():
            continue
        label = path.relative_to(root)
        css = path.read_text(encoding="utf-8")
        if re.search(r"@import\b", css, re.IGNORECASE):
            errors.append(f"{label}: CSS imports are not allowed; use local HTML links")
        for _, value in CSS_URL.findall(css):
            try:
                target = local_reference(root, path, value)
            except ValueError as exc:
                errors.append(f"{label}: {exc}")
                continue
            if target is None:
                errors.append(f"{label}: remote/embedded CSS asset is not allowed: {value}")
            elif not target[0].is_file():
                errors.append(f"{label}: missing CSS asset: {value}")
    for path in files:
        if path.suffix != ".svg" or path.is_symlink() or not path.is_file():
            continue
        label = path.relative_to(root)
        try:
            svg = ElementTree.fromstring(path.read_text(encoding="utf-8"))
        except (UnicodeError, ElementTree.ParseError) as exc:
            errors.append(f"{label}: invalid SVG: {exc}")
            continue
        for element in svg.iter():
            for key, value in element.attrib.items():
                if key.rsplit("}", 1)[-1] not in {"href", "src"}:
                    continue
                try:
                    target = local_reference(root, path, value)
                except ValueError as exc:
                    errors.append(f"{label}: {exc}")
                    continue
                if target is None:
                    errors.append(f"{label}: remote/embedded SVG asset is not allowed: {value}")
                elif not target[0].is_file():
                    errors.append(f"{label}: missing SVG asset: {value}")
    return errors


class CheckerTests(unittest.TestCase):
    """Regression probes for defects that would break a published wiki."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "assets").mkdir()
        for name in ("style.css", "elevate.css", "app.js", "favicon.svg"):
            (self.root / "assets" / name).write_text("")
        (self.root / "assets/favicon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        self.html = ('<!doctype html><html lang="en"><head><title>DESLOC wiki</title>'
                     '<meta name="description" content="Documentation">'
                     '<meta name="viewport" content="width=device-width, initial-scale=1">'
                     '<link rel="canonical" href="https://ha-homelab.github.io/ha-desloc/">'
                     '<meta name="robots" content="noindex"></head><body>'
                     '<main id="main"><h1>DESLOC</h1><a href="#main">Top</a></main></body></html>')
        (self.root / "index.html").write_text(self.html)
        (self.root / "404.html").write_text(self.html)

    def test_valid_site_and_versioned_assets(self) -> None:
        (self.root / "index.html").write_text(self.html.replace("</head>", '<script src="assets/app.js?v=1"></script></head>'))
        self.assertEqual(check_site(self.root), [])

    def test_duplicate_id_missing_anchor_and_missing_asset(self) -> None:
        invalid = '<div id="main"></div><a href="#missing">Missing</a><img src="gone.png" alt="gone">'
        (self.root / "index.html").write_text(self.html.replace("</main>", invalid + "</main>"))
        result = "\n".join(check_site(self.root))
        for message in ("duplicate IDs", "missing anchor", "missing local link/asset"):
            self.assertIn(message, result)

    def test_external_asset_and_escape_are_rejected(self) -> None:
        invalid = '<script src="https://cdn.example/script.js"></script><a href="../secret">Escape</a>'
        (self.root / "index.html").write_text(self.html.replace("</main>", invalid + "</main>"))
        result = "\n".join(check_site(self.root))
        self.assertIn("remote/embedded asset", result)
        self.assertIn("escapes the published site", result)

    def test_symlink_private_files_and_budgets_are_rejected(self) -> None:
        (self.root / "linked").symlink_to(self.root / "index.html")
        (self.root / "session.har").write_text("private")
        (self.root / "assets/app.js").write_text(" " * 24_001)
        result = "\n".join(check_site(self.root))
        for message in ("symlinks cannot", "private/capture", "byte budget"):
            self.assertIn(message, result)

    def test_root_relative_404_assets_and_remote_css(self) -> None:
        (self.root / "404.html").write_text(self.html.replace("</head>", '<link rel="stylesheet" href="/ha-desloc/assets/style.css"></head>'))
        self.assertEqual(check_site(self.root), [])
        (self.root / "assets/style.css").write_text('body { background: url("https://example.org/pixel.png"); }')
        self.assertIn("remote/embedded CSS asset", "\n".join(check_site(self.root)))

    def test_remote_svg_asset_is_rejected(self) -> None:
        (self.root / "assets/favicon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.org/pixel.png"/></svg>')
        self.assertIn("remote/embedded SVG asset", "\n".join(check_site(self.root)))

    def test_localized_pages_use_their_own_canonical_and_shared_assets(self) -> None:
        (self.root / "fr").mkdir()
        localized = self.html.replace('lang="en"', 'lang="fr"').replace(
            'href="https://ha-homelab.github.io/ha-desloc/"',
            'href="https://ha-homelab.github.io/ha-desloc/fr/"')
        localized = localized.replace("</head>",
            '<link rel="alternate" hreflang="en" href="https://ha-homelab.github.io/ha-desloc/">'
            '<link rel="stylesheet" href="../assets/style.css"></head>')
        (self.root / "fr/index.html").write_text(localized)
        self.assertEqual(check_site(self.root), [])
        (self.root / "fr/index.html").write_text(self.html)
        self.assertIn("canonical must point", "\n".join(check_site(self.root)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=SITE)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        unittest.main(argv=[__file__])
    else:
        failures = check_site(args.site)
        if failures:
            raise SystemExit("Wiki validation failed:\n- " + "\n- ".join(failures))
        print("Wiki links, semantics, asset budgets and publication boundaries passed.")
