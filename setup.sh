#!/usr/bin/env bash
set -e
echo "[vidsniff setup]"
pip install -r requirements.txt
echo ""
echo "[OK] Setup complete!"
echo ""
echo "Usage:"
echo "  python vidsniff.py \"https://youtube.com/watch?v=...\""
echo "  python vidsniff.py \"https://site.com/video/slug/\" --domain site.com"
echo "  python vidsniff.py \"https://youtu.be/...\" -x --audio-format ogg"
