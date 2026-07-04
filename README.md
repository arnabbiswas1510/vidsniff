# VidSniff

**Smart universal video downloader** — a `yt-dlp` wrapper that adds browser-interception for sites that yt-dlp cannot handle natively (Cloudflare-protected players, obfuscated streams, etc.).

## How it works

1. **For yt-dlp-supported sites** (YouTube, Vimeo, Twitter, etc.) → passes the URL directly to yt-dlp with all your options
2. **For other sites** → launches Chrome with a bundled extension pre-loaded, captures the video stream URL as the browser fetches it, then downloads it

No manual Chrome extension installation needed. No CDP/automation detection.

---

## Requirements

- Python 3.9+
- Google Chrome (for sniff mode)
- `yt-dlp` and `aria2c` — installed automatically by the setup script

## Install (one-time, any machine)

**Windows:**
```bat
git clone git@github.com:arnabbiswas1510/vidsniff.git
cd vidsniff
setup.bat
```

**Linux / macOS / WSL:**
```bash
git clone git@github.com:arnabbiswas1510/vidsniff.git
cd vidsniff
chmod +x setup.sh && ./setup.sh
```

The setup script:
1. Runs `pip install -e .` — registers `vidsniff` as a system command
2. Adds the Python scripts directory to your `PATH` permanently (`setx` on Windows, updates `.bashrc`/`.zshrc` on Linux/Mac)
3. Installs `aria2c` via `winget` / `apt` / `brew` for faster downloads

> **After setup, open a new terminal.** Then `vidsniff` works from any directory, forever.

---

## Usage

```bash
# YouTube, Vimeo, Twitter, etc. — works exactly like yt-dlp:
vidsniff "https://youtube.com/watch?v=dQw4w9WgXcQ"

# Extract audio as OGG:
vidsniff "https://youtu.be/dQw4w9WgXcQ" -x --audio-format ogg

# Download best quality:
vidsniff "https://youtu.be/dQw4w9WgXcQ" -f "bestvideo[ext=mp4]+bestaudio"

# Site that needs browser interception (domain auto-inferred from URL):
vidsniff "https://bestjavporn.com/video/some-slug/"

# Override domain filter manually (e.g. to include a CDN subdomain):
vidsniff "https://bestjavporn.com/video/some-slug/" --domain bestjavporn.com

# Force sniff mode (skip yt-dlp check):
vidsniff "https://site.com/video/" --sniff
```

All standard yt-dlp options are supported and passed through transparently.

---

## Sniff mode workflow

When vidsniff enters sniff mode:

1. A local HTTP server starts on port `59876`
2. Chrome opens with the `extension/` folder pre-loaded (no manual install required)
3. Navigate to the video page and watch normally
4. The extension captures stream URLs transparently (like Cococut) and sends them to vidsniff
5. The best stream is downloaded automatically

**Tips for sites with pre-roll ads:**
- Let the ad play until the Skip button appears, then skip it
- Click **Play** on the main video — the real stream URL fires at this point
- vidsniff will skip tiny preview clips (< 20 MB) automatically

### Domain filtering (recommended for noisy sites)

If you have other tabs open, their streams will also be captured. Use `--domain` to filter:

```bash
python vidsniff.py "https://site.com/video/" --domain site.com
```

---

## WSL support

vidsniff runs natively in WSL2. It auto-detects WSL and:
- Binds the server to `0.0.0.0` (WSL2 port-forwarding reaches Windows Chrome)
- Launches the Windows Chrome binary from `/mnt/c/Program Files/Google/Chrome/...`

---

## Project structure

```
vidsniff/
├── vidsniff.py        ← Main entry point
├── extension/         ← Chrome extension (auto-loaded, no install needed)
│   ├── manifest.json
│   ├── background.js  ← Uses chrome.webRequest — same technique as Cococut
│   ├── popup.html
│   └── popup.js
├── requirements.txt
├── setup.bat          ← Windows setup
├── setup.sh           ← Linux/macOS/WSL setup
└── README.md
```

---

## Why this works on protected sites

Most "protected" sites detect automation via:
- CDP (Chrome DevTools Protocol) remote control → detectable
- Playwright/Selenium → detectable

VidSniff's extension uses `chrome.webRequest.onBeforeRequest` — a privileged browser API that fires for **every network request in the browser**, including cross-origin iframes, with **zero detection risk**. The page's JavaScript cannot see it.
