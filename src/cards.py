#!/usr/bin/env python3
"""
Spec-card renderer. Produces 1920x1080 (and 1080x1920) product cards from CSV data.
No product photography required - typography, data bars, price panels.
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
BOLD = f"{FONT_DIR}/DejaVuSans-Bold.ttf"
REG  = f"{FONT_DIR}/DejaVuSans.ttf"
MONO = f"{FONT_DIR}/DejaVuSansMono-Bold.ttf"

# palette - high contrast, reads on mobile
BG     = (14, 16, 22)
PANEL  = (24, 27, 36)
ACCENT = (255, 196, 0)
GREEN  = (46, 204, 113)
TEXT   = (240, 242, 245)
MUTED  = (140, 148, 162)


def F(path, size):
    return ImageFont.truetype(path, size)


def wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def rrect(d, box, r, fill):
    d.rounded_rectangle(box, radius=r, fill=fill)


def card(p: dict, idx: int, total: int, size=(1920, 1080), cur="Rs"):
    W, H = size
    vert = H > W
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    s = W / 1920 if not vert else W / 1080
    pad = int(70 * s)

    # rank badge
    f_rank = F(BOLD, int(52 * s))
    badge_w = int(150 * s)
    rrect(d, (pad, pad, pad + badge_w, pad + int(80 * s)), int(14 * s), ACCENT)
    d.text((pad + badge_w // 2, pad + int(40 * s)), f"#{idx}",
           font=f_rank, fill=BG, anchor="mm")
    d.text((pad + badge_w + int(28 * s), pad + int(40 * s)),
           f"of {total}", font=F(REG, int(34 * s)), fill=MUTED, anchor="lm")

    y = pad + int(130 * s)

    # brand
    d.text((pad, y), p["brand"].upper(), font=F(BOLD, int(32 * s)), fill=ACCENT)
    y += int(52 * s)

    # product name
    f_name = F(BOLD, int(78 * s) if not vert else int(64 * s))
    for line in wrap(d, p["name"], f_name, W - 2 * pad)[:3]:
        d.text((pad, y), line, font=f_name, fill=TEXT)
        y += int(92 * s) if not vert else int(78 * s)

    y += int(30 * s)

    # price panel
    ph = int(190 * s)
    rrect(d, (pad, y, W - pad, y + ph), int(18 * s), PANEL)
    f_price = F(MONO, int(96 * s))
    d.text((pad + int(40 * s), y + ph // 2), f"{cur}{int(p['price'])}",
           font=f_price, fill=GREEN, anchor="lm")
    px = pad + int(40 * s) + d.textlength(f"{cur}{int(p['price'])}", font=f_price) + int(40 * s)

    if p.get("discount"):
        f_mrp = F(REG, int(42 * s))
        mrp_t = f"{cur}{int(p['mrp'])}"
        d.text((px, y + ph // 2 - int(28 * s)), mrp_t, font=f_mrp, fill=MUTED)
        lw = d.textlength(mrp_t, font=f_mrp)
        d.line((px, y + ph // 2 - int(6 * s), px + lw, y + ph // 2 - int(6 * s)),
               fill=MUTED, width=int(4 * s))
        d.text((px, y + ph // 2 + int(20 * s)), f"{p['discount']}% OFF",
               font=F(BOLD, int(46 * s)), fill=ACCENT)

    y += ph + int(50 * s)

    # feature rows
    f_feat = F(REG, int(46 * s) if not vert else int(40 * s))
    for k in ("feature_1", "feature_2", "feature_3"):
        if not p.get(k):
            continue
        d.ellipse((pad, y + int(16 * s), pad + int(18 * s), y + int(34 * s)), fill=ACCENT)
        for i, line in enumerate(wrap(d, p[k], f_feat, W - 2 * pad - int(50 * s))[:2]):
            d.text((pad + int(50 * s), y), line, font=f_feat, fill=TEXT)
            y += int(58 * s)
        y += int(26 * s)

    # verdict strip
    if p.get("verdict"):
        vh = int(120 * s)
        vy = H - pad - vh
        rrect(d, (pad, vy, W - pad, vy + vh), int(16 * s), PANEL)
        d.rectangle((pad, vy, pad + int(10 * s), vy + vh), fill=GREEN)
        f_v = F(BOLD, int(40 * s) if not vert else int(34 * s))
        lines = wrap(d, p["verdict"], f_v, W - 2 * pad - int(80 * s))[:2]
        ty = vy + vh // 2 - (len(lines) * int(46 * s)) // 2
        for line in lines:
            d.text((pad + int(40 * s), ty), line, font=f_v, fill=TEXT)
            ty += int(46 * s)

    return img


def title_card(headline: str, sub: str, size=(1920, 1080)):
    W, H = size
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    s = W / 1920
    f = F(BOLD, int(120 * s))
    lines = wrap(d, headline, f, int(W * 0.82))
    y = H // 2 - (len(lines) * int(140 * s)) // 2 - int(60 * s)
    for line in lines:
        d.text((W // 2, y), line, font=f, fill=TEXT, anchor="ma")
        y += int(140 * s)
    d.text((W // 2, y + int(40 * s)), sub, font=F(REG, int(52 * s)),
           fill=ACCENT, anchor="ma")
    return img
