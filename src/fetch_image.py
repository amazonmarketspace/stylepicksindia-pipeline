#!/usr/bin/env python3
"""
Loads product images from data/images/<ASIN>.jpg (committed to repo).
Falls back to Amazon direct download if not found locally.
"""
import sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / "data" / "images"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://www.amazon.in/",
}

KNOWN_IMAGE_IDS = {
    "B0CHJ3X3VM": "71dsoiS55DL",
    "B0D9S87H53": "61H84kDDNFL",
    "B0GY89ZBD8": "61uLwz0SdbL",
    "B0D3DJKVDM": "619B+x+wIAL",
    "B0FWKJ381P": "615LXD8Wr5L",
    "B0DG2WDRCM": "61Vl9TF2+DL",
    "B0DHHBVVHX": "51sVuyIolqL",
}


def fetch(asin: str) -> Path | None:
    # 1. Check local repo images first (committed)
    local = IMG_DIR / f"{asin}.jpg"
    if local.exists() and local.stat().st_size > 5000:
        return local

    # 2. Try direct Amazon download (works on GitHub Actions)
    img_id = KNOWN_IMAGE_IDS.get(asin)
    if img_id:
        for size in ["._AC_SX679_", "._AC_SX466_", ""]:
            url = f"https://m.media-amazon.com/images/I/{urllib.parse.quote(img_id)}{size}.jpg"
            try:
                import urllib.parse
                req = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = r.read()
                if len(data) > 5000 and data[:3] == b'\xff\xd8\xff':
                    local.write_bytes(data)
                    return local
            except Exception:
                continue
    return None


if __name__ == "__main__":
    import urllib.parse
    asin = sys.argv[1] if len(sys.argv) > 1 else "B0CHJ3X3VM"
    result = fetch(asin)
    print(result or "no image")
