# universeofsma-21 video pipeline

Zero-cost Amazon affiliate video pipeline. Spec-card format, no product photography.

## Flow
from_sheet.py -> build.py -> narrate.py -> render.py -> upload.py

## Local run
pip install pyyaml pillow edge-tts google-api-python-client google-auth-oauthlib
python3 src/build.py && python3 src/narrate.py
python3 src/render.py --format long
python3 src/render.py --format short

## GitHub secrets required
GSHEET_ID          sheet id from the URL
GOOGLE_CREDS       service-account JSON (one line)
YT_CLIENT_ID       from yt_auth.py
YT_CLIENT_SECRET   from yt_auth.py
YT_REFRESH_TOKEN   from yt_auth.py

## Google Sheet tab "products" headers (exact)
asin | name | brand | mrp | price | category | hook | feature_1 | feature_2 | feature_3 | verdict | status

## Notes
- Discount is COMPUTED from mrp vs price. Never hardcode a discount claim.
- Uploads default to private. Switch daily.yml to --privacy public once you have
  reviewed a few batches.
- Associate tag lives in config.yaml: universeofsma-21
