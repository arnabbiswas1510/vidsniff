// popup.js

function typeTag(url) {
  const lower = url.toLowerCase().split('?')[0];
  if (lower.endsWith('.m3u8')) return ['m3u8', 'type-m3u8'];
  if (lower.endsWith('.mp4') || lower.endsWith('.m4v')) return ['mp4', 'type-mp4'];
  if (lower.endsWith('.ts')) return ['ts', 'type-ts'];
  if (lower.endsWith('.mpd')) return ['mpd', 'type-m3u8'];
  return ['stream', 'type-other'];
}

function sizeStr(bytes) {
  if (!bytes || bytes < 1024) return '';
  if (bytes < 1024 * 1024) return ` · ${(bytes / 1024).toFixed(0)} KB`;
  return ` · ${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function showStatus(msg, duration = 1500) {
  const el = document.getElementById('status');
  el.textContent = msg;
  el.style.display = 'block';
  setTimeout(() => { el.style.display = 'none'; }, duration);
}

function render(captures) {
  const container = document.getElementById('captures');
  const empty = document.getElementById('empty');
  const count = document.getElementById('count');

  count.textContent = `${captures.length} stream${captures.length === 1 ? '' : 's'}`;

  if (!captures || captures.length === 0) {
    empty.style.display = 'block';
    // Remove all items
    [...container.querySelectorAll('.item')].forEach(el => el.remove());
    return;
  }
  empty.style.display = 'none';

  // Re-render all
  [...container.querySelectorAll('.item')].forEach(el => el.remove());

  captures.forEach(cap => {
    const [label, cls] = typeTag(cap.url);
    const frameHost = cap.frameUrl ? ` · frame: ${cap.frameUrl.replace(/https?:\/\//, '').split('/')[0]}` : '';
    const sz = sizeStr(cap.size);
    const time = new Date(cap.timestamp).toLocaleTimeString();

    const div = document.createElement('div');
    div.className = 'item';
    div.innerHTML = `
      <div>
        <span class="item-type ${cls}">${label}</span>
        <button class="item-copy" data-url="${cap.url}">copy</button>
        <span style="font-size:10px;color:#4a5568">${time}</span>
      </div>
      <div class="item-url">${cap.url}</div>
      <div class="item-meta">${cap.type || ''}${sz}${frameHost}</div>
    `;

    // Click URL to open in new tab
    div.querySelector('.item-url').addEventListener('click', () => {
      chrome.tabs.create({ url: cap.url });
    });

    // Copy button
    div.querySelector('.item-copy').addEventListener('click', (e) => {
      e.stopPropagation();
      navigator.clipboard.writeText(cap.url).then(() => showStatus('✓ Copied!'));
    });

    container.appendChild(div);
  });
}

// Initial load
chrome.storage.local.get(['captures'], (data) => {
  render(data.captures || []);
});

// Live updates via storage changes
chrome.storage.onChanged.addListener((changes) => {
  if (changes.captures) {
    render(changes.captures.newValue || []);
  }
});

// Clear button
document.getElementById('btnClear').addEventListener('click', () => {
  chrome.runtime.sendMessage({ action: 'clear' }, () => {
    render([]);
    showStatus('✓ Cleared');
  });
});

// Copy All button
document.getElementById('btnCopyAll').addEventListener('click', () => {
  chrome.storage.local.get(['captures'], (data) => {
    const urls = (data.captures || []).map(c => c.url).join('\n');
    navigator.clipboard.writeText(urls).then(() => showStatus(`✓ Copied ${(data.captures||[]).length} URLs`));
  });
});
