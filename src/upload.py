#!/usr/bin/env python3
"""
Uploads rendered videos to YouTube and marks sheet rows as 'done'.
Default privacy: public
Daily quota: 1 long + 5 Shorts (6 videos × 1,600 units = 9,600 / 10,000 limit)
"""
import argparse, json, os, sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials as SACredentials

ROOT       = Path(__file__).resolve().parent.parent
TOKEN_URI  = "https://oauth2.googleapis.com/token"

BASE_TAGS = [
    "best smartphone india 2026", "budget smartphone india",
    "smartphone under 10000", "smartphone under 20000",
    "best phone india", "android phone india", "5g phone india",
    "best camera phone india", "smartphone review india",
    "smartphone accessories", "mobile accessories india",
    "best smartphone accessories", "phone accessories under 500",
    "fast charger india", "gan charger", "power bank india",
    "wireless charger india", "usb c charger", "car charger india",
    "amazon india deals", "amazon finds india", "amazon sale india",
    "best deals amazon india", "budget tech india", "tech deals india",
    "सस्ता स्मार्टफोन", "मोबाइल एक्सेसरी", "अमेज़न ऑफर", "बेस्ट फोन इंडिया",
]


def yt_client():
    for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
        if not os.environ.get(k):
            sys.exit(f"{k} not set")
    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri=TOKEN_URI,
        scopes=["https://www.googleapis.com/auth/youtube.upload"])
    return build("youtube", "v3", credentials=creds)


def sheets_client():
    """Returns Sheets service for marking rows done after upload."""
    raw = os.environ.get("GOOGLE_CREDS")
    if not raw:
        return None
    creds = SACredentials.from_service_account_info(
        json.loads(raw),
        scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return build("sheets", "v4", credentials=creds).spreadsheets()


def mark_done(rows_info: dict, sheets):
    """Mark rows as done in the sheet after successful upload."""
    if not sheets or not rows_info:
        return
    col    = rows_info.get("status_col")
    tab    = rows_info.get("tab", "Sheet1")
    rownums = rows_info.get("rows", [])
    sheet_id = os.environ.get("GSHEET_ID")
    if not col or not rownums or not sheet_id:
        return
    sheets.values().batchUpdate(
        spreadsheetId=sheet_id,
        body={
            "valueInputOption": "RAW",
            "data": [{"range": f"{tab}!{col}{r}", "values": [["done"]]}
                     for r in rownums]
        }
    ).execute()
    print(f"Marked rows {rownums} → done")


def product_tags(p: dict) -> list:
    tags = [p.get("brand", "").lower()]
    name_words = p.get("name", "").lower().replace("-", " ").split()
    tags.extend([w for w in name_words if len(w) > 3][:4])
    tags.append(p.get("category", ""))
    if p.get("discount", 0) >= 50:
        tags.append(f"{p['discount']}% off amazon")
    tags.append(f"rs {int(p.get('price', 0))} india")
    return [t for t in tags if t]


def dedup(tags):
    seen, out = set(), []
    for t in tags:
        t = t.strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def push(svc, path: Path, title: str, desc: str, tags: list, privacy: str):
    body = {
        "snippet": {
            "title": title[:100],
            "description": desc[:4900],
            "tags": tags[:30],
            "categoryId": "28",
            "defaultLanguage": "hi",
            "defaultAudioLanguage": "hi",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
            "madeForKids": False,
        }
    }
    media = MediaFileUpload(str(path), chunksize=-1, resumable=True,
                            mimetype="video/mp4")
    req = svc.videos().insert(part="snippet,status", body=body, media_body=media)
    res = None
    while res is None:
        _, res = req.next_chunk()
    vid = res["id"]
    print(f"  https://youtu.be/{vid}  [{privacy}]")
    return vid


def latest():
    ds = sorted((ROOT / "out").glob("*/manifest.json"))
    if not ds:
        sys.exit("Nothing rendered.")
    return ds[-1].parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--privacy",   default="public",
                    choices=["private","unlisted","public"])
    ap.add_argument("--max-long",  type=int, default=1)
    ap.add_argument("--max-short", type=int, default=5)
    ap.add_argument("--shorts-only", action="store_true")
    a = ap.parse_args()

    d   = latest()
    ps  = json.loads((d / "manifest.json").read_text())
    desc = (d / "description.txt").read_text()
    svc  = yt_client()
    sheets = sheets_client()

    # Load row tracking info written by from_sheet.py
    rows_file = ROOT / "data" / ".current_rows.json"
    rows_info = json.loads(rows_file.read_text()) if rows_file.exists() else {}

    top = max(p["discount"] for p in ps)
    uploaded = 0

    # --- Long-form ---
    if not a.shorts_only and (d / "long.mp4").exists() and uploaded < a.max_long:
        title = (f"Top {len(ps)} Smartphones & Accessories on Amazon India "
                 f"| Up to {top}% Off | Best Deals 2026")[:100]
        all_tags = dedup(BASE_TAGS + [t for p in ps for t in product_tags(p)])
        print("Uploading long-form video...")
        push(svc, d / "long.mp4", title, desc, all_tags[:30], a.privacy)
        uploaded += 1

    # --- Shorts ---
    count = 0
    for i, p in enumerate(ps, 1):
        if count >= a.max_short:
            break
        f = d / f"short_{i:02d}.mp4"
        if not f.exists():
            continue
        st = (f"{p['brand']} {p['name']} - "
              f"₹{int(p['price'])} | {p['discount']}% Off | #shorts")[:100]
        sd = (
            f"{p['hook']}\n\n"
            f"✅ {p['name']}\n"
            f"💰 Price: ₹{int(p['price'])} (was ₹{int(p['mrp'])}, {p['discount']}% off)\n"
            f"🔗 {p['url']}\n\n"
            f"As an Amazon Associate I earn from qualifying purchases.\n"
            f"Prices correct at time of recording.\n\n"
            f"#shorts #amazonfinds #smartphoneaccessories #techdeals #india "
            f"#{p['brand'].lower().replace(' ','')} #mobilegadgets #amazonsale"
        )
        short_tags = dedup(BASE_TAGS[:10] + product_tags(p) + [
            "shorts", "youtube shorts", "tech shorts india",
            "amazon shorts", "mobile accessories shorts"
        ])
        print(f"Uploading Short {i}: {p['name'][:40]}...")
        push(svc, f, st, sd, short_tags[:30], a.privacy)
        count += 1

    # --- Mark rows done AFTER all uploads succeed ---
    mark_done(rows_info, sheets)
    print(f"\n✅ Upload complete. {uploaded} long + {count} Shorts published.")


if __name__ == "__main__":
    main()
