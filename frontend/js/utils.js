// JARVIS v3 — utils.js
window.JARVIS = window.JARVIS || {};

JARVIS.storage = {
  get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch {} },
  del: (k) => { try { localStorage.removeItem(k); } catch {} },
};

JARVIS.toast = (msg, type = "info", duration = 3000) => {
  const c = document.getElementById("toast-container");
  if (!c) return;
  const t = document.createElement("div");
  t.className = `toast ${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), duration);
};

JARVIS.fmtTime = () => {
  const now = new Date();
  return now.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: true });
};

JARVIS.esc = (text) => {
  const d = document.createElement("div");
  d.textContent = text;
  return d.innerHTML;
};

JARVIS.formatMsg = (text) => {
  if (!text) return "";
  let s = text;

  // Code blocks — must come first
  s = s.replace(/```(\w+)?\n?([\s\S]*?)```/g, (_, lang, code) => {
    const escaped = code.trim()
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    return `<pre style="background:#0a0e17;border:1px solid rgba(0,212,255,0.2);border-radius:8px;padding:12px;overflow-x:auto;margin:8px 0;font-family:'Courier New',monospace;font-size:0.82rem;color:#e8f4f8;white-space:pre;">${escaped}</pre>`;
  });

  // Inline code
  s = s.replace(/`([^`]+)`/g,
    `<code style="background:#1a2236;padding:1px 6px;border-radius:4px;font-family:'Courier New',monospace;font-size:0.85em;color:#00d4ff;">$1</code>`
  );

  // Bold
  s = s.replace(/\*\*(.*?)\*\*/g,
    `<strong style="color:#e8f4f8;font-weight:700;">$1</strong>`
  );

  // Italic
  s = s.replace(/\*(.*?)\*/g, "<em>$1</em>");

  // Links
  s = s.replace(/(https?:\/\/[^\s<"]+)/g,
    `<a href="$1" target="_blank" rel="noopener" style="color:#00d4ff;text-decoration:underline;word-break:break-all;">$1</a>`
  );

  // Line breaks
  s = s.replace(/\n/g, "<br>");

  return s;
};

JARVIS.api = async (path, method = "GET", body = null) => {
  const token = JARVIS.storage.get("j_token");
  const opts = {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

JARVIS.debounce = (fn, ms) => {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
};

JARVIS.uuid = () => Math.random().toString(36).slice(2) + Date.now().toString(36);
