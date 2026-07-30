#!/usr/bin/env python3
"""
Run ONCE on your own machine to mint a YouTube refresh token.
  pip install google-auth-oauthlib
  python3 src/yt_auth.py client_secret.json
Prints the refresh token -> paste into GitHub secret YT_REFRESH_TOKEN.
"""
import sys
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

if len(sys.argv) < 2:
    sys.exit("usage: yt_auth.py <client_secret.json>")

flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
creds = flow.run_local_server(port=8080, prompt="consent", access_type="offline")
print("\nYT_CLIENT_ID     =", flow.client_config["client_id"])
print("YT_CLIENT_SECRET =", flow.client_config["client_secret"])
print("YT_REFRESH_TOKEN =", creds.refresh_token)
