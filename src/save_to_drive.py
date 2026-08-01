#!/usr/bin/env python3
"""
Saves rendered video files to Google Drive after rendering.
Called once per batch slot (long_1, short_1, long_2, etc.)
Stores: video file + metadata JSON (title, description, tags, type)
"""
import argparse, json, os, sys
from pathlib import Path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT         = Path(__file__).resolve().parent.parent
DRIVE_FOLDER = os.environ["DRIVE_FOLDER_ID"]
GSHEET_TAB   = os.environ.get("GSHEET_TAB", "Sheet1")

def drive_client():
    creds = Credentials.from_service_account_info(
        json.loads(os.environ["GOOGLE_CREDS"]),
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)

def upload_file(svc, local_path: Path, name: str) -> str:
    media = MediaFileUpload(str(local_path), resumable=True)
    f = svc.files().create(
        body={"name": name, "parents": [DRIVE_FOLDER]},
        media_body=media, fields="id"
    ).execute()
    return f["id"]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", required=True,
                        help="long_1|short_1|long_2|short_2|long_3|short_3")
    args = parser.parse_args()
    slot = os.environ.get("BATCH_SLOT") or args.slot

    # Find latest output dir
    out_dirs = sorted(ROOT.glob("out/*/manifest.json"))
    if not out_dirs:
        sys.exit("No rendered output found")
    manifest_path = out_dirs[-1]
    d = manifest_path.parent
    manifest = json.loads(manifest_path.read_text())
    ps = manifest if isinstance(manifest, list) else manifest.get("products", manifest)

    # Import title generators
    sys.path.insert(0, str(ROOT / "src"))
    from titles import make_long_title, make_short_title

    svc = drive_client()
    slot_type = "long" if slot.startswith("long") else "short"

    uploaded = []

    if slot_type == "long":
        mp4 = d / "long.mp4"
        if not mp4.exists():
            sys.exit(f"long.mp4 not found in {d}")
        title    = make_long_title(ps).encode("ascii","ignore").decode("ascii").strip()
        desc     = (d / "description.txt").read_text().encode("ascii","ignore").decode("ascii")
        meta = {"slot": slot, "type": "long", "title": title,
                "description": desc, "privacy": "public"}
        # Upload video
        vid_id = upload_file(svc, mp4, f"{slot}_video.mp4")
        # Upload metadata
        meta_bytes = json.dumps(meta).encode()
        from googleapiclient.http import MediaInMemoryUpload
        svc.files().create(
            body={"name": f"{slot}_meta.json", "parents": [DRIVE_FOLDER]},
            media_body=MediaInMemoryUpload(meta_bytes, mimetype="application/json"),
            fields="id"
        ).execute()
        print(f"✓ Saved {slot} long video to Drive: {vid_id}")
        uploaded.append(slot)

    else:  # short
        shorts = sorted(d.glob("short_*.mp4"))
        if not shorts:
            sys.exit(f"No shorts found in {d}")
        mp4 = shorts[0]  # take first short
        p   = ps[0]      # first product
        title = make_short_title(p).encode("ascii","ignore").decode("ascii").strip()
        desc  = (f"{p.get('hook','')}\n\n{p.get('name','')}\n"
                 f"Price: Rs{int(p.get('price',0))}\n\n{p.get('url','')}\n\n"
                 f"As an Amazon Associate I earn from qualifying purchases.\n"
                 f"#shorts #amazonfinds #india")
        desc = desc.encode("ascii","ignore").decode("ascii")
        meta = {"slot": slot, "type": "short", "title": title,
                "description": desc, "privacy": "public"}
        vid_id = upload_file(svc, mp4, f"{slot}_video.mp4")
        meta_bytes = json.dumps(meta).encode()
        from googleapiclient.http import MediaInMemoryUpload
        svc.files().create(
            body={"name": f"{slot}_meta.json", "parents": [DRIVE_FOLDER]},
            media_body=MediaInMemoryUpload(meta_bytes, mimetype="application/json"),
            fields="id"
        ).execute()
        print(f"✓ Saved {slot} short to Drive: {vid_id}")
        uploaded.append(slot)

    print(f"Drive folder: https://drive.google.com/drive/folders/{DRIVE_FOLDER}")

if __name__ == "__main__":
    main()
