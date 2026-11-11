#!/usr/bin/env python3
"""Render the English and Spanish pages from the shared template."""

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ROOT / "scripts" / "locales"
TEMPLATE = ROOT / "scripts" / "page.template.html"
WEB = ROOT / "web"
TOKEN = re.compile(r"@@([A-Za-z0-9_]+)@@")


def load(lang):
    return json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8"))


def render(lang, data, template):
    out = template
    for key, value in data.items():
        if not isinstance(value, str):
            continue
        out = out.replace(f"@@{key}@@", html.escape(value, quote=True))
    missing = sorted(set(TOKEN.findall(out)))
    if missing:
        raise SystemExit(f"{lang} page still has placeholders: {', '.join(missing)}")
    return out


def redirect_page(data):
    desc = html.escape(data["description"], quote=True)
    image = html.escape(data["og_image"], quote=True)
    title = html.escape(data["og_title"], quote=True)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="https://radar-30x-three.vercel.app/">
<link rel="alternate" hreflang="en" href="https://radar-30x-three.vercel.app/">
<link rel="alternate" hreflang="es" href="https://radar-30x-three.vercel.app/es/">
<link rel="alternate" hreflang="x-default" href="https://radar-30x-three.vercel.app/">
<meta http-equiv="refresh" content="0; url=/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Radar 30X">
<meta property="og:locale" content="en_US">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="https://radar-30x-three.vercel.app/">
<meta property="og:image" content="{image}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{image}">
<script>location.replace("/");</script>
</head>
<body>
<p><a href="/">Radar 30X</a></p>
</body>
</html>
"""


def main():
    en = load("en")
    es = load("es")
    if set(en) != set(es):
        missing_es = sorted(set(en) - set(es))
        missing_en = sorted(set(es) - set(en))
        raise SystemExit(f"locale keys differ. only en: {missing_es}. only es: {missing_en}")
    template = TEMPLATE.read_text(encoding="utf-8")
    (WEB / "index.html").write_text(render("en", en, template), encoding="utf-8")
    (WEB / "es").mkdir(exist_ok=True)
    (WEB / "es" / "index.html").write_text(render("es", es, template), encoding="utf-8")
    (WEB / "en").mkdir(exist_ok=True)
    (WEB / "en" / "index.html").write_text(redirect_page(en), encoding="utf-8")
    i18n = "window.RADAR_I18N = " + json.dumps({"en": en, "es": es}, ensure_ascii=False, indent=2) + ";\n"
    (WEB / "i18n.js").write_text(i18n, encoding="utf-8")


if __name__ == "__main__":
    main()
