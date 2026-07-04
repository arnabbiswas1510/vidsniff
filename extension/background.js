// VidSniff background.js v2
// Uses chrome.webRequest to intercept ALL media requests across ALL frames
// including cross-origin iframes — exactly how Cococut works.

const VIDEO_EXTS = ['.m3u8', '.mp4', '.webm', '.flv', '.m4v', '.mpd', '.m3u'];
const VIDEO_MIME_PATTERNS = ['video/', 'audio/mpegurl', 'application/x-mpegurl',
                             'application/vnd.apple.mpegurl', 'application/dash+xml'];
const VIDEO_PATH_PATTERNS = ['/hls/', '/dash/', '/stream/', '/manifest/', '.m3u8', '.mp4'];

// Exclude these — don't match even if path contains 'files/' or 'stream/'
const IMAGE_EXTS = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico',
                    '.css', '.js', '.woff', '.woff2', '.ttf', '.eot',
                    '.html', '.htm', '.json', '.xml', '.txt', '.vtt', '.srt'];

// Ad/tracker domains to silently ignore
const BLOCK_DOMAINS = [
  'magsrv.com', 'doubleclick.net', 'google-analytics.com',
  'googletagmanager.com', 'facebook.net', 'adsrvr.org',
  'adnxs.com', 'rubiconproject.com', 'elastic-sync.xyz',
  'kibibe.com', 'tsyndicate.com', 'sandwichconscientiousroadside.com'
];

const SERVER = 'http://localhost:59876/capture';

let captures = [];
const MAX_CAPTURES = 500;

function isVideoUrl(url) {
  try {
    const lower = url.toLowerCase();
    const path = lower.split('?')[0];
    if (IMAGE_EXTS.some(e => path.endsWith(e))) return false;
    // Skip individual HLS segments (very noisy)
    if (path.endsWith('.ts') || lower.includes('_av1_') || lower.includes('_init_')) return false;
    if (VIDEO_EXTS.some(e => path.endsWith(e))) return true;
    if (VIDEO_PATH_PATTERNS.some(p => lower.includes(p))) return true;
    return false;
  } catch (e) { return false; }
}

function isBlockedDomain(url) {
  try {
    const host = new URL(url).hostname;
    return BLOCK_DOMAINS.some(d => host.includes(d));
  } catch (e) { return false; }
}

// Get page title for the tab that initiated the request
async function getTabTitle(tabId) {
  try {
    if (tabId && tabId > 0) {
      const tab = await chrome.tabs.get(tabId);
      return tab.title || '';
    }
  } catch (e) {}
  return '';
}

async function processCapture(details, contentType = '', size = 0) {
  const url = details.url;
  if (!url || !url.startsWith('http')) return;
  if (isBlockedDomain(url)) return;
  if (!isVideoUrl(url)) return;
  if (captures.some(c => c.url === url)) return;

  const pageTitle = await getTabTitle(details.tabId);

  const entry = {
    url,
    tabId: details.tabId,
    frameId: details.frameId,
    frameUrl: details.initiator || '',
    type: details.type,
    contentType,
    size,
    pageTitle,
    timestamp: Date.now(),
  };

  captures.unshift(entry);
  if (captures.length > MAX_CAPTURES) captures.pop();
  chrome.storage.local.set({ captures });

  // Post to local vidsniff server (silently ignore if not running)
  fetch(SERVER, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(entry),
  }).catch(() => {});
}

// Intercept requests BEFORE they are made (catches everything)
chrome.webRequest.onBeforeRequest.addListener(
  (details) => { processCapture(details); },
  { urls: ['<all_urls>'] },
  ['requestBody']
);

// Also intercept response headers to get Content-Type and Content-Length
chrome.webRequest.onHeadersReceived.addListener(
  (details) => {
    const url = details.url;
    if (!url || !url.startsWith('http')) return;
    if (isBlockedDomain(url)) return;

    const headers = details.responseHeaders || [];
    const ct = (headers.find(h => h.name.toLowerCase() === 'content-type') || {}).value || '';
    const cl = (headers.find(h => h.name.toLowerCase() === 'content-length') || {}).value || '';
    const isVideoMime = ['video/', 'application/x-mpegurl', 'application/vnd.apple.mpegurl',
                         'application/dash+xml'].some(m => ct.toLowerCase().includes(m));
    if (!isVideoMime) return;

    const size = parseInt(cl) || 0;
    if (captures.some(c => c.url === url)) {
      // Update size if we already have this URL
      const existing = captures.find(c => c.url === url);
      if (existing && !existing.size && size) {
        existing.size = size;
        chrome.storage.local.set({ captures });
      }
      return;
    }
    processCapture(details, ct, size);
  },
  { urls: ['<all_urls>'] },
  ['responseHeaders']
);

// Clear captures when tab navigates away
chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.status === 'loading') {
    captures = captures.filter(c => c.tabId !== tabId);
    chrome.storage.local.set({ captures });
  }
});

// Message handler for popup
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === 'clear') {
    captures = [];
    chrome.storage.local.set({ captures });
    sendResponse({ ok: true });
  } else if (msg.action === 'get') {
    sendResponse({ captures });
  }
  return true;
});
