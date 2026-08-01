#!/usr/bin/env python3
"""
Uploads rendered videos to YouTube and marks sheet rows as 'done'.
Default privacy: public
Daily quota: 1 long + 5 Shorts (6 videos x 1,600 units = 9,600 / 10,000 limit)
"""
import argparse, json, os, sys, random
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials as SACredentials
sys.path.insert(0, str(Path(__file__).parent))
from titles import make_long_title, make_short_title

ROOT       = Path(__file__).resolve().parent.parent
TOKEN_URI  = "https://oauth2.googleapis.com/token"
sys.path.insert(0, str(Path(__file__).parent))
from titles import make_long_title, make_short_title
BASE_TAGS = [
    "best fashion deals india 2026",
    "amazon india fashion",
    "clothing deals amazon india",
    "ethnic wear india",
    "kurta deals india",
    "saree deals amazon",
    "women fashion india",
    "men fashion india",
    "amazon india deals",
    "budget fashion india",
    "apparel deals india",
    "amazon finds india",
    "amazon sale india",
    "best deals amazon india",
    "style picks india",
    "affordable fashion india",
    "fashion india 2026",
    "amazon fashion sale",
    "ethnic clothing india",
    "best clothing india",
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
    print(f"Marked rows {rownums} -> done")


def product_tags(p: dict) -> list:
    INVALID = set('/\\\\,|<>&"\';:()[]{}@#%^*+=~`')
    STOP = {'for','the','and','with','this','that','from','into','over','your',
            'our','its','are','was','has','had','have','been','will','can',
            'not','but','all','one','new','get','use','may','per','off',
            'more','also','only','same','just','like','some','than','then',
            'when','what','which','who','how','why','where','each','both',
            'buy','best','deal','free','shop','save','sale','fast','good'}

    def clean(word: str) -> str | None:
        w = word.strip().lower()
        if not w or len(w) < 4:
            return None
        if w in STOP:
            return None
        if any(c in INVALID for c in w):
            return None
        if any(ord(c) > 127 for c in w):
            return None
        if w.replace('.', '').replace('m', '').replace('ft', '').isdigit():
            return None
        if len(w) <= 5 and any(c.isdigit() for c in w):
            return None
        return w

    tags = []
    brand = clean(p.get("brand", ""))
    if brand:
        tags.append(brand)
    name_words = p.get("name", "").lower().replace("-", " ").replace("/", " ").split()
    clean_words = [c for w in name_words if (c := clean(w))]
    tags.extend(clean_words[:4])
    cat = clean(p.get("category", ""))
    if cat:
        tags.append(cat)
    if p.get("discount", 0) >= 50:
        tags.append(f"{p['discount']}% off amazon")
    try:
        tags.append(f"rs {int(p.get('price', 0))} india")
    except (ValueError, TypeError):
        pass
    return [t for t in tags if t]


def dedup(tags):
    seen, out = set(), []
    for t in tags:
        t = t.strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def sanitise_tags(tags: list) -> list:
    """Strip tags with non-ASCII chars, commas, or angle brackets.
    YouTube allows only ASCII letters, numbers, spaces and hyphens in tags.
    Also enforces 500-char total limit."""
    clean = []
    total = 0
    for t in tags:
        t = t.strip()
        # Skip if any non-ASCII character
        if any(ord(c) > 127 for c in t):
            continue
        # Skip if contains chars YouTube rejects in tags
        if any(c in t for c in ('<', '>', '&', '"', "'")):
            continue
        if not t:
            continue
        if total + len(t) > 495:
            break
        clean.append(t)
        total += len(t)
    return clean


def push(svc, path: Path, title: str, desc: str, tags: list, privacy: str):
    # Build safe tags - strict ASCII only, no special chars
    raw_tags = sanitise_tags(tags)
    # Extra safety: re-encode through ASCII to strip any invisible characters
    safe_tags = []
    for t in raw_tags[:25]:  # max 25 to stay well under 30 limit
        cleaned = t.encode('ascii', 'ignore').decode('ascii').strip()
        if cleaned and len(cleaned) >= 3:
            safe_tags.append(cleaned)
    # Sanitise description - remove any chars that YouTube might reject
    safe_desc = desc[:4900].encode('ascii', 'ignore').decode('ascii')
    safe_title = title[:100].encode('ascii', 'ignore').decode('ascii').strip()
    body = {
        "snippet": {
            "title": safe_title,
            "description": safe_desc,
            "tags": safe_tags,
            "categoryId": "28",
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
    try:
        res = None
        while res is None:
            _, res = req.next_chunk()
    except Exception as e:
        err_str = str(e)
        if 'uploadLimitExceeded' in err_str:
            print(f"  ⚠ YouTube daily upload limit reached - will retry tomorrow at 8am IST")
            sys.exit(0)  # exit cleanly so rows aren't marked done but pipeline doesn't fail
        raise
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
        title = make_long_title(ps)
        # Use only BASE_TAGS - dynamic product tags cause invalidTags 400 errors
        safe_base_tags = [t.encode('ascii','ignore').decode('ascii').strip()
                          for t in BASE_TAGS if t.encode('ascii','ignore').decode('ascii').strip()]
        print("Uploading long-form video...")
        push(svc, d / "long.mp4", title, desc, safe_base_tags[:20], a.privacy)
        uploaded += 1

    # --- Shorts ---
    count = 0
    for i, p in enumerate(ps, 1):
        if count >= a.max_short:
            break
        f = d / f"short_{i:02d}.mp4"
        if not f.exists():
            continue
        st = make_short_title(p)
        sd = (
            f"{p['hook']}\n\n"
            f"{p['name']}\n"
            f"Price: Rs{int(p['price'])} (was Rs{int(p['mrp'])}, {p['discount']}% off)\n"
            f"Link: {p['url']}\n\n"
            f"As an Amazon Associate I earn from qualifying purchases.\n"
            f"Prices correct at time of recording.\n\n"
            f"#shorts #amazonfinds #smartphoneaccessories #techdeals #india "
            f"#{p['brand'].lower().replace(' ','')} #mobilegadgets #amazonsale"
        )
        short_tags = [t.encode('ascii','ignore').decode('ascii').strip()
                      for t in BASE_TAGS[:15] + ["shorts", "youtube shorts", "tech shorts india"]
                      if t.encode('ascii','ignore').decode('ascii').strip()]
        print(f"Uploading Short {i}: {p['name'][:40]}...")
        push(svc, f, st, sd, short_tags[:30], a.privacy)
        count += 1

    # --- Mark rows done AFTER all uploads succeed ---
    mark_done(rows_info, sheets)
    print(f"\nOK Upload complete. {uploaded} long + {count} Shorts published.")


if __name__ == "__main__":
    main()
