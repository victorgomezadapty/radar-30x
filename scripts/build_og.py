#!/usr/bin/env python3
"""Draw the English and Spanish social preview images."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "og"
FONT = "/usr/share/fonts/truetype/macos"
W, H = 1200, 630
BG = (11, 16, 32)
INK = (255, 255, 255)
MUTED = (148, 163, 184)
ACCENT = (165, 180, 252)


def font(name, size):
    return ImageFont.truetype(f"{FONT}/Inter-{name}.ttf", size)


def wrap(draw, text, face, width):
    lines, cur = [], ""
    for word in text.split():
        trial = word if not cur else cur + " " + word
        if draw.textlength(trial, font=face) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def radar(draw):
    cx, cy, rings = 1010, 330, (190, 130, 74)
    for r in rings:
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(165, 180, 252, 70), width=2)
    draw.line((cx, cy, cx + 150, cy - 150), fill=ACCENT, width=3)
    draw.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=ACCENT)
    for x, y in ((1120, 180), (860, 430), (1080, 470)):
        draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=ACCENT)


def card(path, eyebrow, title, subtitle):
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    radar(draw)
    draw.text((72, 150), eyebrow, font=font("SemiBold", 22), fill=ACCENT)
    title_font = font("Bold", 58)
    y = 200
    for line in wrap(draw, title, title_font, 700):
        draw.text((72, y), line, font=title_font, fill=INK)
        y += 68
    sub_font = font("Regular", 26)
    y += 16
    for line in wrap(draw, subtitle, sub_font, 680):
        draw.text((72, y), line, font=sub_font, fill=MUTED)
        y += 38
    image.save(path, "PNG")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    card(
        OUT / "en.png",
        "RADAR 30X",
        "What are the 10 topics growing the most this week?",
        "Why they work, and how 30X adapts them for leaders in Latin America.",
    )
    card(
        OUT / "es.png",
        "RADAR 30X",
        "Descubre qué está creciendo hoy en redes, antes que todos.",
        "Cinco redes, un ranking hecho con datos y las ideas listas para tu audiencia.",
    )


if __name__ == "__main__":
    main()
