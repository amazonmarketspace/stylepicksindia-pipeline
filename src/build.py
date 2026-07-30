#!/usr/bin/env python3
"""
Video package builder for Amazon-affiliate YouTube channel.
Input : data/products.csv  (+ config.yaml)
Output: out/<slug>/script.md, description.txt, shorts.md, manifest.json
"""
import csv, json, re, sys, datetime as dt
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

ROOT = Path(__file__).resolve().parent.parent
CFG  = yaml.safe_load((ROOT / "config.yaml").read_text())


# ---------- links ----------
def affiliate_url(asin: str) -> str:
    """Canonical /dp/ link + associate tag. No shorteners (Amazon prohibits them)."""
    asin = asin.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{10}", asin):
        raise ValueError(f"Bad ASIN: {asin!r}")
    return f"https://{CFG['marketplace']}/dp/{asin}/?tag={CFG['associate_tag']}"


# ---------- discount ----------
def discount_pct(mrp: float, price: float) -> int:
    if mrp <= 0 or price <= 0 or price >= mrp:
        return 0
    return round((mrp - price) / mrp * 100)


def headline(products: list[dict]) -> str:
    """Build a claim from the data, not from a template constant."""
    top = max(p["discount"] for p in products)
    cheap = min(p["price"] for p in products)
    if top >= 40:
        return f"Up to {top}% off"            # true: an actual product hits this
    return f"All under {CFG['currency']}{int(cheap) if cheap<1000 else 999}"


# ---------- load ----------
def load_products() -> list[dict]:
    rows = list(csv.DictReader((ROOT / "data" / "products.csv").open()))
    out = []
    for i, r in enumerate(rows, 1):
        mrp, price = float(r["mrp"]), float(r["price"])
        d = discount_pct(mrp, price)
        if CFG.get("require_real_discount") and mrp < price:
            sys.exit(f"Row {i}: price above MRP - check your data.")
        out.append({**r, "mrp": mrp, "price": price, "discount": d,
                    "url": affiliate_url(r["asin"])})
    return out


# ---------- outputs ----------
def build_script(ps: list[dict]) -> str:
    spp = CFG["long_form"]["seconds_per_product"]
    L = [f"# {headline(ps)} - {CFG['niche'].title()}", "",
         "## HOOK (0:00-0:15)",
         f"Ten {CFG['niche']} I actually use. Real prices, real discounts, "
         f"links below. Number 3 replaced something four times its price.", ""]
    t = 15
    for n, p in enumerate(ps, 1):
        mm, ss = divmod(t, 60)
        L += [f"## {n}. {p['name']} ({mm}:{ss:02d})",
              f"*{p['brand']} | {CFG['currency']}{p['price']:.0f}"
              + (f" (was {CFG['currency']}{p['mrp']:.0f}, {p['discount']}% off)"
                 if p["discount"] else "") + "*", "",
              f"**Hook:** {p['hook']}",
              f"- {p['feature_1']}", f"- {p['feature_2']}", f"- {p['feature_3']}",
              f"**Verdict:** {p['verdict']}", ""]
        t += spp
    L += ["## OUTRO", "Links in the description, ordered same as the video.",
          "", f"*Runtime ~{t//60}:{t%60:02d}*"]
    return "\n".join(L)


def build_description(ps: list[dict]) -> str:
    L = [f"{headline(ps)} on {CFG['niche']} - everything shown, with links.", "",
         CFG["disclosure"], CFG["price_caveat"], "", "-- PRODUCTS --", ""]
    for n, p in enumerate(ps, 1):
        tag = f" ({p['discount']}% off)" if p["discount"] else ""
        L += [f"{n}. {p['name']} - {CFG['currency']}{p['price']:.0f}{tag}",
              f"   {p['url']}", ""]
    L += ["-- CHAPTERS --"]
    t = 15
    for n, p in enumerate(ps, 1):
        L.append(f"{t//60}:{t%60:02d} {p['name']}")
        t += CFG["long_form"]["seconds_per_product"]
    L += ["", "#ad #amazonfinds #" + CFG["niche"].replace(" ", "")]
    return "\n".join(L)


def build_shorts(ps: list[dict]) -> str:
    """One Short per product - each is a standalone upload."""
    out = []
    for n, p in enumerate(ps, 1):
        out += [f"### Short {n}: {p['name']}",
                f"0-3s  HOOK: {p['hook']}",
                f"3-20s DEMO: {p['feature_1']} / {p['feature_2']}",
                f"20-27s PRICE: {CFG['currency']}{p['price']:.0f}"
                + (f", {p['discount']}% off" if p["discount"] else ""),
                f"27-30s CTA: Link in description.",
                f"DESC: {p['name']} - {p['url']}",
                f"      {CFG['disclosure']}", ""]
    return "\n".join(out)


def main():
    ps = load_products()
    slug = dt.date.today().isoformat()
    d = ROOT / "out" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "script.md").write_text(build_script(ps))
    (d / "description.txt").write_text(build_description(ps))
    (d / "shorts.md").write_text(build_shorts(ps))
    (d / "manifest.json").write_text(json.dumps(ps, indent=2))
    print(f"Built {len(ps)} products -> {d}")
    print(f"Headline: {headline(ps)}")


if __name__ == "__main__":
    main()
