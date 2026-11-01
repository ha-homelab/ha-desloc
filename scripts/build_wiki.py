#!/usr/bin/env python3
"""Render the complete static wiki in every supported language (stdlib only)."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
URL = "https://ha-homelab.github.io/ha-desloc/"
SLOT = re.compile(r"\{\{([a-z][a-z0-9_]*)\}\}")
PLACEHOLDER = re.compile(r"(?<!\{)\{[a-z][a-z0-9_]*\}(?!\})")
GENERATED = {"language", "direction", "canonical", "alternate_links", "asset_prefix",
             "current_language", "language_links"}
VOID_TAGS = {"br", "hr", "img", "input", "meta", "link"}


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    """Reject silent JSON key overwrites in source and translated catalogs."""
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


class Fragment(HTMLParser):
    """Capture markup and code contracts independently of translated prose."""

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=True)
        self.markup: list[tuple] = []
        self.code: list[str] = []
        self.text: list[str] = []
        self.stack: list[str] = []
        self.feed(source)
        self.close()
        if self.stack:
            raise ValueError("unclosed HTML in message")

    def handle_starttag(self, tag, attrs):
        if len(dict(attrs)) != len(attrs):
            raise ValueError("duplicate HTML attribute in message")
        if tag not in {"a", "strong", "em", "span", "p", "br", "code"}:
            raise ValueError(f"unsupported message tag: {tag}")
        self.markup.append(("start", tag, tuple(sorted(attrs))))
        if tag not in VOID_TAGS:
            self.stack.append(tag)
        if tag == "code":
            self.code.append("")

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            raise ValueError("unbalanced HTML in message")
        self.markup.append(("end", tag))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_data(self, data):
        self.text.append(data)
        if "code" in self.stack:
            self.code[-1] += data

    def handle_comment(self, data):
        raise ValueError("HTML comments are not allowed in messages")

    def handle_decl(self, decl):
        raise ValueError("HTML declarations are not allowed in messages")


def validate_messages(source: dict, translated: dict, language: str) -> None:
    if not isinstance(translated, dict) or translated.keys() != source.keys():
        raise ValueError(f"{language}: translation keys do not match English")
    for key, original in source.items():
        value = translated[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{language}/{key}: empty or non-text message")
        if "{{" in value or "}}" in value:
            raise ValueError(f"{language}/{key}: unresolved template slot")
        if Counter(PLACEHOLDER.findall(value)) != Counter(PLACEHOLDER.findall(original)):
            raise ValueError(f"{language}/{key}: named placeholders changed")
        if key.startswith("a"):
            if "<" in value or ">" in value:
                raise ValueError(f"{language}/{key}: markup in a plain attribute")
            continue
        before, after = Fragment(original), Fragment(value)
        if before.markup != after.markup:
            raise ValueError(f"{language}/{key}: HTML structure, attributes or links changed")
        if before.code != after.code:
            raise ValueError(f"{language}/{key}: code example changed")
        if language != "en" and value == original and len("".join(before.text).split()) > 7:
            raise ValueError(f"{language}/{key}: untranslated English sentence")


def load_sources(root: Path) -> tuple[str, list[dict], dict, str]:
    wiki = root / "wiki"
    template = (wiki / "template.html").read_text(encoding="utf-8")
    languages = read_json(wiki / "languages.json")
    codes = [item["code"] for item in languages]
    if not codes or codes[0] != "en" or len(codes) != len(set(codes)):
        raise ValueError("language catalog must start with English and have unique codes")
    for item in languages:
        if not re.fullmatch(r"[a-z]{2}(?:-[A-Za-z]{2,4})?", item["code"]):
            raise ValueError("invalid language path")
        if not item.get("label") or item.get("dir", "ltr") not in {"ltr", "rtl"}:
            raise ValueError("invalid language label or direction")
    english_path = wiki / "locales/en.json"
    source = read_json(english_path)
    if not source or any(not re.fullmatch(r"[ma][0-9]{3}", key) for key in source):
        raise ValueError("invalid source message keys")
    if set(SLOT.findall(template)) != source.keys() | GENERATED:
        raise ValueError("template slots and source messages do not match")
    validate_messages(source, source, "en")
    return template, languages, source, hashlib.sha256(english_path.read_bytes()).hexdigest()


def page_path(code: str) -> str:
    return "" if code == "en" else code + "/"


def render(template: str, languages: list[dict], language: dict, messages: dict) -> str:
    code = language["code"]
    prefix = "" if code == "en" else "../"
    links = []
    alternates = []
    for item in languages:
        target = item["code"]
        current = ' aria-current="page"' if target == code else ""
        href = (prefix + page_path(target)) or "./"
        links.append(f'<a href="{href}" lang="{target}" hreflang="{target}" '
                     f'dir="{item.get("dir", "ltr")}"{current}>{escape(item["label"])}</a>')
        alternates.append(f'<link rel="alternate" hreflang="{target}" href="{URL}{page_path(target)}">')
    alternates.append(f'<link rel="alternate" hreflang="x-default" href="{URL}">')
    values = {key: escape(value, quote=True) if key.startswith("a") else value
              for key, value in messages.items()}
    values.update(language=code, direction=language.get("dir", "ltr"),
                  canonical=URL + page_path(code), alternate_links="\n".join(alternates),
                  asset_prefix=prefix, current_language=escape(language["label"]),
                  language_links="\n".join(links))
    return SLOT.sub(lambda match: values[match[1]], template)


def build(root: Path, check: bool = False, only: str | None = None) -> int:
    template, languages, source, digest = load_sources(root)
    if only and only not in {item["code"] for item in languages}:
        raise ValueError(f"unsupported language: {only}")
    expected_files = {root / "site" / page_path(item["code"]) / "index.html" for item in languages}
    unexpected = set((root / "site").rglob("index.html")) - expected_files
    if unexpected:
        raise ValueError("unlisted wiki pages: " + ", ".join(str(p) for p in sorted(unexpected)))
    outputs = []
    for language in languages:
        code = language["code"]
        if only and code != only:
            continue
        messages = source
        if code != "en":
            catalog = read_json(root / "wiki/locales" / f"{code}.json")
            if catalog.get("source_sha256") != digest:
                raise ValueError(f"{code}: stale translation; review changed English content")
            messages = catalog.get("messages")
            validate_messages(source, messages, code)
        path = root / "site" / page_path(code) / "index.html"
        outputs.append((path, render(template, languages, language, messages)))
    stale = []
    for path, output in outputs:
        if check:
            if not path.is_file() or path.read_text(encoding="utf-8") != output:
                stale.append(str(path.relative_to(root)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(output, encoding="utf-8")
    if stale:
        raise ValueError("generated pages are stale; run scripts/build_wiki.py: " + ", ".join(stale))
    return len(outputs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if committed pages are stale")
    parser.add_argument("--language", help="preview one language; CI always checks every language")
    args = parser.parse_args()
    try:
        count = build(ROOT, args.check, args.language)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f"Wiki generation failed: {error}\n")
    print(f"Wiki {'verified' if args.check else 'rendered'}: {count} complete language pages.")
