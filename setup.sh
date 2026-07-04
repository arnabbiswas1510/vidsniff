#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "[vidsniff setup]"

# ── 1. Create virtual environment ────────────────────────────────────────────
echo ""
echo "[1/3] Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "      Created: $VENV_DIR"
else
    echo "      Already exists: $VENV_DIR"
fi

# Use the venv's pip and python from here on
PIP="$VENV_DIR/bin/pip"
PYTHON="$VENV_DIR/bin/python"

echo "      Installing vidsniff + yt-dlp..."
"$PIP" install -q -e "$SCRIPT_DIR"

# ── 2. Add venv bin to PATH permanently ──────────────────────────────────────
VENV_BIN="$VENV_DIR/bin"
PATH_LINE="export PATH=\"$VENV_BIN:\$PATH\"  # vidsniff"

# Detect shell config file
if [ -n "$ZSH_VERSION" ] || [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
elif [ -f "$HOME/.bash_profile" ]; then
    SHELL_RC="$HOME/.bash_profile"
else
    SHELL_RC="$HOME/.bashrc"
    touch "$SHELL_RC"
fi

if ! grep -q "vidsniff" "$SHELL_RC" 2>/dev/null; then
    echo "" >> "$SHELL_RC"
    echo "$PATH_LINE" >> "$SHELL_RC"
    echo "      Added $VENV_BIN to PATH in $SHELL_RC"
else
    echo "      PATH already configured in $SHELL_RC"
fi

# Also apply for the rest of this script session
export PATH="$VENV_BIN:$PATH"

# ── 3. Install aria2c ─────────────────────────────────────────────────────────
echo ""
echo "[2/3] Installing aria2c (fast multi-connection downloader)..."
if command -v aria2c &>/dev/null; then
    echo "      aria2c already installed."
else
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y aria2
    elif command -v brew &>/dev/null; then
        brew install aria2
    elif command -v yum &>/dev/null; then
        sudo yum install -y aria2
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm aria2
    else
        echo "      Could not auto-install aria2c."
        echo "      Ubuntu/Debian/WSL: sudo apt install aria2"
        echo "      macOS:             brew install aria2"
        echo "      vidsniff works without it, just slower."
    fi
fi

# ── 4. Verify ────────────────────────────────────────────────────────────────
echo ""
echo "[3/3] Verifying..."
if "$VENV_BIN/vidsniff" --help >/dev/null 2>&1; then
    echo "      vidsniff command: OK"
else
    echo "      [!] vidsniff command not found in venv — something went wrong."
fi

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo " Setup complete!"
echo "============================================================"
echo ""
echo " Open a new terminal (or: source $SHELL_RC), then:"
echo "   vidsniff \"https://youtube.com/watch?v=...\""
echo "   vidsniff \"https://youtu.be/...\" -x --audio-format ogg"
echo "   vidsniff \"https://bestjavporn.com/video/some-slug/\""
echo ""
