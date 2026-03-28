'use strict';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const state = {
  assets: [],        // array of asset objects
  polling: new Map() // assetId -> intervalId
};

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------
function apiKey() {
  return document.getElementById('api-key').value.trim() || 'demo';
}

async function apiFetch(path, options = {}) {
  const key = apiKey();
  const headers = {
    'Content-Type': 'application/json',
    'X-API-Key': key,
    ...(options.headers || {})
  };
  const resp = await fetch(path, { ...options, headers });
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const body = await resp.json();
      detail = body.detail || detail;
    } catch (_) { /* ignore */ }
    throw new Error(detail);
  }
  return resp.json();
}

// ---------------------------------------------------------------------------
// Toast notifications
// ---------------------------------------------------------------------------
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const icons = { error: '✗', success: '✓', info: 'ℹ' };
  const div = document.createElement('div');
  div.className = `toast ${type}`;
  div.innerHTML = `
    <span class="toast-icon">${icons[type] || icons.info}</span>
    <span>${message}</span>
    <button class="toast-close" onclick="this.parentElement.remove()">×</button>
  `;
  container.appendChild(div);
  setTimeout(() => div.remove(), 5000);
}

// ---------------------------------------------------------------------------
// Asset generation
// ---------------------------------------------------------------------------
async function generateAsset() {
  const textarea = document.getElementById('description');
  const desc = textarea.value.trim();
  if (!desc) {
    showToast('Please enter an asset description.', 'error');
    textarea.focus();
    return;
  }

  const btn = document.getElementById('generate-btn');
  const progress = document.getElementById('progress-bar');

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Generating…';
  progress.classList.add('visible');
  const fill = progress.querySelector('.progress-fill');
  fill.classList.add('indeterminate');

  try {
    const asset = await apiFetch('/assets', {
      method: 'POST',
      body: JSON.stringify({ description: desc })
    });

    textarea.value = '';
    upsertAsset(asset);
    renderGallery();

    if (asset.status === 'pending' || asset.status === 'generating') {
      startPolling(asset.id);
    } else {
      showToast('Asset generated successfully!', 'success');
    }
  } catch (err) {
    showToast(`Generation failed: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = 'Generate';
    fill.classList.remove('indeterminate');
    progress.classList.remove('visible');
  }
}

// ---------------------------------------------------------------------------
// Polling
// ---------------------------------------------------------------------------
function startPolling(assetId) {
  if (state.polling.has(assetId)) return;
  const id = setInterval(() => pollAsset(assetId), 2000);
  state.polling.set(assetId, id);
}

async function pollAsset(assetId) {
  try {
    const asset = await apiFetch(`/assets/${assetId}`);
    upsertAsset(asset);
    renderGallery();
    if (asset.status !== 'pending' && asset.status !== 'generating') {
      clearInterval(state.polling.get(assetId));
      state.polling.delete(assetId);
      if (asset.status === 'ready') {
        showToast('Asset ready!', 'success');
      } else if (asset.status === 'error') {
        showToast('Asset generation failed.', 'error');
      }
    }
  } catch (err) {
    clearInterval(state.polling.get(assetId));
    state.polling.delete(assetId);
  }
}

// ---------------------------------------------------------------------------
// State management
// ---------------------------------------------------------------------------
function upsertAsset(asset) {
  const idx = state.assets.findIndex(a => a.id === asset.id);
  if (idx >= 0) {
    state.assets[idx] = asset;
  } else {
    state.assets.unshift(asset);
  }
}

// ---------------------------------------------------------------------------
// Refine modal
// ---------------------------------------------------------------------------
function openRefineModal(assetId, description) {
  closeModal();
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.id = 'refine-modal';
  overlay.innerHTML = `
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="refine-title">
      <h3 id="refine-title">Refine Asset</h3>
      <p>Asset: <em>${escapeHtml(description)}</em></p>
      <textarea id="refine-feedback" placeholder="Describe what to change or improve…"></textarea>
      <div class="modal-actions">
        <button class="btn btn-outline btn-sm" onclick="closeModal()">Cancel</button>
        <button class="btn btn-primary btn-sm" onclick="submitRefinement('${escapeHtml(assetId)}')">
          Refine
        </button>
      </div>
    </div>
  `;
  overlay.addEventListener('click', e => { if (e.target === overlay) closeModal(); });
  document.body.appendChild(overlay);
  document.getElementById('refine-feedback').focus();
}

function closeModal() {
  const m = document.getElementById('refine-modal');
  if (m) m.remove();
}

async function submitRefinement(assetId) {
  const feedback = document.getElementById('refine-feedback').value.trim();
  if (!feedback) {
    showToast('Please enter refinement feedback.', 'error');
    return;
  }

  const btn = document.querySelector('#refine-modal .btn-primary');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Refining…';

  try {
    const asset = await apiFetch(`/assets/${assetId}/refine`, {
      method: 'PATCH',
      body: JSON.stringify({ feedback })
    });
    closeModal();
    upsertAsset(asset);
    renderGallery();
    if (asset.status === 'pending' || asset.status === 'generating') {
      startPolling(asset.id);
    } else {
      showToast('Refinement complete!', 'success');
    }
  } catch (err) {
    showToast(`Refinement failed: ${err.message}`, 'error');
    btn.disabled = false;
    btn.innerHTML = 'Refine';
  }
}

// ---------------------------------------------------------------------------
// Google Drive integration
// ---------------------------------------------------------------------------
let _driveAuthenticated = false;

async function checkDriveStatus() {
  try {
    const resp = await fetch('/auth/google/status');
    if (resp.ok) {
      const data = await resp.json();
      _driveAuthenticated = data.authenticated;
    }
  } catch (_) {
    _driveAuthenticated = false;
  }
  updateDriveIndicator();
}

function updateDriveIndicator() {
  const el = document.getElementById('drive-status');
  if (!el) return;
  if (_driveAuthenticated) {
    el.textContent = 'Connected to Drive';
    el.className = 'drive-status connected';
  } else {
    el.textContent = '';
    el.className = 'drive-status';
  }
}

async function exportToDrive(assetId) {
  if (!_driveAuthenticated) {
    sessionStorage.setItem('pendingDriveExport', assetId);
    window.location.href = '/auth/google';
    return;
  }

  try {
    const resp = await fetch(`/assets/${assetId}/export/drive`, { method: 'POST' });
    if (resp.status === 401) {
      _driveAuthenticated = false;
      updateDriveIndicator();
      sessionStorage.setItem('pendingDriveExport', assetId);
      window.location.href = '/auth/google';
      return;
    }
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${resp.status}`);
    }
    const data = await resp.json();
    const link = data.drive_url
      ? ` — <a href="${escapeHtml(data.drive_url)}" target="_blank" rel="noopener">View in Drive</a>`
      : '';
    showToast(`Exported to Google Drive!${link}`, 'success');
  } catch (err) {
    showToast(`Drive export failed: ${err.message}`, 'error');
  }
}

function resumePendingDriveExport() {
  const assetId = sessionStorage.getItem('pendingDriveExport');
  if (assetId && _driveAuthenticated) {
    sessionStorage.removeItem('pendingDriveExport');
    exportToDrive(assetId);
  }
}

// ---------------------------------------------------------------------------
// Inline USD file preview
// ---------------------------------------------------------------------------
async function openUsdPreview(assetId) {
  closeModal();

  // Show modal immediately with loading state
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.id = 'usd-preview-modal';
  overlay.innerHTML = `
    <div class="modal modal-wide" role="dialog" aria-modal="true" aria-labelledby="usd-preview-title">
      <div class="modal-header">
        <h3 id="usd-preview-title">USD File Preview</h3>
        <div class="modal-header-actions">
          <button class="btn btn-outline btn-sm" onclick="downloadUsd('${escapeHtml(assetId)}')">
            ↓ Download
          </button>
          <button class="btn btn-outline btn-sm" onclick="closeModal()">✕ Close</button>
        </div>
      </div>
      <div id="usd-preview-body" class="usd-preview-body">
        <div class="usd-preview-loading">
          <span class="spinner"></span> Loading…
        </div>
      </div>
    </div>
  `;
  overlay.addEventListener('click', e => { if (e.target === overlay) closeModal(); });
  document.body.appendChild(overlay);
  document.getElementById('usd-preview-modal').querySelector('.modal').focus?.();

  // Fetch the raw .usda content
  try {
    const resp = await fetch(`/assets/${assetId}/file`, {
      headers: { 'X-API-Key': apiKey() }
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const text = await resp.text();

    const body = document.getElementById('usd-preview-body');
    body.innerHTML = `
      <div class="usd-preview-meta">
        <span class="usd-meta-tag">USDA</span>
        <span class="usd-meta-size">${formatBytes(text.length)}</span>
        <span class="usd-meta-lines">${text.split('\n').length} lines</span>
      </div>
      <pre class="usd-code"><code>${escapeHtml(text)}</code></pre>
    `;
  } catch (err) {
    const body = document.getElementById('usd-preview-body');
    body.innerHTML = `<p class="usd-preview-error">Failed to load USD file: ${escapeHtml(err.message)}</p>`;
  }
}

async function downloadUsd(assetId) {
  try {
    const resp = await fetch(`/assets/${assetId}/file`, {
      headers: { 'X-API-Key': apiKey() }
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const text = await resp.text();
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${assetId}.usda`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    showToast(`Download failed: ${err.message}`, 'error');
  }
}

function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  } catch (_) { return iso; }
}

function renderGallery() {
  const grid = document.getElementById('asset-grid');
  const empty = document.getElementById('gallery-empty');
  const countBadge = document.getElementById('asset-count');

  countBadge.textContent = state.assets.length;

  if (state.assets.length === 0) {
    empty.style.display = 'block';
    grid.style.display = 'none';
    return;
  }

  empty.style.display = 'none';
  grid.style.display = 'grid';

  grid.innerHTML = state.assets.map(asset => {
    const isReady = asset.status === 'ready';
    const isActive = asset.status === 'pending' || asset.status === 'generating';
    const statusClass = `status-${asset.status}`;
    const desc = escapeHtml(asset.description || '(no description)');
    const id = escapeHtml(asset.id);
    const url = asset.url ? escapeHtml(asset.url) : null;

    return `
      <div class="asset-card" data-id="${id}">
        <div class="card-top">
          <span class="card-description">${desc}</span>
          <span class="status-badge ${statusClass}">
            ${isActive ? '<span class="spinner"></span> ' : ''}${escapeHtml(asset.status)}
          </span>
        </div>
        <div class="card-meta">
          <span>ID: <code>${id.slice(0, 8)}…</code></span>
          <span>Created: ${formatDate(asset.created_at)}</span>
          ${asset.completed_at ? `<span>Completed: ${formatDate(asset.completed_at)}</span>` : ''}
          ${url ? `<span class="url" title="${url}">${url}</span>` : ''}
          ${asset.parent_id ? `<span>Refined from: <code>${escapeHtml(asset.parent_id).slice(0, 8)}…</code></span>` : ''}
        </div>
        <div class="card-actions">
          ${isReady ? `
            <a class="btn btn-outline btn-sm" href="/view/${id}" target="_blank" rel="noopener">
              View 3D
            </a>
            <button class="btn btn-outline btn-sm" onclick="openUsdPreview('${id}')">
              Preview USD
            </button>
            <button class="btn btn-outline btn-sm"
              onclick="openRefineModal('${id}', '${desc.replace(/'/g, "\\'")}')">
              Refine
            </button>
            <button class="btn btn-success btn-sm" onclick="exportToDrive('${id}')">
              Export to Drive
            </button>
          ` : ''}
        </div>
      </div>
    `;
  }).join('');
}

// ---------------------------------------------------------------------------
// API key persistence
// ---------------------------------------------------------------------------
function initApiKey() {
  const input = document.getElementById('api-key');
  const saved = localStorage.getItem('usdagent_api_key');
  if (saved) input.value = saved;
  input.addEventListener('input', () => {
    localStorage.setItem('usdagent_api_key', input.value);
  });
}

// ---------------------------------------------------------------------------
// Keyboard shortcut: Ctrl/Cmd+Enter in textarea submits
// ---------------------------------------------------------------------------
function initKeyboardShortcuts() {
  document.getElementById('description').addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      generateAsset();
    }
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal();
  });
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  initApiKey();
  initKeyboardShortcuts();
  renderGallery();
  checkDriveStatus().then(resumePendingDriveExport);
});
