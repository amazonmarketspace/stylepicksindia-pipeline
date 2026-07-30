#!/bin/bash
# Run this ONCE on your GCP VM after cloning the repo
# Sets up the full pipeline environment

set -e
echo "=== Setting up universeofsma pipeline ==="

# System deps
sudo apt-get update -q
sudo apt-get install -y ffmpeg fonts-dejavu python3-pip git -q

# Python deps
pip3 install --break-system-packages \
  pyyaml pillow edge-tts \
  google-api-python-client google-auth-oauthlib \
  google-auth-httplib2

echo ""
echo "=== Done. Next steps ==="
echo ""
echo "1. Set your environment variables (add to ~/.bashrc):"
echo "   export GSHEET_ID='your-sheet-id-from-url'"
echo "   export YT_CLIENT_ID='from yt_auth.py'"
echo "   export YT_CLIENT_SECRET='from yt_auth.py'"
echo "   export YT_REFRESH_TOKEN='from yt_auth.py'"
echo ""
echo "2. Run YouTube auth ONCE on your Mac (not the VM):"
echo "   python3 src/yt_auth.py client_secret.json"
echo "   -> Copy the 3 values into GitHub Secrets + ~/.bashrc on VM"
echo ""
echo "3. Test full pipeline manually:"
echo "   python3 src/build.py"
echo "   python3 src/narrate.py"
echo "   python3 src/render.py --format long"
echo "   python3 src/render.py --format short"
echo "   python3 src/upload.py --privacy private"
echo ""
echo "4. Push to GitHub - Actions will run daily at 08:00 IST automatically"
