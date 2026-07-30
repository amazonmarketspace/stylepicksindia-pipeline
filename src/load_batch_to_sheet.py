#!/usr/bin/env python3
"""
One-time script: loads data/products_batch.csv into the Google Sheet.
Appends to existing rows (doesn't overwrite headers or existing data).
Run via GitHub Actions workflow_dispatch.
"""
import csv, json, os, sys
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

ROOT     = Path(__file__).resolve().parent.parent
SHEET_ID = os.environ.get("GSHEET_ID")
TAB      = os.environ.get("GSHEET_TAB", "Sheet1")
BATCH_FILE = ROOT / "data" / "products_batch.csv"

COLS = ["asin","name","brand","mrp","price","category","hook",
        "feature_1","feature_2","feature_3","verdict","status"]


def svc():
    creds = Credentials.from_service_account_info(
        json.loads(os.environ["GOOGLE_CREDS"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return build("sheets","v4",credentials=creds).spreadsheets()


def main():
    if not SHEET_ID:
        sys.exit("GSHEET_ID not set")
    if not BATCH_FILE.exists():
        sys.exit(f"Batch file not found: {BATCH_FILE}")

    # Read CSV
    with open(BATCH_FILE, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    print(f"Loaded {len(rows)} products from CSV")

    # Get current sheet to find first empty row
    s = svc()
    existing = s.values().get(
        spreadsheetId=SHEET_ID,
        range=f"{TAB}!A1:A10000"
    ).execute().get("values", [])

    first_empty = len(existing) + 1
    print(f"Sheet has {len(existing)} rows. Appending from row {first_empty}...")

    # If sheet is empty, write headers first
    if len(existing) == 0:
        s.values().update(
            spreadsheetId=SHEET_ID,
            range=f"{TAB}!A1:L1",
            valueInputOption="RAW",
            body={"values": [COLS]}
        ).execute()
        first_empty = 2

    # Write products in batches of 50
    values = [[str(r.get(c,"")) for c in COLS] for r in rows]
    batch_size = 50
    for i in range(0, len(values), batch_size):
        batch = values[i:i+batch_size]
        start_row = first_empty + i
        end_row   = start_row + len(batch) - 1
        s.values().update(
            spreadsheetId=SHEET_ID,
            range=f"{TAB}!A{start_row}:L{end_row}",
            valueInputOption="RAW",
            body={"values": batch}
        ).execute()
        print(f"  Wrote rows {start_row}–{end_row}")

    print(f"\n✅ Successfully loaded {len(rows)} products into sheet")


if __name__ == "__main__":
    main()
