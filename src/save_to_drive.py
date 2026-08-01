#!/usr/bin/env python3
"""
Saves rendered video + metadata to Google Drive after rendering.
Uses Drive OAuth refresh token for authentication.
"""
import argparse, json, os, sys
from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaInMemoryUpload

ROOT         = Path(__file__).resolve().parent.parent
DRIVE_FOLDER = os.environ["DRIVE_FOLDER_ID"]
TOKEN_URI    = "https://oauth2.googleapis.com/token"


def drive_client():
    creds = Credentials(
        None,
        refresh_token=os.environ["DRIVE_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri=TOKEN_URI,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)


def upload_file(svc, local_path: Path, name: str) -> str:
    # Delete existing file with same name first
    existing = svc.files().list(
        q=f"name=\'{name}\' and \'{DRIVE_FOLDER}\' in parents and trashed=false",
        fields="files(id)"
    ).execute().get("files", [])
    for f in existing:
        svc.files().delete(fileId=f["id"]).execute()

    media = MediaFileUpload(str(local_path), resumable=True)
    f = svc.files().create(
        body={"name": name, "parents": [DRIVE_FOLDER]},
        media_body=media, fields="id"
    ).execute()
    return f["id"]


def upload_meta(svc, meta: dict, name: str):
    # Delete existing metadata file
    existing = svc.files().list(
        q=f"name=\'{name}\' and \'{DRIVE_FOLDER}\' in parents and trashed=false",
        fields="files(id)"
    ).execute().get("files", [])
    for f in existing:
        svc.files().delete(fileId=f["id"]).execute()

    data = json.dumps(meta).encode()
    svc.files().create(
        body={"name": name, "parents": [DRIVE_FOLDER]},
        media_body=MediaInMemoryUpload(data, mimetype="application/json"),
        fields="id"
    ).execute()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", default=None)
    args = parser.parse_args()
    slot = os.environ.get("BATCH_SLOT") or args.slot
    if not slot:
        sys.exit("BATCH_SLOT env var or --slot argument required")

    # Find latest output dir
    out_dirs = sorted(ROOT.glob("out/*/manifest.json"))
    if not out_dirs:
        sys.exit("No rendered output found - run render.py first")
    d = out_dirs[-1].parent
    manifest = json.loads(out_dirs[-1].read_text())
    ps = manifest if isinstance(manifest, list) else manifest.get("products", [])

    sys.path.insert(0, str(ROOT / "src"))
    from titles import make_long_title, make_short_title

    svc = drive_client()
    is_long = slot.startswith("long")

    if is_long:
        mp4 = d / "long.mp4"
        if not mp4.exists():
            sys.exit(f"long.mp4 not found in {d}")
        title = make_long_title(ps).encode("ascii","ignore").decode("ascii").strip()
        desc  = (d / "description.txt").read_text().encode("ascii","ignore").decode("ascii") if (d/"description.txt").exists() else ""
        meta  = {"slot": slot, "type": "long", "title": title,
                 "description": desc, "privacy": "public"}
        vid_id = upload_file(svc, mp4, f"{slot}_video.mp4")
        upload_meta(svc, meta, f"{slot}_meta.json")
        size_mb = mp4.stat().st_size / 1024 / 1024
        print(f"✓ {slot}: {size_mb:.1f}MB long video saved to Drive ({vid_id})")
    else:
        shorts = sorted(d.glob("short_*.mp4"))
        if not shorts:
            sys.exit(f"No shorts found in {d}")
        mp4 = shorts[0]
        p   = ps[0] if ps else {}
        title = make_short_title(p).encode("ascii","ignore").decode("ascii").strip() if p else f"{slot} short"
        desc  = (f"{p.get('hook','')}\n\n{p.get('name','')}\nPrice: Rs{int(p.get('price',0))}\n\n{p.get('url','')}\n\n"
                 f"As an Amazon Associate I earn from qualifying purchases.\n#shorts #amazonfinds #india")
        desc  = desc.encode("ascii","ignore").decode("ascii")
        meta  = {"slot": slot, "type": "short", "title": title,
                 "description": desc, "privacy": "public"}
        vid_id = upload_file(svc, mp4, f"{slot}_video.mp4")
        upload_meta(svc, meta, f"{slot}_meta.json")
        size_mb = mp4.stat().st_size / 1024 / 1024
        print(f"✓ {slot}: {size_mb:.1f}MB short saved to Drive ({vid_id})")

    print(f"Drive: https://drive.google.com/drive/folders/{DRIVE_FOLDER}")


if __name__ == "__main__":
    main()
