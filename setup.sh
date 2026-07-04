#!/usr/bin/env bash
set -e

echo "[vidsniff setup]"

echo ""
echo "[1/3] Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "[2/3] Installing aria2c (fast multi-connection downloader)..."
if command -v aria2c &>/dev/null; then
    echo "aria2c already installed."
else
    if command -v apt-get &>/dev/null; then
        echo "Detected apt — installing aria2..."
        sudo apt-get install -y aria2
    elif command -v brew &>/dev/null; then
        echo "Detected Homebrew — installing aria2..."
        brew install aria2
    elif command -v yum &>/dev/null; then
        echo "Detected yum — installing aria2..."
        sudo yum install -y aria2
    elif command -v pacman &>/dev/null; then
        echo "Detected pacman — installing aria2..."
        sudo pacman -S --noconfirm aria2
    else
        echo "Could not auto-install aria2c. Install manually:"
        echo "  Ubuntu/Debian/WSL: sudo apt install aria2"
        echo "  macOS:             brew install aria2"
        echo ""
        echo "vidsniff will still work without aria2c, just slower."
    fi
fi

echo ""
echo "[3/3] Registering 'vidsniff' command on PATH..."
pip install -e .

echo ""
echo "[OK] Setup complete!"
echo ""
echo "Usage:"
echo "  vidsniff \"https://youtube.com/watch?v=...\""
echo "  vidsniff \"https://youtu.be/...\" -x --audio-format ogg"
echo "  vidsniff \"https://bestjavporn.com/video/some-slug/\""
