/* ═══════════════════════════════════════════════════════════
   J.A.R.V.I.S — Main Application Entry Point
   Initialises all modules after DOM ready.
   ═══════════════════════════════════════════════════════════ */

JARVIS.app = (() => {
  function onLogin(user) {
    const { displayName, role, familyMember } = user;

    // Update header user pill
    const pill  = document.getElementById('user-display-name');
    const emoji = document.getElementById('user-emoji');
    const member = (familyMember || displayName || '').toLowerCase();

    const roleEmoji = { lucky: '👑', krishna: '👨', sangeetha: '👩', thapaswini: '👧', dhruva: '👦', prajwal: '👦' };
    if (pill)  pill.textContent  = displayName || 'User';
    if (emoji) emoji.textContent = roleEmoji[member] || '👤';

    // Show admin button for Lucky
    if (role === 'admin') {
      JARVIS.show('admin-btn');
    } else {
      JARVIS.hide('admin-btn');
    }

    // Connect WebSocket
    JARVIS.ws.connect();

    // Update welcome screen
    const welcomeSub = document.getElementById('welcome-sub');
    if (welcomeSub) {
      welcomeSub.textContent = `Welcome back, ${displayName}! I remember everything about you. What's on your mind?`;
    }
  }

  function init() {
    // Init all modules
    JARVIS.chat.init();
    JARVIS.voice.init();
    JARVIS.music.init();
    JARVIS.panels.init();
    JARVIS.admin.init();

    // Auth (triggers login or restores session)
    JARVIS.auth.init();

    // Theme toggle
    document.getElementById('theme-btn')?.addEventListener('click', () => {
      document.body.classList.toggle('light-theme');
      const isDark = !document.body.classList.contains('light-theme');
      JARVIS.storage.set('j_theme', isDark ? 'dark' : 'light');
    });

    // Apply saved theme
    const savedTheme = JARVIS.storage.get('j_theme');
    if (savedTheme === 'light') document.body.classList.add('light-theme');

    // Close right panel on backdrop click (mobile)
    document.getElementById('panel-overlay')?.addEventListener('click', () => {
      document.getElementById('right-panel')?.classList.remove('open');
    });
  }

  return { init, onLogin };
})();

// ── Boot ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => JARVIS.app.init());
