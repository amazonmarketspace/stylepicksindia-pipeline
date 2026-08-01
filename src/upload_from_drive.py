#!/usr/bin/env python3
"""
Downloads a video from Google Drive by slot name, uploads to YouTube,
then deletes it from Drive. Triggered at exact IST times by cron-job.org.
"""
import json, os, sys, tempfile
from pathlib import Path
from google.oauth2.service_account import Credentials
from google.oauth2.credentials import Credentials as OAuthCreds
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io

ROOT         = Path(__file__).resolve().parent.parent
DRIVE_FOLDER = os.environ["DRIVE_FOLDER_ID"]
SLOT         = os.environ["UPLOAD_SLOT"]   # e.g. long_1, short_2
TOKEN_URI    = "https://oauth2.googleapis.com/token"

def drive_client():
    creds = Credentials.from_service_account_info(
        json.loads(os.environ["GOOGLE_CREDS"]),
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)

def yt_client():
    creds = OAuthCreds(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri=TOKEN_URI,
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )
    return build("youtube", "v3", credentials=creds)

def find_slot_files(svc, slot):
    """Find video and metadata files for this slot in Drive folder."""
    q = f"'{DRIVE_FOLDER}' in parents and trashed=false"
    files = svc.files().list(q=q, fields="files(id,name)").execute().get("files", [])
    vid_id  = next((f["id"] for f in files if f["name"] == f"{slot}_video.mp4"), None)
    meta_id = next((f["id"] for f in files if f["name"] == f"{slot}_meta.json"), None)
    return vid_id, meta_id

def download_file(svc, file_id, dest_path):
    req = svc.files().get_media(fileId=file_id)
    with open(dest_path, "wb") as fh:
        dl = MediaIoBaseDownload(fh, req)
        done = False
        while not done:
            _, done = dl.next_chunk()

def delete_file(svc, file_id):
    svc.files().delete(fileId=file_id).execute()

def upload_to_youtube(yt_svc, video_path, meta):
    title    = meta["title"][:100]
    desc     = meta["description"][:4900]
    privacy  = meta.get("privacy", "public")

    BASE_TAGS = [
        "amazon india deals", "amazon finds india", "amazon sale india",
        "best deals amazon india", "budget deals india", "amazon india 2026",
        "amazon shopping india", "best amazon products india",
        "amazon discount india", "amazon offers india",
    ]
    safe_tags = [t.encode("ascii","ignore").decode("ascii").strip() for t in BASE_TAGS][:15]

    body = {
        "snippet": {
            "title":       title.encode("ascii","ignore").decode("ascii").strip(),
            "description": desc.encode("ascii","ignore").decode("ascii"),
            "tags":        safe_tags,
            "categoryId":  "28",
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    req   = yt_svc.videos().insert(part="snippet,status", body=body, media_body=media)
    res   = None
    while res is None:
        _, res = req.next_chunk()
    return f"https://www.youtube.com/watch?v={res['id']}"

def main():
    print(f"Uploading slot: {SLOT}")

    drive = drive_client()
    yt    = yt_client()

    vid_id, meta_id = find_slot_files(drive, SLOT)
    if not vid_id:
        print(f"⚠ No video found for slot {SLOT} in Drive — skipping")
        print("(Render workflow may not have run yet)")
        sys.exit(0)

    # Download metadata
    meta = {}
    if meta_id:
        buf = io.BytesIO()
        req = drive.files().get_media(fileId=meta_id)
        dl = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _, done = dl.next_chunk()
        meta = json.loads(buf.getvalue())
        print(f"Title: {meta.get('title','')[:60]}")

    # Download video to temp file
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = tmp.name
    print(f"Downloading video from Drive...")
    download_file(drive, vid_id, tmp_path)
    size_mb = Path(tmp_path).stat().st_size / 1024 / 1024
    print(f"Downloaded {size_mb:.1f} MB")

    # Upload to YouTube
    print("Uploading to YouTube...")
    url = upload_to_youtube(yt, tmp_path, meta)
    print(f"✓ Published: {url}")

    # Delete from Drive (video + metadata)
    print("Deleting from Drive...")
    delete_file(drive, vid_id)
    if meta_id:
        delete_file(drive, meta_id)
    print(f"✓ Deleted slot {SLOT} from Drive")

    # Cleanup temp file
    Path(tmp_path).unlink(missing_ok=True)
    print(f"✓ Done — {SLOT} uploaded and Drive cleaned")

if __name__ == "__main__":
    main()
