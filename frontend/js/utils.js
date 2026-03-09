/* ═══════════════════════════════════════════════════════════
   J.A.R.V.I.S — Utility Helpers
   ═══════════════════════════════════════════════════════════ */

const JARVIS = window.JARVIS = window.JARVIS || {};

// ── Local Storage ──────────────────────────────────────────
JARVIS.storage = {
  get: (k, fallback = null) => {
    try { const v = localStorage.getItem(k); return v !== null ? JSON.parse(v) : fallback; }
    catch { return fallback; }
  },
  set: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
  remove: (k) => { try { localStorage.removeItem(k); } catch {} },
};

// ── Device ID ─────────────────────────────────────────────
JARVIS.getDeviceId = () => {
  let id = JARVIS.storage.get('j_device_id');
  if (!id) {
    id = 'dev_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
    JARVIS.storage.set('j_device_id', id);
  }
  return id;
};

// ── Toast Notifications ────────────────────────────────────
JARVIS.toast = (msg, type = '', duration = 3000) => {
  const container = document.getElementById('toast-container') || (() => {
    const el = document.createElement('div');
    el.id = 'toast-container';
    document.body.appendChild(el);
    return el;
  })();
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  container.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transform = 'scale(0.9)'; t.style.transition = '0.3s'; setTimeout(() => t.remove(), 300); }, duration);
};

// ── Time Formatting ───────────────────────────────────────
JARVIS.timeAgo = (ts) => {
  const d = new Date(ts), now = new Date();
  const diff = Math.floor((now - d) / 1000);
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
};

JARVIS.fmtTime = (ts) => {
  const d = ts ? new Date(ts) : new Date();
  return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });
};

// ── Escape HTML ───────────────────────────────────────────
JARVIS.esc = (s) => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

// ── Format Message (markdown-lite) ───────────────────────
JARVIS.formatMsg = (text) => {
  if (!text) return '';
  let s = JARVIS.esc(text);
  // Code blocks
  s = s.replace(/```(?:\w+\n)?([\s\S]*?)```/g, (_, code) =>
    '<pre style="background:#0a0e17;border:1px solid rgba(0,212,255,0.2);border-radius:8px;padding:12px;overflow-x:auto;margin:8px 0;font-family:monospace;font-size:0.82rem;color:#e8f4f8;white-space:pre;">' + code.trim() + '</pre>'
  );
  // Inline code
  s = s.replace(/`([^`]+)`/g, '<code style="background:#1a2236;padding:1px 6px;border-radius:4px;font-family:monospace;font-size:0.85em;color:#00d4ff;">$1</code>');
  // Bold
  s = s.replace(/\*\*(.*?)\*\*/g, '<strong style="color:#e8f4f8;font-weight:700;">$1</strong>');
  // Italic
  s = s.replace(/\*(.*?)\*/g, '<em>$1</em>');
  // URLs
  s = s.replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener" style="color:#00d4ff;">$1</a>');
  // Line breaks
  s = s.replace(/\n/g, '<br>');
  return s;
};

// ── API Fetch (with auth header) ─────────────────────────
JARVIS.api = async (path, opts = {}) => {
  const token = JARVIS.storage.get('j_token');
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(path, { ...opts, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
};

// ── Debounce ─────────────────────────────────────────────
JARVIS.debounce = (fn, ms) => {
  let t; return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
};

// ── Generate UUID ─────────────────────────────────────────
JARVIS.uuid = () => 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
  const r = Math.random() * 16 | 0;
  return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
});

// ── Check Admin ───────────────────────────────────────────
JARVIS.isAdmin = () => JARVIS.storage.get('j_role') === 'admin';

// ── Family colors ─────────────────────────────────────────
const FAMILY_COLORS = {
  lucky: '#ffd700', krishna: '#00d4ff', sangeetha: '#ff88cc',
  thapaswini: '#cc88ff', dhruva: '#00ff88', prajwal: '#00ff88',
};
JARVIS.memberColor = (name = '') => FAMILY_COLORS[name.toLowerCase()] || 'var(--cyan)';

// ── Show / hide el ───────────────────────────────────────
JARVIS.show = (id) => { const el = document.getElementById(id); if(el) el.classList.remove('hidden'); };
JARVIS.hide = (id) => { const el = document.getElementById(id); if(el) el.classList.add('hidden'); };
