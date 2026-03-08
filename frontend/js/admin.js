/* ═══════════════════════════════════════════════════════════
   J.A.R.V.I.S — Admin Dashboard Module
   Phase 7: Full API-driven admin panel for Lucky only.
   ═══════════════════════════════════════════════════════════ */

JARVIS.admin = (() => {
  let factsData   = [];
  let activeTab   = 'users';

  // ── Show admin panel ──────────────────────────────────
  function show() {
    if (!JARVIS.isAdmin()) { JARVIS.toast('Admin access required.', 'error'); return; }
    const panel = document.getElementById('admin-panel-overlay');
    if (panel) {
      panel.classList.add('active');
      loadTab('users');
    }
  }

  function hide() {
    document.getElementById('admin-panel-overlay')?.classList.remove('active');
  }

  function loadTab(tab) {
    activeTab = tab;
    document.querySelectorAll('.admin-tab').forEach(el =>
      el.classList.toggle('active', el.dataset.tab === tab));
    document.querySelectorAll('.admin-tab-body').forEach(el =>
      el.classList.toggle('active', el.dataset.tab === tab));

    if (tab === 'users')     loadUsers();
    if (tab === 'stats')     loadStats();
    if (tab === 'facts')     loadFacts();
    if (tab === 'devices')   loadDevices();
    if (tab === 'broadcast') { /* static form */ }
  }

  // ── USERS (Pending + All) ─────────────────────────────
  async function loadUsers() {
    await Promise.all([loadPending(), loadAllUsers()]);
  }

  async function loadPending() {
    const list = document.getElementById('pending-users-list');
    if (!list) return;
    try {
      const data  = await JARVIS.api('/admin/pending');
      const users = data.pending || [];
      if (!users.length) {
        list.innerHTML = '<div class="text-muted text-sm" style="padding:8px">No pending approvals 🎉</div>';
        return;
      }
      list.innerHTML = users.map(u => `
        <div class="user-row">
          <div class="user-avatar-big">👤</div>
          <div class="user-info">
            <div class="user-name">${JARVIS.esc(u.display_name || u.username)}</div>
            <div class="user-role">${JARVIS.esc(u.relation || 'guest')} — knows ${JARVIS.esc(u.knows_member || 'unknown')}</div>
          </div>
          <div class="user-actions">
            <button class="approve-btn" data-user="${JARVIS.esc(u.username)}">Approve</button>
          </div>
        </div>`).join('');
      list.querySelectorAll('.approve-btn').forEach(btn => {
        btn.addEventListener('click', () => approveUser(btn.dataset.user));
      });
    } catch (e) {
      list.innerHTML = `<div class="text-muted text-sm">Error: ${JARVIS.esc(e.message)}</div>`;
    }
  }

  async function approveUser(username) {
    try {
      await JARVIS.api('/admin/approve', { method: 'POST', body: JSON.stringify({ username }) });
      JARVIS.toast(`✅ ${username} approved!`, 'success');
      loadUsers();
    } catch (e) { JARVIS.toast('Approval failed: ' + e.message, 'error'); }
  }

  async function loadAllUsers() {
    const list = document.getElementById('all-users-list');
    if (!list) return;
    try {
      const data  = await JARVIS.api('/admin/users');
      const users = data.users || [];
      const roleEmoji = { admin: '👑', father: '👨', mother: '👩', sister: '👧', brother: '👦', guest: '👤' };
      list.innerHTML = users.map(u => `
        <div class="user-row">
          <div class="user-avatar-big">${roleEmoji[u.role] || '👤'}</div>
          <div class="user-info">
            <div class="user-name">${JARVIS.esc(u.display_name || u.username)}</div>
            <div class="user-role">${JARVIS.esc(u.role)} · Logins: ${u.login_count || 0} · ${u.approved ? '✅ Active' : '⏳ Pending'}</div>
          </div>
          <span class="badge ${u.approved ? 'badge-green' : 'badge-red'}">${u.approved ? 'Active' : 'Pending'}</span>
        </div>`).join('');
    } catch {}
  }

  // ── STATS ─────────────────────────────────────────────
  async function loadStats() {
    const grid = document.getElementById('stats-grid');
    if (!grid) return;
    grid.innerHTML = '<div class="text-muted text-sm" style="padding:8px">Loading…</div>';
    try {
      const data = await JARVIS.api('/admin/memory');
      const s = data.stats || {};
      grid.innerHTML = `
        <div class="stat-card"><div class="stat-value">${s.hot || 0}</div><div class="stat-label">Messages (Hot)</div></div>
        <div class="stat-card"><div class="stat-value">${s.archived || 0}</div><div class="stat-label">Archived</div></div>
        <div class="stat-card"><div class="stat-value">${s.devices || 0}</div><div class="stat-label">Devices</div></div>
        <div class="stat-card"><div class="stat-value">${s.facts || 0}</div><div class="stat-label">Facts Learned</div></div>`;
    } catch (e) {
      grid.innerHTML = `<div class="text-muted text-sm">Error: ${JARVIS.esc(e.message)}</div>`;
    }
  }

  // ── FACTS ─────────────────────────────────────────────
  async function loadFacts() {
    const grid = document.getElementById('facts-grid');
    if (!grid) return;
    grid.innerHTML = '<div class="text-muted text-sm" style="padding:8px">Loading…</div>';
    try {
      const data = await JARVIS.api('/admin/memory');
      factsData  = Object.entries(data.facts || {});
      renderFacts(factsData);
    } catch (e) {
      grid.innerHTML = `<div class="text-muted text-sm">Error: ${JARVIS.esc(e.message)}</div>`;
    }
  }

  function renderFacts(entries) {
    const grid = document.getElementById('facts-grid');
    if (!grid) return;
    if (!entries.length) {
      grid.innerHTML = '<div class="text-muted text-sm" style="padding:8px">No facts learned yet.</div>';
      return;
    }
    grid.innerHTML = entries.map(([k, v]) => `
      <div class="fact-row">
        <div class="fact-key">${JARVIS.esc(k)}</div>
        <div class="fact-value">${JARVIS.esc(v)}</div>
      </div>`).join('');
  }

  function filterFacts(query) {
    if (!query) { renderFacts(factsData); return; }
    const q = query.toLowerCase();
    renderFacts(factsData.filter(([k,v]) => k.toLowerCase().includes(q) || v.toLowerCase().includes(q)));
  }

  // ── DEVICES ───────────────────────────────────────────
  async function loadDevices() {
    const list = document.getElementById('devices-list');
    if (!list) return;
    try {
      const data = await JARVIS.api('/admin/memory');
      const devices = data.devices || [];
      if (!devices.length) {
        list.innerHTML = '<div class="text-muted text-sm" style="padding:8px">No devices connected yet.</div>';
        return;
      }
      list.innerHTML = devices.map(d => `
        <div class="device-row">
          <div class="device-icon">${getDeviceIcon(d.name || '')}</div>
          <div class="device-info">
            <div class="device-name">${JARVIS.esc(d.name || 'Unknown Device')}</div>
            <div class="device-owner">Owner: ${JARVIS.esc(d.owner || 'Unknown')}</div>
          </div>
          <div class="device-count">${d.message_count || 0} msgs</div>
        </div>`).join('');
    } catch {}
  }

  function getDeviceIcon(name) {
    const n = name.toLowerCase();
    if (n.includes('samsung') || n.includes('android') || n.includes('iphone')) return '📱';
    if (n.includes('ipad') || n.includes('tablet')) return '📟';
    if (n.includes('windows') || n.includes('mac') || n.includes('pc')) return '💻';
    return '📡';
  }

  // ── BROADCAST ─────────────────────────────────────────
  async function sendBroadcast() {
    const titleEl   = document.getElementById('broadcast-title');
    const contentEl = document.getElementById('broadcast-content');
    const title   = titleEl?.value?.trim() || 'Family Announcement';
    const content = contentEl?.value?.trim();
    if (!content) { JARVIS.toast('Please enter a message.', 'error'); return; }

    const btn = document.getElementById('broadcast-send-btn');
    if (btn) btn.disabled = true;
    try {
      await JARVIS.api('/admin/announcement', {
        method: 'POST',
        body: JSON.stringify({ title, content }),
      });
      JARVIS.toast('📢 Announcement sent!', 'success');
      if (contentEl) contentEl.value = '';
    } catch (e) {
      JARVIS.toast('Failed: ' + e.message, 'error');
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  // ── MEMORY ACTIONS ────────────────────────────────────
  async function compressMemory() {
    if (!confirm('Compress old messages into archive summaries?')) return;
    try {
      await JARVIS.api('/admin/memory/compress', { method: 'POST' });
      JARVIS.toast('✅ Memory compressed.', 'success');
      loadStats();
    } catch (e) { JARVIS.toast('Compress failed: ' + e.message, 'error'); }
  }

  async function wipeChats() {
    const confirmed = prompt('Type CONFIRM to wipe all chat history:');
    if (confirmed !== 'CONFIRM') { JARVIS.toast('Cancelled.'); return; }
    try {
      await JARVIS.api('/admin/memory/chats', { method: 'DELETE' });
      JARVIS.toast('🗑️ Chat history wiped. Facts preserved.', 'success');
      loadStats();
    } catch (e) { JARVIS.toast('Wipe failed: ' + e.message, 'error'); }
  }

  async function wipeAll() {
    const confirmed = prompt('Type WIPE ALL to reset everything:');
    if (confirmed !== 'WIPE ALL') { JARVIS.toast('Cancelled.'); return; }
    try {
      await JARVIS.api('/admin/memory/all', { method: 'DELETE' });
      JARVIS.toast('🔴 Full reset done.', 'success');
      loadStats();
    } catch (e) { JARVIS.toast('Wipe failed: ' + e.message, 'error'); }
  }

  // ── CHANGE PASSWORD ───────────────────────────────────
  async function changePassword() {
    const user = prompt('Username to change password:');
    if (!user) return;
    const pw = prompt('New password (min 6 chars):');
    if (!pw || pw.length < 6) { JARVIS.toast('Password too short.', 'error'); return; }
    try {
      const data = await JARVIS.api('/admin/change-password', {
        method: 'POST',
        body: JSON.stringify({ username: user, new_password: pw }),
      });
      if (data.success) JARVIS.toast(`✅ Password changed for ${user}`, 'success');
      else JARVIS.toast(data.error || 'Failed.', 'error');
    } catch (e) { JARVIS.toast('Failed: ' + e.message, 'error'); }
  }

  // ── Init ─────────────────────────────────────────────
  function init() {
    document.getElementById('admin-btn')?.addEventListener('click', show);
    document.getElementById('admin-close-btn')?.addEventListener('click', hide);

    document.querySelectorAll('.admin-tab').forEach(btn => {
      btn.addEventListener('click', () => loadTab(btn.dataset.tab));
    });

    document.getElementById('facts-search')?.addEventListener('input', JARVIS.debounce(
      e => filterFacts(e.target.value), 250
    ));

    document.getElementById('broadcast-send-btn')?.addEventListener('click', sendBroadcast);
    document.getElementById('compress-btn')?.addEventListener('click', compressMemory);
    document.getElementById('wipe-chats-btn')?.addEventListener('click', wipeChats);
    document.getElementById('wipe-all-btn')?.addEventListener('click', wipeAll);
    document.getElementById('change-pw-btn')?.addEventListener('click', changePassword);
  }

  return { init, show, hide };
})();
