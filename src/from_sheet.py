#!/usr/bin/env python3
"""
Pulls the next unpublished batch from Google Sheet -> data/products.csv
Marks those rows as 'in_progress' while rendering.
After upload, upload.py marks them 'done'.
When ALL rows are 'done', automatically resets all to 'ready' (full cycle).

Sheet tab columns (row 1 = headers):
  asin | name | brand | mrp | price | category | hook |
  feature_1 | feature_2 | feature_3 | verdict | status

status lifecycle:
  ready / blank  → eligible to pick
  in_progress    → currently being rendered/uploaded
  done           → published, skip until full cycle resets
"""
import csv, json, os, sys
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

ROOT     = Path(__file__).resolve().parent.parent
SHEET_ID = os.environ.get("GSHEET_ID")
TAB      = os.environ.get("GSHEET_TAB", "Sheet1")
BATCH    = int(os.environ.get("BATCH_SIZE", "8"))
COLS     = ["asin","name","brand","mrp","price","category","hook",
            "feature_1","feature_2","feature_3","verdict"]


def svc():
    raw = os.environ.get("GOOGLE_CREDS")
    if not raw:
        sys.exit("GOOGLE_CREDS not set")
    creds = Credentials.from_service_account_info(
        json.loads(raw),
        scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return build("sheets", "v4", credentials=creds).spreadsheets()


def main():
    if not SHEET_ID:
        sys.exit("GSHEET_ID not set")

    s    = svc()
    vals = s.values().get(spreadsheetId=SHEET_ID,
                          range=f"{TAB}!A1:L1000").execute().get("values", [])
    if len(vals) < 2:
        sys.exit("Sheet is empty")

    hdr  = [h.strip() for h in vals[0]]
    missing = [c for c in COLS if c not in hdr]
    if missing:
        sys.exit(f"Sheet missing columns: {missing}")

    si   = hdr.index("status") if "status" in hdr else None
    col  = chr(ord("A") + si) if si is not None else None

    # --- Check if full cycle complete (all rows done) → reset to ready ---
    if si is not None:
        statuses = [
            (row + [""] * (len(hdr) - len(row)))[si].strip().lower()
            for row in vals[1:]
            if any(row)  # skip truly empty rows
        ]
        non_empty = [st for st in statuses if st != ""]
        if non_empty and all(st == "done" for st in non_empty):
            print("Full cycle complete — resetting all rows to ready.")
            reset_data = [
                {"range": f"{TAB}!{col}{n}", "values": [["ready"]]}
                for n, row in enumerate(vals[1:], start=2)
                if any(row)
            ]
            if reset_data:
                s.values().batchUpdate(
                    spreadsheetId=SHEET_ID,
                    body={"valueInputOption": "RAW", "data": reset_data}
                ).execute()
            # Re-fetch after reset
            vals = s.values().get(spreadsheetId=SHEET_ID,
                                  range=f"{TAB}!A1:L1000").execute().get("values", [])

    # --- Pick next BATCH rows with status ready/blank ---
    picked, rownums = [], []
    for n, row in enumerate(vals[1:], start=2):
        row = row + [""] * (len(hdr) - len(row))
        st  = (row[si].strip().lower() if si is not None else "")
        if st in ("", "ready"):
            rec = {c: row[hdr.index(c)].strip() for c in COLS}
            if not rec["asin"] or not rec["price"]:
                continue
            picked.append(rec)
            rownums.append(n)
        if len(picked) >= BATCH:
            break

    if not picked:
        sys.exit("No ready rows found. Check your Google Sheet.")

    # Write products.csv
    out = ROOT / "data" / "products.csv"
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(picked)
    print(f"Pulled {len(picked)} products → {out}")

    # Mark as in_progress + store row numbers for upload.py
    if si is not None:
        s.values().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={
                "valueInputOption": "RAW",
                "data": [{"range": f"{TAB}!{col}{r}", "values": [["in_progress"]]}
                         for r in rownums]
            }
        ).execute()
        print(f"Marked rows {rownums} → in_progress")

    # Save row numbers so upload.py can mark them done
    (ROOT / "data" / ".current_rows.json").write_text(
        json.dumps({"rows": rownums, "status_col": col, "tab": TAB})
    )


if __name__ == "__main__":
    main()
