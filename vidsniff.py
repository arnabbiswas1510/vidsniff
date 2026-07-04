#!/usr/bin/env python3
"""
vidsniff — Smart universal video downloader
==========================================
A wrapper around yt-dlp that adds browser-interception for sites
that yt-dlp cannot handle natively (e.g. sites behind Cloudflare,
DRM-lite players, etc.).

Usage
-----
  # Works like yt-dlp for any supported site (YouTube, Vimeo, etc.):
  python vidsniff.py "https://youtube.com/watch?v=..."
  python vidsniff.py "https://youtube.com/watch?v=..." -x --audio-format ogg
  python vidsniff.py "https://youtube.com/watch?v=..." -f "bestvideo+bestaudio"

  # For sites that need browser interception:
  python vidsniff.py "https://bestjavporn.com/video/some-slug/" --sniff
  python vidsniff.py "https://site.com/video/" --sniff --domain site.com

  # Auto-detect (try yt-dlp first, fall back to sniff mode):
  python vidsniff.py "https://unknown-site.com/video/slug/"

How it works (sniff mode)
-------------------------
1. Starts a local HTTP server on port 59876
2. Launches Chrome with the bundled extension pre-loaded (no manual install)
3. You watch the video normally; the extension captures the stream URL
4. The best video URL is downloaded (yt-dlp first, then direct download)

WSL note
--------
The server binds to 0.0.0.0 so WSL2 port-forwarding reaches Windows Chrome.
Chrome is launched from /mnt/c/Program Files/Google/Chrome/Application/chrome.exe
"""

import sys
import os
import re
import json
import time
import threading
import subprocess
import argparse
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
PORT = 59876
EXT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'extension')
MIN_DOWNLOAD_MB = 20   # Skip files smaller than this (previews)

# ─────────────────────────────────────────────
# Chrome path detection
# ─────────────────────────────────────────────
def find_chrome():
    candidates = []
    # WSL: call Windows Chrome directly
    if 'microsoft' in open('/proc/version').read().lower() if os.path.exists('/proc/version') else False:
        candidates += [
            '/mnt/c/Program Files/Google/Chrome/Application/chrome.exe',
            '/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe',
        ]
    # Windows native
    candidates += [
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
    ]
    # Linux / Mac
    candidates += [
        '/usr/bin/google-chrome', '/usr/bin/chromium-browser', '/usr/bin/chromium',
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def is_wsl():
    try:
        return 'microsoft' in open('/proc/version').read().lower()
    except Exception:
        return False


def wsl_to_win_path(path):
    """Convert /mnt/c/... to C:\\... for Chrome's --load-extension."""
    m = re.match(r'^/mnt/([a-z])(/.*)$', path)
    if m:
        return m.group(1).upper() + ':' + m.group(2).replace('/', '\\')
    return path


# ─────────────────────────────────────────────
# Filename helpers
# ─────────────────────────────────────────────
def slug_from_url(url):
    """Extract a human-readable slug from the video page URL."""
    parsed = urlparse(url)
    parts = [p for p in parsed.path.strip('/').split('/') if p]
    # Prefer the last meaningful path segment (skip generic ones)
    for part in reversed(parts):
        if len(part) > 3 and part not in ('video', 'watch', 'embed', 'v', 'play'):
            return part
    return parts[-1] if parts else 'video'


def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', '-', name)


# ─────────────────────────────────────────────
# yt-dlp helpers
# ─────────────────────────────────────────────
def ytdlp_supports(url):
    """Return True if yt-dlp can extract this URL natively."""
    try:
        result = subprocess.run(
            ['yt-dlp', '--simulate', '--quiet', '--no-warnings', url],
            capture_output=True, timeout=20)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def ytdlp_download(url, extra_args, output_template=None):
    """Run yt-dlp with the given URL and extra args. Returns True on success."""
    cmd = ['yt-dlp', '--no-playlist']
    if output_template:
        cmd += ['-o', output_template]
    cmd += extra_args
    cmd.append(url)
    print(f'[*] Running: yt-dlp {" ".join(extra_args)} ...')
    try:
        subprocess.run(cmd, check=True)
        return True
    except FileNotFoundError:
        print('[!] yt-dlp not found. Install: pip install yt-dlp')
        return False
    except subprocess.CalledProcessError:
        return False


def direct_download(url, output):
    """Direct HTTP download with progress bar. Fallback when yt-dlp fails."""
    print(f'[*] Direct download → {output}')
    ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    req = urllib.request.Request(url, headers={'User-Agent': ua, 'Referer': 'https://www.google.com/'})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            total = int(resp.headers.get('Content-Length', 0))
            done = 0
            with open(output, 'wb') as f:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        pct = done / total * 100
                        mb = done / 1024 / 1024
                        print(f'\r   {pct:.1f}%  {mb:.1f} / {total/1024/1024:.1f} MB', end='', flush=True)
        print(f'\n[+] Saved: {output}')
        return True
    except Exception as e:
        print(f'\n[!] Direct download failed: {e}')
        return False


def probe_size(url):
    ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    for method, extra in [('HEAD', {}), ('GET', {'Range': 'bytes=0-0'})]:
        try:
            req = urllib.request.Request(
                url, method=method,
                headers={'User-Agent': ua, 'Referer': 'https://www.google.com/', **extra})
            with urllib.request.urlopen(req, timeout=8) as r:
                cr = r.getheader('Content-Range', '')
                m = re.search(r'/(\d+)', cr)
                if m: return int(m.group(1))
                cl = r.getheader('Content-Length', '')
                if cl and int(cl) > 1: return int(cl)
        except Exception:
            continue
    return 0


def size_str(b):
    if not b: return '?'
    if b < 1024 * 1024: return f'{b/1024:.0f} KB'
    return f'{b/1024/1024:.1f} MB'


# ─────────────────────────────────────────────
# URL classification (for sniff mode)
# ─────────────────────────────────────────────
VIDEO_EXTS      = ('.m3u8', '.mpd', '.mp4', '.m4v', '.webm', '.flv', '.ts')
PLAYLIST_EXTS   = ('.m3u8', '.mpd', '.m3u')
IMAGE_EXTS      = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico',
                   '.css', '.js', '.woff', '.woff2', '.ttf', '.eot',
                   '.html', '.htm', '.json', '.xml', '.txt', '.vtt', '.srt')
VIDEO_MIMES     = ('video/', 'application/x-mpegurl', 'application/vnd.apple.mpegurl',
                   'application/dash+xml')
AD_PATTERNS     = ('300x250', '728x90', 'preroll', '/banner', 'top_banner',
                   'overlay', 'ping.m3u8')


def is_real_video_url(url, ct=''):
    path = url.lower().split('?')[0]
    if any(path.endswith(e) for e in IMAGE_EXTS): return False
    # Skip individual HLS segments / init chunks
    if path.endswith('.ts') or '_av1_' in url or '_init_' in url: return False
    if any(path.endswith(e) for e in VIDEO_EXTS): return True
    if any(m in ct.lower() for m in VIDEO_MIMES): return True
    return False


def is_playlist(url, ct=''):
    p = url.lower().split('?')[0]
    return (any(p.endswith(e) for e in PLAYLIST_EXTS)
            or any(m in ct.lower() for m in ('mpegurl', 'dash+xml')))


def is_ad(url):
    return any(p in url.lower() for p in AD_PATTERNS)


def pick_best(caps, skipped):
    real = [c for c in caps
            if is_real_video_url(c['url'], c.get('contentType', ''))
            and not is_ad(c['url'])
            and c['url'] not in skipped]
    if not real:
        return None
    playlists = [c for c in real if is_playlist(c['url'], c.get('contentType', ''))]
    if playlists:
        return playlists[0]
    return max(real, key=lambda c: c.get('size', 0))


# ─────────────────────────────────────────────
# Local HTTP server (receives URLs from extension)
# ─────────────────────────────────────────────
_captures = []
_lock = threading.Lock()
_allowed_domains = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def _ok(self, body=b'ok'):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != '/capture':
            self.send_response(404); self.end_headers(); return
        try:
            length = int(self.headers.get('Content-Length', 0))
            entry = json.loads(self.rfile.read(length))
            url = entry.get('url', '')
            ct  = entry.get('contentType', '')

            if not is_real_video_url(url, ct):
                return self._ok(b'skip')

            frame_url = entry.get('frameUrl', '') or ''
            if _allowed_domains:
                host = urlparse(frame_url).netloc
                if not any(d in host for d in _allowed_domains):
                    return self._ok(b'filtered')

            with _lock:
                if not any(c['url'] == url for c in _captures):
                    _captures.append(entry)
                    pl = is_playlist(url, ct)
                    ad = is_ad(url)
                    tag = 'PLAYLIST' if pl else ('AD?   ' if ad else 'DIRECT ')
                    frame_host = urlparse(frame_url).netloc
                    sz = size_str(entry.get('size', 0))
                    print(f'\n[+] [{tag}] [{sz:>8}] {url[:80]}')
                    if frame_host: print(f'         frame: {frame_host}')
            self._ok()
        except Exception:
            self.send_response(500); self.end_headers()

    def do_GET(self):
        if self.path == '/captures':
            with _lock:
                data = json.dumps(_captures).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404); self.end_headers()


# ─────────────────────────────────────────────
# Chrome launcher
# ─────────────────────────────────────────────
def launch_chrome(url, chrome_path, profile_dir=None):
    ext_path = EXT_DIR
    if is_wsl():
        ext_path = wsl_to_win_path(ext_path)

    cmd = [
        chrome_path,
        f'--load-extension={ext_path}',
        '--no-first-run',
        '--no-default-browser-check',
        url,
    ]
    if profile_dir:
        cmd.insert(1, f'--user-data-dir={profile_dir}')

    print(f'[*] Launching Chrome with extension pre-loaded...')
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return proc
    except Exception as e:
        print(f'[!] Could not launch Chrome: {e}')
        print(f'    Path tried: {chrome_path}')
        return None


# ─────────────────────────────────────────────
# Sniff mode: capture + download loop
# ─────────────────────────────────────────────
def sniff_and_download(url, output_template, extra_ytdlp_args, timeout, domain_filter):
    global _allowed_domains
    if domain_filter:
        _allowed_domains = domain_filter

    # Start local server (bind 0.0.0.0 for WSL2 compatibility)
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    chrome = find_chrome()
    if not chrome:
        print('[!] Chrome not found. Set CHROME_PATH env var or install Chrome.')
        server.shutdown()
        return False

    print(f'[*] vidsniff — sniff mode')
    print(f'[*] Server: http://localhost:{PORT}')
    print(f'[*] Extension: {EXT_DIR}')
    if domain_filter:
        print(f'[*] Domain filter: {", ".join(domain_filter)}')
    print(f'[*] Timeout: {timeout}s')
    print()

    chrome_proc = launch_chrome(url, chrome)
    print(f'[*] Chrome opened. Watch the video (skip ads, then press play).')
    print(f'    (Press Ctrl+C to stop and show captured URLs)\n')

    downloaded = set()
    skipped_urls = set()
    first_good_at = None
    deadline = time.time() + timeout

    try:
        while True:
            time.sleep(1)
            with _lock:
                caps = list(_captures)

            good = [c for c in caps
                    if not is_ad(c['url'])
                    and is_real_video_url(c['url'], c.get('contentType', ''))
                    and c['url'] not in downloaded
                    and c['url'] not in skipped_urls]

            if good:
                if first_good_at is None:
                    first_good_at = time.time()
                    print('[*] Non-ad stream detected — waiting 10s for more to arrive...')
                    print('    >> Skip the ad and click PLAY if you haven\'t yet <<')
                elif time.time() - first_good_at >= 10:
                    best = pick_best(caps, skipped_urls)
                    if best and best['url'] not in downloaded:
                        sz = best.get('size', 0)
                        if not sz:
                            print(f'   [size] probing...')
                            sz = probe_size(best['url'])
                            best['size'] = sz
                            if sz: print(f'   [size] {size_str(sz)}')
                        if sz and sz < MIN_DOWNLOAD_MB * 1024 * 1024:
                            skipped_urls.add(best['url'])
                            first_good_at = None
                            print(f'[*] Skipping {size_str(sz)} preview. Waiting for main video...')
                            print('    >> Make sure you clicked PLAY <<')
                        else:
                            downloaded.add(best['url'])
                            first_good_at = None
                            _do_download(best['url'], output_template, extra_ytdlp_args)
                            print(f'\n[*] Monitoring for more streams... (Ctrl+C to exit)')

            if time.time() > deadline:
                if not any(not is_ad(c['url']) for c in _captures):
                    print(f'\n[!] Timed out — no main video streams captured.')
                break

    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        if chrome_proc:
            try: chrome_proc.terminate()
            except Exception: pass

    with _lock:
        caps = list(_captures)
    _print_summary(caps)
    return bool(downloaded)


def _do_download(url, output_template, extra_args):
    """Try yt-dlp first, then direct download."""
    cmd = ['yt-dlp', '--no-playlist']
    if output_template:
        cmd += ['-o', output_template]
    cmd += extra_args
    cmd.append(url)
    print(f'\n[*] Downloading: {url[:80]}')
    print(f'[*] Running: yt-dlp {" ".join(extra_args)} ...')
    try:
        subprocess.run(cmd, check=True)
        print('[+] Download complete!')
        return True
    except FileNotFoundError:
        print('[!] yt-dlp not found. Install: pip install yt-dlp')
        return False
    except subprocess.CalledProcessError:
        print('[*] yt-dlp failed, trying direct download...')
        out = (output_template or '{slug}.mp4').replace('{slug}', 'video')
        if '.' not in os.path.basename(out):
            out += '.mp4'
        return direct_download(url, out)


def _print_summary(caps):
    if not caps:
        print('\n[!] No streams captured.')
        return
    print(f'\n\n{"="*60}')
    print(f'Captured {len(caps)} stream(s):')
    print('='*60)
    for i, c in enumerate(caps):
        pl = is_playlist(c['url'], c.get('contentType', ''))
        ad = is_ad(c['url'])
        tag = 'PLAYLIST' if pl else ('AD' if ad else 'DIRECT')
        print(f'  [{i+1}] [{tag}] [{size_str(c.get("size", 0))}] {c["url"][:85]}')


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        prog='vidsniff',
        description='Smart video downloader — yt-dlp wrapper + browser interception.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # YouTube (passes straight to yt-dlp):
  python vidsniff.py "https://youtu.be/dQw4w9WgXcQ"
  python vidsniff.py "https://youtu.be/dQw4w9WgXcQ" -x --audio-format ogg
  python vidsniff.py "https://youtu.be/dQw4w9WgXcQ" -f "bestvideo[ext=mp4]+bestaudio"

  # Auto-detect + sniff mode for unknown sites:
  python vidsniff.py "https://bestjavporn.com/video/some-slug/"
  python vidsniff.py "https://bestjavporn.com/video/some-slug/" --domain bestjavporn.com

  # Force sniff mode (skip yt-dlp check):
  python vidsniff.py "https://site.com/video/" --sniff
        """)

    ap.add_argument('url', help='Video page URL')
    ap.add_argument('--sniff', action='store_true',
                    help='Force browser-interception mode (skip yt-dlp auto-check)')
    ap.add_argument('--domain', nargs='+', metavar='DOMAIN',
                    help='Only capture streams from these frame domains (sniff mode). '
                         'Filters other open tabs. E.g.: --domain bestjavporn.com')
    ap.add_argument('-o', '--output', metavar='TEMPLATE',
                    help='Output filename template. Default: derived from URL slug. '
                         'Passed to yt-dlp as-is, or used for direct downloads.')
    ap.add_argument('--timeout', type=int, default=180,
                    help='Sniff mode timeout in seconds (default: 180)')
    ap.add_argument('--no-auto', action='store_true',
                    help='Skip yt-dlp auto-detection; always prompt before using sniff mode')

    # Capture all remaining args as extra yt-dlp passthrough options
    args, extra = ap.parse_known_args()

    url   = args.url
    slug  = sanitize_filename(slug_from_url(url))
    output = args.output or f'{slug}.%(ext)s'

    print(f'[*] vidsniff  |  {url[:70]}')
    print(f'[*] Output:   {output}')

    # ── Step 1: Try yt-dlp natively (for YouTube, Vimeo, etc.) ──────────────
    if not args.sniff:
        print(f'[*] Checking yt-dlp support...')
        if ytdlp_supports(url):
            print(f'[*] yt-dlp supports this site — downloading directly.')
            success = ytdlp_download(url, extra, output)
            if success:
                return
            print(f'[*] yt-dlp failed, falling back to sniff mode...')
        else:
            print(f'[*] yt-dlp does not support this site — using sniff mode.')

    # ── Step 2: Sniff mode ───────────────────────────────────────────────────
    if not os.path.isdir(EXT_DIR):
        print(f'[!] Extension not found at: {EXT_DIR}')
        print(f'    Make sure the "extension/" folder is next to vidsniff.py')
        sys.exit(1)

    sniff_and_download(
        url=url,
        output_template=output,
        extra_ytdlp_args=extra,
        timeout=args.timeout,
        domain_filter=args.domain or [],
    )


if __name__ == '__main__':
    main()
