#!/usr/bin/env python3
"""Reset all in_progress rows back to ready in the Google Sheet."""
import os, json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SHEET_ID = os.environ.get("GSHEET_ID")
TAB = os.environ.get("GSHEET_TAB", "Sheet1")
info = json.loads(os.environ.get("GOOGLE_CREDS"))
creds = Credentials.from_service_account_info(
    info, scopes=["https://www.googleapis.com/auth/spreadsheets"])
svc = build("sheets", "v4", credentials=creds).spreadsheets()

vals = svc.values().get(spreadsheetId=SHEET_ID, range=f"{TAB}!A1:L1000").execute().get("values", [])
if not vals:
    print("Sheet empty"); exit(1)

hdr = vals[0]
si = hdr.index("status") if "status" in hdr else None
if si is None:
    print("No status column"); exit(1)

col = chr(ord("A") + si)
updates = []
for n, row in enumerate(vals[1:], start=2):
    row = row + [""] * (len(hdr) - len(row))
    st = row[si].strip().lower()
    if st == "in_progress":
        updates.append({"range": f"{TAB}!{col}{n}", "values": [["ready"]]})
        print(f"  Row {n}: in_progress → ready")

if updates:
    svc.values().batchUpdate(spreadsheetId=SHEET_ID, body={
        "valueInputOption": "RAW", "data": updates}).execute()
    print(f"Reset {len(updates)} rows")
else:
    print("No rows to reset - all already ready")
