#!/usr/bin/env python3
"""
Auto-scrapes Amazon India daily for smartphones + accessories with best discounts.
Adds NEW products (not already in sheet) to the Google Sheet with status=ready.
Runs before from_sheet.py in the daily workflow.

Strategy:
- Searches 15 URL patterns covering smartphones + all accessory sub-categories
- Deduplicates against existing ASINs in the sheet
- Adds up to DAILY_NEW_TARGET new products per run
- Sheet always has fresh stock — never runs dry
"""
import json, os, sys, time, urllib.request, urllib.parse, re
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

ROOT              = Path(__file__).resolve().parent.parent
SHEET_ID          = os.environ.get("GSHEET_ID")
TAB               = os.environ.get("GSHEET_TAB", "Sheet1")
DAILY_NEW_TARGET  = int(os.environ.get("DAILY_NEW_TARGET", "40"))  # add 40 fresh products/day

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SEARCHES = [
    # Smartphones by brand
    ("https://www.amazon.in/s?k=samsung+smartphone+india&s=discount-rank",        "smartphone"),
    ("https://www.amazon.in/s?k=redmi+note+smartphone+india&s=discount-rank",     "smartphone"),
    ("https://www.amazon.in/s?k=realme+smartphone+india+5g&s=discount-rank",      "smartphone"),
    ("https://www.amazon.in/s?k=poco+smartphone+india&s=discount-rank",           "smartphone"),
    ("https://www.amazon.in/s?k=motorola+moto+smartphone+india&s=discount-rank",  "smartphone"),
    ("https://www.amazon.in/s?k=vivo+smartphone+india&s=discount-rank",           "smartphone"),
    ("https://www.amazon.in/s?k=infinix+smartphone+india&s=discount-rank",        "smartphone"),
    ("https://www.amazon.in/s?k=iqoo+smartphone+india&s=discount-rank",           "smartphone"),
    ("https://www.amazon.in/s?k=oneplus+smartphone+india&s=discount-rank",        "smartphone"),
    ("https://www.amazon.in/s?k=nokia+smartphone+india&s=discount-rank",          "smartphone"),
    # Accessories
    ("https://www.amazon.in/s?k=fast+charger+india+gan&s=discount-rank",          "charger"),
    ("https://www.amazon.in/s?k=power+bank+india+20000mah&s=discount-rank",       "powerbank"),
    ("https://www.amazon.in/s?k=wireless+earbuds+india+under+2000&s=discount-rank","earphone"),
    ("https://www.amazon.in/s?k=phone+case+cover+samsung+redmi&s=discount-rank",  "case"),
    ("https://www.amazon.in/s?k=usb+c+cable+fast+charging+india&s=discount-rank", "cable"),
    ("https://www.amazon.in/s?k=tempered+glass+screen+protector+india&s=discount-rank","protector"),
    ("https://www.amazon.in/s?k=bluetooth+earphones+india+under+500&s=discount-rank","earphone"),
    ("https://www.amazon.in/s?k=car+phone+holder+mount+india&s=discount-rank",    "car"),
    ("https://www.amazon.in/s?k=magsafe+wireless+charger+india&s=discount-rank",  "charger"),
    ("https://www.amazon.in/s?k=selfie+stick+tripod+phone+india&s=discount-rank", "accessory"),
]

PHONE_KEYWORDS = ['smartphone','5g','4g','gb ram','gb storage','android','mobile phone']
PHONE_BRANDS   = ['samsung','redmi','realme','poco','vivo','oppo','motorola','nokia',
                   'iqoo','oneplus','infinix','tecno','lava','mi','honor','nothing']

HOOKS = {
    "smartphone": lambda p: {
        "hook":      f"{p['brand']} {int(p['discount'])}% off - best smartphone deal on Amazon India today",
        "feature_1": "Powerful processor handles gaming and multitasking without lag",
        "feature_2": "All day battery life - no more mid-day charging anxiety",
        "feature_3": "Quality camera system punches above its price range",
        "verdict":   f"Best value smartphone under Rs{int(p['price'])} available right now",
    },
    "charger": lambda p: {
        "hook":      f"Charges your phone {p['discount']}% faster for {p['discount']}% less",
        "feature_1": "Fast charging technology - full charge in under 1 hour",
        "feature_2": "Compatible with all Android phones iPhones and laptops",
        "feature_3": "Compact GaN design stays cool even during fast charging",
        "verdict":   "Your stock charger is wasting your time - upgrade today",
    },
    "powerbank": lambda p: {
        "hook":      f"Never get stranded with dead battery again - {p['discount']}% off today",
        "feature_1": "High capacity charges your phone 2 to 3 times fully",
        "feature_2": "Fast charging both input and output saves your time",
        "feature_3": "Slim lightweight design fits in pocket or small bag",
        "verdict":   "Best power bank for daily commute and travel in India",
    },
    "earphone": lambda p: {
        "hook":      f"Sound quality that beats earphones costing 3x the price",
        "feature_1": "Deep bass and crystal clear highs for all music genres",
        "feature_2": "Comfortable secure fit stays in ear during workouts",
        "feature_3": "Built in microphone delivers clear voice on calls",
        "verdict":   f"Best earphone under Rs{int(p['price'])} you can buy in India right now",
    },
    "case": lambda p: {
        "hook":      f"Protect your Rs{int(p['mrp'])+10000} phone for just Rs{int(p['price'])}",
        "feature_1": "Military grade drop protection tested up to 2 meters",
        "feature_2": "Precise cutouts for camera charging port and all buttons",
        "feature_3": "Slim fit does not add bulk keeps phone looking premium",
        "verdict":   "One drop can crack your screen - this prevents it",
    },
    "protector": lambda p: {
        "hook":      f"One rupee of protection for every thousand your phone costs",
        "feature_1": "9H hardness tempered glass harder than your display",
        "feature_2": "Crystal clarity preserves full display quality and touch sensitivity",
        "feature_3": "Bubble free installation takes under 2 minutes",
        "verdict":   "Cheapest insurance you can buy for your phone screen",
    },
    "cable": lambda p: {
        "hook":      f"The charging cable that actually survives daily use",
        "feature_1": "Nylon braided reinforcement resists bending and fraying",
        "feature_2": "Supports fast charging and high speed data transfer",
        "feature_3": "Works with all USB Type C Android and Lightning iPhone",
        "verdict":   "Buy two - one for home one for your bag",
    },
    "car": lambda p: {
        "hook":      f"Use your phone safely for navigation without holding it",
        "feature_1": "360 degree rotation for perfect landscape or portrait angle",
        "feature_2": "Strong grip holds phone securely on all road conditions",
        "feature_3": "One hand quick mount and release while driving",
        "verdict":   "Essential for safe phone navigation while driving",
    },
    "accessory": lambda p: {
        "hook":      f"{p['discount']}% off on this must have smartphone accessory",
        "feature_1": "Universal compatibility with all major smartphone brands",
        "feature_2": "Premium quality build designed to last years not months",
        "feature_3": "Compact size easy to carry and use anywhere",
        "verdict":   "Practical upgrade that makes your smartphone more useful",
    },
}


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", errors="ignore")


def parse_page(html: str, category: str) -> list:
    """Parse Amazon search results page, extract product data."""
    products = []
    # Find all data-asin blocks
    asin_pattern = re.compile(
        r'data-asin="([A-Z0-9]{10})"[^>]*data-component-type="s-search-result"',
        re.DOTALL
    )
    price_pattern    = re.compile(r'<span class="a-price-whole">([\d,]+)<')
    mrp_pattern      = re.compile(r'a-text-price[^>]*>.*?<span[^>]*>([\d,]+)<', re.DOTALL)
    title_pattern    = re.compile(r'<span[^>]*class="a-size-medium[^"]*a-color-base[^"]*a-text-normal[^"]*"[^>]*>([^<]+)<')
    discount_pattern = re.compile(r'\((\d+)%\s*off\)')

    # Split by search result blocks
    blocks = re.split(r'data-component-type="s-search-result"', html)
    for block in blocks[1:]:
        asin_m = re.search(r'data-asin="([A-Z0-9]{10})"', block)
        if not asin_m:
            continue
        asin = asin_m.group(1)

        title_m = title_pattern.search(block)
        if not title_m:
            # fallback
            title_m2 = re.search(r'alt="([^"]{10,100})"', block)
            title = title_m2.group(1) if title_m2 else ""
        else:
            title = title_m.group(1).strip()

        if not title or len(title) < 8:
            continue

        price_m = price_pattern.search(block)
        if not price_m:
            continue
        price = float(price_m.group(1).replace(",", ""))
        if price < 99 or price > 25000:
            continue

        mrp_m = mrp_pattern.search(block)
        mrp = float(mrp_m.group(1).replace(",", "")) if mrp_m else price

        disc_m = discount_pattern.search(block)
        discount = int(disc_m.group(1)) if disc_m else (
            round((mrp - price) / mrp * 100) if mrp > price else 0
        )
        if discount < 15:
            continue

        # Validate category match
        n = title.lower()
        if category == "smartphone":
            if not (any(b in n for b in PHONE_BRANDS) and
                    any(k in n for k in PHONE_KEYWORDS)):
                continue

        brand = title.split()[0][:20]
        products.append({
            "asin": asin, "name": title[:100], "brand": brand,
            "mrp": round(mrp), "price": round(price),
            "category": category, "discount": discount,
        })
    return products


def svc():
    creds = Credentials.from_service_account_info(
        json.loads(os.environ["GOOGLE_CREDS"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return build("sheets", "v4", credentials=creds).spreadsheets()


def main():
    if not SHEET_ID:
        sys.exit("GSHEET_ID not set")

    s = svc()

    # Get existing ASINs from sheet to avoid duplicates
    existing = s.values().get(
        spreadsheetId=SHEET_ID,
        range=f"{TAB}!A1:A5000"
    ).execute().get("values", [])

    existing_asins = {row[0].strip() for row in existing[1:] if row}
    print(f"Sheet has {len(existing_asins)} existing ASINs")

    # Scrape Amazon
    new_products = []
    seen_asins   = set(existing_asins)

    for url, category in SEARCHES:
        if len(new_products) >= DAILY_NEW_TARGET:
            break
        try:
            print(f"  Scraping: {category} — {url[35:70]}...")
            html = fetch_html(url)
            products = parse_page(html, category)
            for p in products:
                if p["asin"] not in seen_asins:
                    seen_asins.add(p["asin"])
                    # Enrich with hooks/features
                    gen = HOOKS.get(category, HOOKS["accessory"])
                    extras = gen(p)
                    new_products.append({
                        "asin":      p["asin"],
                        "name":      p["name"],
                        "brand":     p["brand"],
                        "mrp":       p["mrp"],
                        "price":     p["price"],
                        "category":  p["category"],
                        "hook":      extras["hook"],
                        "feature_1": extras["feature_1"],
                        "feature_2": extras["feature_2"],
                        "feature_3": extras["feature_3"],
                        "verdict":   extras["verdict"],
                        "status":    "ready",
                    })
            time.sleep(1)  # polite delay
        except Exception as e:
            print(f"  Scrape failed for {url[:50]}: {e}", file=sys.stderr)
            continue

    if not new_products:
        print("No new products found today — existing sheet stock is sufficient")
        return

    # Append new products to sheet
    COLS = ["asin","name","brand","mrp","price","category","hook",
            "feature_1","feature_2","feature_3","verdict","status"]

    first_empty = len(existing) + 1
    values = [[str(p.get(c,"")) for c in COLS] for p in new_products]

    batch_size = 50
    for i in range(0, len(values), batch_size):
        batch     = values[i:i+batch_size]
        start_row = first_empty + i
        end_row   = start_row + len(batch) - 1
        s.values().update(
            spreadsheetId=SHEET_ID,
            range=f"{TAB}!A{start_row}:L{end_row}",
            valueInputOption="RAW",
            body={"values": batch}
        ).execute()

    print(f"✅ Added {len(new_products)} new products to sheet "
          f"(rows {first_empty}–{first_empty+len(new_products)-1})")


if __name__ == "__main__":
    main()
