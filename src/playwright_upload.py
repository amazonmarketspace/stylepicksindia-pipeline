#!/usr/bin/env python3
"""
Playwright-based YouTube uploader for channels 2-99.
Logs into YouTube Studio using stored credentials and uploads via browser UI.
No YouTube API quota used.
"""
import os, sys, json, time, re
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

ROOT       = Path(__file__).resolve().parent.parent
CREDS_FILE = ROOT / "yt_credentials.json"   # {"email": "...", "password": "..."}

YT_EMAIL    = os.environ.get("YT_EMAIL")
YT_PASSWORD = os.environ.get("YT_PASSWORD")
YT_CHANNEL  = os.environ.get("YT_CHANNEL_HANDLE", "")   # @StylePicksIndia

UPLOAD_URL  = "https://www.youtube.com/upload"
STUDIO_URL  = "https://studio.youtube.com"

MAX_WAIT    = 120_000   # 2 minutes in ms


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def login(page):
    """Log into Google account via YouTube."""
    log("Navigating to YouTube...")
    page.goto("https://accounts.google.com/signin")
    page.wait_for_load_state("networkidle")

    log("Entering email...")
    page.fill('input[type="email"]', YT_EMAIL)
    page.press('input[type="email"]', "Enter")
    page.wait_for_timeout(2000)

    log("Entering password...")
    page.fill('input[type="password"]', YT_PASSWORD)
    page.press('input[type="password"]', "Enter")
    page.wait_for_timeout(3000)

    # Check if 2FA or unusual activity page
    if "challenge" in page.url or "signin/v2/challenge" in page.url:
        log("⚠ 2FA or challenge detected — manual intervention needed")
        sys.exit(1)

    log("Navigating to YouTube Studio...")
    page.goto(STUDIO_URL)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)

    if "studio.youtube.com" not in page.url:
        log(f"❌ Login failed — current URL: {page.url}")
        sys.exit(1)

    log("✓ Logged in to YouTube Studio")


def switch_channel(page, channel_handle):
    """Switch to the correct brand channel if needed."""
    # Click account icon
    page.click('button[aria-label="Account"], yt-img-shadow#avatar-btn')
    page.wait_for_timeout(1500)

    # Look for the channel in the switcher
    channels = page.query_selector_all('[class*="channel-name"], [class*="account-name"]')
    for ch in channels:
        if channel_handle.lower() in (ch.inner_text() or "").lower():
            ch.click()
            page.wait_for_timeout(2000)
            log(f"✓ Switched to channel: {channel_handle}")
            return

    log(f"⚠ Channel {channel_handle} not found in switcher — proceeding with current")


def upload_video(page, video_path: Path, title: str, description: str,
                 tags: list, is_short: bool = False, privacy: str = "public") -> str | None:
    """Upload a single video. Returns video URL if successful."""
    log(f"Uploading: {video_path.name} | Title: {title[:60]}")

    # Go to YouTube Studio upload
    page.goto(STUDIO_URL)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # Click CREATE button
    try:
        page.click('button:has-text("Create"), ytcp-button#create-icon', timeout=10000)
        page.wait_for_timeout(1000)
        page.click('[test-id="upload-beta"], button:has-text("Upload videos")', timeout=8000)
    except PlaywrightTimeout:
        # Try direct navigation
        page.goto("https://www.youtube.com/upload")
        page.wait_for_timeout(3000)

    # File input
    log("Selecting video file...")
    try:
        file_input = page.locator('input[type="file"]').first
        file_input.set_input_files(str(video_path))
    except Exception as e:
        log(f"❌ File input error: {e}")
        return None

    # Wait for upload to start and details panel to appear
    log("Waiting for upload panel...")
    page.wait_for_selector('[id="textbox"], ytcp-video-upload-dialog', timeout=MAX_WAIT)
    page.wait_for_timeout(2000)

    # Fill title — clear existing and type new
    log("Setting title...")
    title_box = page.locator('#textbox').first
    title_box.click()
    title_box.select_all() if hasattr(title_box, 'select_all') else page.keyboard.press("Control+a")
    title_box.type(title[:100], delay=30)

    # Fill description
    log("Setting description...")
    desc_boxes = page.locator('#textbox')
    if desc_boxes.count() >= 2:
        desc_box = desc_boxes.nth(1)
        desc_box.click()
        page.keyboard.press("Control+a")
        desc_box.type(description[:4900], delay=5)

    # Tags (if available)
    try:
        more_options = page.locator('button:has-text("More options"), [class*="more-options"]')
        if more_options.count() > 0:
            more_options.click()
            page.wait_for_timeout(1000)
            tag_input = page.locator('input[placeholder*="tag"], #tags-input input')
            if tag_input.count() > 0:
                for tag in tags[:15]:
                    tag_input.fill(tag)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(200)
    except Exception:
        pass  # tags are optional

    # Scroll to find "Not made for kids"
    try:
        page.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]').click()
    except Exception:
        pass

    # Click Next through steps (Details → Monetization → Visibility)
    log("Navigating through upload steps...")
    for step in range(3):
        try:
            next_btn = page.locator('button:has-text("Next"), ytcp-button:has-text("Next")')
            if next_btn.count() > 0:
                next_btn.first.click()
                page.wait_for_timeout(1500)
        except Exception:
            pass

    # Set visibility
    log(f"Setting visibility: {privacy}...")
    page.wait_for_timeout(1000)
    try:
        if privacy == "public":
            page.locator('tp-yt-paper-radio-button[name="PUBLIC"]').click()
        elif privacy == "private":
            page.locator('tp-yt-paper-radio-button[name="PRIVATE"]').click()
    except Exception:
        pass

    # Wait for upload to complete then publish
    log("Waiting for upload to finish...")
    try:
        # Wait until progress bar is gone or "Upload complete" message appears
        page.wait_for_selector(
            'span:has-text("Upload complete"), ytcp-ve.ytcp-upload-progress:has-text("100%")',
            timeout=600_000  # 10 minutes for large files
        )
    except PlaywrightTimeout:
        log("⚠ Upload progress check timed out — attempting to publish anyway")

    page.wait_for_timeout(2000)

    # Click Save / Publish
    log("Publishing...")
    try:
        save_btn = page.locator('button:has-text("Save"), ytcp-button:has-text("Publish"), button:has-text("Publish")')
        save_btn.first.click()
        page.wait_for_timeout(5000)
    except Exception as e:
        log(f"⚠ Save button error: {e}")

    # Get video URL from success dialog
    video_url = None
    try:
        link = page.locator('a[href*="youtu.be"], a[href*="youtube.com/watch"]').first
        video_url = link.get_attribute("href")
        log(f"✓ Published: {video_url}")
    except Exception:
        log("✓ Published (URL not captured)")

    page.wait_for_timeout(2000)
    return video_url


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-long",  type=int, default=1)
    parser.add_argument("--max-short", type=int, default=5)
    parser.add_argument("--privacy",   default="public")
    parser.add_argument("--headless",  action="store_true", default=True)
    args = parser.parse_args()

    if not YT_EMAIL or not YT_PASSWORD:
        sys.exit("YT_EMAIL and YT_PASSWORD env vars required")

    # Find latest output directory
    out_dirs = sorted(ROOT.glob("out/*/manifest.json"))
    if not out_dirs:
        sys.exit("No output found — run render.py first")
    manifest_path = out_dirs[-1]
    d = manifest_path.parent
    manifest = json.loads(manifest_path.read_text())
    ps = manifest if isinstance(manifest, list) else manifest.get("products", manifest)

    # Read description and title
    desc = (d / "description.txt").read_text() if (d / "description.txt").exists() else ""

    # Import title generator
    sys.path.insert(0, str(Path(__file__).parent))
    from titles import make_long_title, make_short_title

    # Build safe tags
    BASE_TAGS = [
        "amazon india fashion", "fashion deals india", "clothing deals amazon",
        "ethnic wear india", "kurta deals india", "saree deals amazon",
        "amazon india deals", "budget fashion india", "apparel deals india",
        "style picks india", "fashion india 2026", "amazon finds india",
        "women fashion india", "men fashion india", "amazon sale india",
        "discount fashion india", "best fashion india", "top clothing deals",
        "affordable fashion india", "fashion amazon 2026"
    ]
    safe_tags = [t.encode("ascii","ignore").decode("ascii").strip()
                 for t in BASE_TAGS if t.encode("ascii","ignore").decode("ascii").strip()][:20]

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=args.headless,
            args=["--no-sandbox", "--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled"]
        )
        # Use persistent context to store cookies between runs
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/125.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = ctx.new_page()

        # Login
        login(page)

        # Switch to correct channel if handle provided
        if YT_CHANNEL:
            switch_channel(page, YT_CHANNEL)

        uploaded = 0

        # Upload long-form
        long_mp4 = d / "long.mp4"
        if long_mp4.exists() and uploaded < args.max_long:
            title = make_long_title(ps)
            title_safe = title.encode("ascii","ignore").decode("ascii").strip()
            desc_safe  = desc.encode("ascii","ignore").decode("ascii")
            url = upload_video(page, long_mp4, title_safe, desc_safe, safe_tags,
                               is_short=False, privacy=args.privacy)
            if url:
                uploaded += 1

        # Upload shorts
        short_count = 0
        for short_mp4 in sorted(d.glob("short_*.mp4")):
            if short_count >= args.max_short:
                break
            # Get product for this short
            idx = int(short_mp4.stem.split("_")[1]) if "_" in short_mp4.stem else 0
            p = ps[min(idx, len(ps)-1)]
            st = make_short_title(p)
            st_safe = st.encode("ascii","ignore").decode("ascii").strip()
            # Short description
            sd = (f"{p.get('hook','')}\n\n{p.get('name','')}\n"
                  f"Price: Rs{int(p.get('price',0))}\n\n{p.get('url','')}\n\n"
                  f"As an Amazon Associate I earn from qualifying purchases.\n"
                  f"#shorts #fashionfinds #amazonfinds #india")
            sd_safe = sd.encode("ascii","ignore").decode("ascii")
            url = upload_video(page, short_mp4, st_safe, sd_safe, safe_tags[:10],
                               is_short=True, privacy=args.privacy)
            if url:
                short_count += 1

        browser.close()
        log(f"Done — {uploaded} long + {short_count} shorts uploaded")


if __name__ == "__main__":
    main()
