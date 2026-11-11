#!/usr/bin/env python3
"""English is the default page. Spanish stays available on its own URL."""

import json
import re
import struct
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://radar-30x-three.vercel.app"
QUESTION = "What are the 10 topics growing the most this week, why they work, and how 30X adapts them for leaders in Latin America?"
SPANISH_HERO = "Descubre qué está creciendo hoy en redes, antes que todos."


class MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lang = ""
        self.metas = []
        self.links = []
        self.title = []
        self.h1 = []
        self._capture = None
        self._buf = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "html":
            self.lang = data.get("lang", "")
        elif tag == "meta":
            self.metas.append(data)
        elif tag == "link":
            self.links.append(data)
        elif tag in ("title", "h1"):
            self._capture = tag
            self._buf = []

    def handle_data(self, data):
        if self._capture:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == self._capture:
            text = "".join(self._buf).strip()
            getattr(self, tag if tag != "title" else "title").append(text) if tag == "h1" else self.title.append(text)
            self._capture = None


def parse(path):
    parser = MetaParser()
    parser.feed(Path(path).read_text(encoding="utf-8"))
    return parser


def meta(parser, key, attr="property"):
    for item in parser.metas:
        if item.get(attr) == key or item.get("property") == key or item.get("name") == key:
            if key in (item.get(attr), item.get("property"), item.get("name")):
                return item.get("content", "")
    return ""


def hreflang(parser):
    return {item.get("hreflang"): item.get("href") for item in parser.links if item.get("rel") == "alternate"}


class LanguageDefaultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(["python3", "scripts/build_web.py"], cwd=ROOT, check=True)
        cls.en = parse(ROOT / "web" / "index.html")
        cls.es = parse(ROOT / "web" / "es" / "index.html")
        cls.en_html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        cls.es_html = (ROOT / "web" / "es" / "index.html").read_text(encoding="utf-8")
        cls.locales = {
            "en": json.loads((ROOT / "scripts" / "locales" / "en.json").read_text(encoding="utf-8")),
            "es": json.loads((ROOT / "scripts" / "locales" / "es.json").read_text(encoding="utf-8")),
        }

    def test_root_is_english(self):
        self.assertEqual(self.en.lang, "en")
        self.assertEqual(self.en.h1, ["What are the 10 topics growing the most this week?"])
        self.assertIn(QUESTION, self.en_html)
        self.assertNotIn("Descubre qué está", self.en_html)
        self.assertEqual(meta(self.en, "og:title"), "Radar 30X")
        self.assertEqual(meta(self.en, "og:description"), QUESTION)
        self.assertEqual(meta(self.en, "description", "name"), QUESTION)
        self.assertEqual(meta(self.en, "og:image"), f"{SITE}/og/en.png")
        self.assertEqual(meta(self.en, "og:locale"), "en_US")
        self.assertEqual(meta(self.en, "og:url"), f"{SITE}/")
        self.assertEqual(meta(self.en, "twitter:card", "name"), "summary_large_image")
        self.assertEqual(meta(self.en, "twitter:title", "name"), "Radar 30X")
        self.assertEqual(meta(self.en, "twitter:description", "name"), QUESTION)
        self.assertEqual(meta(self.en, "twitter:image", "name"), f"{SITE}/og/en.png")
        canonical = [item.get("href") for item in self.en.links if item.get("rel") == "canonical"]
        self.assertEqual(canonical, [f"{SITE}/"])
        self.assertEqual(hreflang(self.en), {
            "en": f"{SITE}/",
            "es": f"{SITE}/es/",
            "x-default": f"{SITE}/",
        })
        self.assertIn('href="/es/"', self.en_html)
        self.assertIn(">EN<", self.en_html)
        self.assertIn(">ES<", self.en_html)

    def test_spanish_url_stays_spanish(self):
        self.assertEqual(self.es.lang, "es")
        self.assertEqual(self.es.h1, [SPANISH_HERO])
        self.assertIn("Cinco redes, un ranking hecho con datos", self.es_html)
        self.assertEqual(meta(self.es, "og:description"), self.locales["es"]["og_description"])
        self.assertIn(SPANISH_HERO, meta(self.es, "og:description"))
        self.assertEqual(meta(self.es, "og:image"), f"{SITE}/og/es.png")
        self.assertEqual(meta(self.es, "og:locale"), "es_419")
        self.assertEqual(meta(self.es, "og:url"), f"{SITE}/es/")
        self.assertEqual(meta(self.es, "twitter:description", "name"), self.locales["es"]["og_description"])
        self.assertEqual(meta(self.es, "twitter:image", "name"), f"{SITE}/og/es.png")
        canonical = [item.get("href") for item in self.es.links if item.get("rel") == "canonical"]
        self.assertEqual(canonical, [f"{SITE}/es/"])
        self.assertEqual(hreflang(self.es)["x-default"], f"{SITE}/")
        self.assertIn('href="/"', self.es_html)

    def test_english_alias_redirects_home(self):
        config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
        redirects = {(item["source"], item["destination"]) for item in config["redirects"]}
        self.assertIn(("/en", "/"), redirects)
        self.assertIn(("/en/", "/"), redirects)
        self.assertIn(("/es", "/es/"), redirects)
        alias = parse(ROOT / "web" / "en" / "index.html")
        self.assertEqual(alias.lang, "en")
        self.assertIn('url=/', (ROOT / "web" / "en" / "index.html").read_text(encoding="utf-8"))
        self.assertEqual(meta(alias, "og:description"), QUESTION)
        self.assertEqual(meta(alias, "og:image"), f"{SITE}/og/en.png")

    def test_locales_and_script_stay_in_sync(self):
        self.assertEqual(set(self.locales["en"]), set(self.locales["es"]))
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        used = set(re.findall(r"\bT\.([A-Za-z_][A-Za-z0-9_]*)", app))
        self.assertTrue(used)
        self.assertTrue(used <= set(self.locales["en"]))
        template = (ROOT / "scripts" / "page.template.html").read_text(encoding="utf-8")
        tokens = set(re.findall(r"@@([A-Za-z0-9_]+)@@", template))
        self.assertTrue(tokens <= set(self.locales["en"]))
        subprocess.run(["node", "--check", "web/app.js"], cwd=ROOT, check=True)
        subprocess.run(["node", "--check", "web/i18n.js"], cwd=ROOT, check=True)

    def test_english_copy_reuses_project_strings(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8").replace("*", "")
        for phrase in (
            QUESTION,
            "It answers in one run, in 1 to 3 minutes, and for about 5 cents",
            "It works for AI (the main demo), fitness, or any open topic the user writes.",
            "It collects public pieces from YouTube, Reddit, Instagram, LinkedIn, TikTok, and Hacker News",
            "JEV classifies each piece (topic, hook, format, whether it mentions a launch)",
            "JEV scores audience fit (applicability, technical level, relevance for LatAm)",
            "It proposes three ready-to-copy pieces (carousel, reel, and LinkedIn post)",
            "Collects, measures, and decides the ranking",
            "It only writes; it does not touch the ranking",
            "only data from public pieces is used, never from people.",
        ):
            self.assertIn(phrase, readme)
            self.assertIn(phrase, self.en_html)

    def test_new_english_copy_has_no_forbidden_marks(self):
        def walk(value):
            if isinstance(value, str):
                self.assertNotIn("--", value)
                self.assertNotIn("\u2014", value)
                self.assertNotIn("\u2013", value)
                low = value.lower()
                for banned in ("optimo", "malqa", "riyadh", "armah"):
                    self.assertNotIn(banned, low)
            elif isinstance(value, dict):
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)
        walk(self.locales["en"])

    def test_social_images(self):
        for name in ("en.png", "es.png"):
            data = (ROOT / "web" / "og" / name).read_bytes()
            self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
            width, height = struct.unpack(">II", data[16:24])
            self.assertEqual((width, height), (1200, 630))


if __name__ == "__main__":
    unittest.main()
