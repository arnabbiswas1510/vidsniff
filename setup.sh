#!/usr/bin/env bash
set -e

echo "[vidsniff setup]"

echo ""
echo "[1/3] Installing Python dependencies + vidsniff command..."
pip install -e .

# Add pip user bin to PATH permanently in the appropriate shell config
# On Linux/WSL/Mac, pip installs scripts to ~/.local/bin by default
USER_BIN="$HOME/.local/bin"

# Detect which shell config file to update
if [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
elif [ -f "$HOME/.bash_profile" ]; then
    SHELL_RC="$HOME/.bash_profile"
else
    SHELL_RC="$HOME/.bashrc"
fi

if ! grep -q "$USER_BIN" "$SHELL_RC" 2>/dev/null; then
    echo "" >> "$SHELL_RC"
    echo "# Added by vidsniff setup" >> "$SHELL_RC"
    echo "export PATH=\"$USER_BIN:\$PATH\"" >> "$SHELL_RC"
    echo "[OK] Added $USER_BIN to PATH in $SHELL_RC"
    # Also apply for the rest of this script session
    export PATH="$USER_BIN:$PATH"
else
    echo "[OK] $USER_BIN already in $SHELL_RC"
fi

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
echo "============================================================"
echo " Setup complete!"
echo "============================================================"
echo ""
echo " Open a new terminal (or run: source $SHELL_RC), then:"
echo "   vidsniff \"https://youtube.com/watch?v=...\""
echo "   vidsniff \"https://youtu.be/...\" -x --audio-format ogg"
echo "   vidsniff \"https://bestjavporn.com/video/some-slug/\""
echo ""
