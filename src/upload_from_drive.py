#!/usr/bin/env python3
"""
Downloads video from Google Drive by slot, uploads to YouTube, deletes from Drive.
Triggered at exact IST times by cron-job.org via workflow_dispatch.
"""
import json, os, sys, tempfile, io
from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

ROOT         = Path(__file__).resolve().parent.parent
DRIVE_FOLDER = os.environ["DRIVE_FOLDER_ID"]
SLOT         = os.environ["UPLOAD_SLOT"]
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


def yt_client():
    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri=TOKEN_URI,
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )
    return build("youtube", "v3", credentials=creds)


def find_slot_files(svc, slot):
    q = f"\'{DRIVE_FOLDER}\' in parents and trashed=false"
    files = svc.files().list(q=q, fields="files(id,name)").execute().get("files", [])
    vid  = next((f["id"] for f in files if f["name"] == f"{slot}_video.mp4"), None)
    meta = next((f["id"] for f in files if f["name"] == f"{slot}_meta.json"), None)
    return vid, meta


def download_to_temp(svc, file_id, suffix=".mp4"):
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    req = svc.files().get_media(fileId=file_id)
    dl  = MediaIoBaseDownload(tmp, req)
    done = False
    while not done:
        _, done = dl.next_chunk()
    tmp.close()
    return tmp.name


def upload_to_youtube(yt_svc, video_path, meta):
    BASE_TAGS = [
        "amazon india deals", "amazon finds india", "best deals amazon india",
        "amazon sale india", "budget deals india", "amazon india 2026",
        "amazon shopping india", "amazon offers india", "amazon discount india",
        "best amazon india",
    ]
    safe_tags = [t.encode("ascii","ignore").decode("ascii") for t in BASE_TAGS][:10]
    body = {
        "snippet": {
            "title":       meta["title"][:100].encode("ascii","ignore").decode("ascii").strip(),
            "description": meta["description"][:4900].encode("ascii","ignore").decode("ascii"),
            "tags":        safe_tags,
            "categoryId":  "28",
        },
        "status": {"privacyStatus": meta.get("privacy","public"),
                   "selfDeclaredMadeForKids": False}
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    req   = yt_svc.videos().insert(part="snippet,status", body=body, media_body=media)
    res   = None
    while res is None:
        _, res = req.next_chunk()
    vid_id = res["id"]
    vid_type = "Short" if meta.get("type") == "short" else "Video"
    print(f"✓ {vid_type} published: https://www.youtube.com/watch?v={vid_id}")
    return vid_id


def main():
    print(f"[Upload] Slot: {SLOT}")
    drive = drive_client()
    yt    = yt_client()

    vid_id, meta_id = find_slot_files(drive, SLOT)
    if not vid_id:
        print(f"⚠ No video found for slot {SLOT} — render workflow may not have run yet")
        sys.exit(0)  # exit cleanly

    # Download metadata
    meta = {"title": f"Amazon India Deals - {SLOT}", "type": "long",
            "description": "Amazon India deals.", "privacy": "public"}
    if meta_id:
        buf = io.BytesIO()
        dl  = MediaIoBaseDownload(buf, drive.files().get_media(fileId=meta_id))
        done = False
        while not done:
            _, done = dl.next_chunk()
        meta = json.loads(buf.getvalue())
    print(f"Title: {meta.get('title','')[:60]}")

    # Download video
    print("Downloading from Drive...")
    tmp_path = download_to_temp(drive, vid_id, ".mp4")
    size_mb  = Path(tmp_path).stat().st_size / 1024 / 1024
    print(f"Downloaded: {size_mb:.1f} MB")

    # Upload to YouTube
    print("Uploading to YouTube...")
    upload_to_youtube(yt, tmp_path, meta)

    # Delete from Drive
    drive.files().delete(fileId=vid_id).execute()
    if meta_id:
        drive.files().delete(fileId=meta_id).execute()
    print(f"✓ Slot {SLOT} deleted from Drive")

    Path(tmp_path).unlink(missing_ok=True)
    print("Done.")


if __name__ == "__main__":
    main()
