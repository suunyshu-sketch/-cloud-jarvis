/* ═══════════════════════════════════════════════════════════
   J.A.R.V.I.S — Auth Module
   Login / Register / Verify token on load
   ═══════════════════════════════════════════════════════════ */

JARVIS.auth = (() => {
  let currentTab = 'login';

  // ── Init ──────────────────────────────────────────────
  async function init() {
    const token = JARVIS.storage.get('j_token');
    if (token) {
      // Show loading spinner instead of auth screen while verifying
      const authScreen = document.getElementById('auth-screen');
      const app = document.getElementById('app');
      if (authScreen) authScreen.style.display = 'none';
      if (app) {
        app.classList.remove('hidden');
        app.style.opacity = '0';
      }
      await verifyExistingToken(token);
      if (app) app.style.opacity = '1';
    } else {
      showAuthScreen();
    }
    bindEvents();
  }

  async function verifyExistingToken(token) {
    try {
      const res = await fetch('/auth/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, device_id: JARVIS.getDeviceId() }),
      });
      const data = await res.json();
      if (data.valid && data.user) {
        onLoginSuccess(data.user, token);
      } else {
        JARVIS.storage.remove('j_token');
        showAuthScreen();
      }
    } catch {
      showAuthScreen();
    }
  }

  // ── UI ────────────────────────────────────────────────
  function showAuthScreen() {
    JARVIS.show('auth-screen');
    JARVIS.hide('app');
    setTimeout(() => {
      const inp = document.getElementById('login-username');
      if (inp) inp.focus();
    }, 200);
  }

  function hideAuthScreen() {
    JARVIS.hide('auth-screen');
    JARVIS.show('app');
  }

  function switchTab(tab) {
    currentTab = tab;
    document.querySelectorAll('.auth-tab').forEach(el => el.classList.toggle('active', el.dataset.tab === tab));
    document.getElementById('login-form').classList.toggle('hidden', tab !== 'login');
    document.getElementById('register-form').classList.toggle('hidden', tab !== 'register');
    clearMessages();
  }

  function clearMessages() {
    ['auth-error', 'auth-success'].forEach(id => {
      const el = document.getElementById(id);
      if (el) { el.classList.remove('active'); el.textContent = ''; }
    });
  }

  function showError(msg) {
    const el = document.getElementById('auth-error');
    if (el) { el.textContent = msg; el.classList.add('active'); }
  }
  function showSuccess(msg) {
    const el = document.getElementById('auth-success');
    if (el) { el.textContent = msg; el.classList.add('active'); }
  }

  function setLoading(btnId, loading) {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    btn.classList.toggle('loading', loading);
    btn.disabled = loading;
  }

  // ── Password strength ─────────────────────────────────
  function checkPwStrength(password) {
    let score = 0;
    if (password.length >= 6)  score++;
    if (password.length >= 10) score++;
    if (/[A-Z]/.test(password)) score++;
    if (/[0-9]/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;
    const fill  = document.getElementById('pw-strength-fill');
    const pct   = (score / 5) * 100;
    const color = score <= 1 ? 'var(--red)' : score <= 3 ? 'var(--gold)' : 'var(--green)';
    if (fill) { fill.style.width = pct + '%'; fill.style.background = color; }
    return score;
  }

  // ── Login ─────────────────────────────────────────────
  async function doLogin() {
    clearMessages();
    const username = document.getElementById('login-username')?.value?.trim();
    const password = document.getElementById('login-password')?.value;
    if (!username || !password) { showError('Please enter username and password.'); return; }

    setLoading('login-btn', true);
    try {
      const data = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username, password,
          device_id: JARVIS.getDeviceId(),
          user_agent: navigator.userAgent,
        }),
      }).then(r => r.json());

      if (data.success) {
        JARVIS.storage.set('j_token', data.token);
        onLoginSuccess(data, data.token);
      } else {
        showError(data.error || 'Login failed.');
      }
    } catch (e) {
      showError('Connection failed. Please try again.');
    } finally {
      setLoading('login-btn', false);
    }
  }

  // ── Register ──────────────────────────────────────────
  async function doRegister() {
    clearMessages();
    const username     = document.getElementById('reg-username')?.value?.trim();
    const password     = document.getElementById('reg-password')?.value;
    const display_name = document.getElementById('reg-display')?.value?.trim();
    const knows_member = document.getElementById('reg-knows')?.value?.trim();

    if (!username || !password || !display_name) {
      showError('Please fill in all required fields.'); return;
    }
    if (password.length < 6) { showError('Password must be at least 6 characters.'); return; }

    setLoading('register-btn', true);
    try {
      const data = await fetch('/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, display_name, knows_member, relation: 'guest' }),
      }).then(r => r.json());

      if (data.success) {
        showSuccess(data.message || 'Request sent! Lucky will review soon.');
        setTimeout(() => switchTab('login'), 2500);
      } else {
        showError(data.error || 'Registration failed.');
      }
    } catch {
      showError('Connection failed. Please try again.');
    } finally {
      setLoading('register-btn', false);
    }
  }

  // ── On Login Success ──────────────────────────────────
  function onLoginSuccess(user, token) {
    const displayName  = user.display_name || user.displayName || user.username;
    const role         = user.role || 'guest';
    const familyMember = user.family_member || user.familyMember || '';

    JARVIS.storage.set('j_token',         token);
    JARVIS.storage.set('j_display',       displayName);
    JARVIS.storage.set('j_role',          role);
    JARVIS.storage.set('j_family_member', familyMember);

    hideAuthScreen();
    JARVIS.app?.onLogin({ displayName, role, familyMember });
  }

  // ── Logout ────────────────────────────────────────────
  function logout() {
    ['j_token','j_display','j_role','j_family_member'].forEach(k => JARVIS.storage.remove(k));
    showAuthScreen();
    JARVIS.ws?.close();
    document.getElementById('chat-messages').innerHTML = '';
  }

  // ── Event Binding ─────────────────────────────────────
  function bindEvents() {
    document.querySelectorAll('.auth-tab').forEach(el =>
      el.addEventListener('click', () => switchTab(el.dataset.tab)));

    document.getElementById('login-btn')?.addEventListener('click', doLogin);
    document.getElementById('register-btn')?.addEventListener('click', doRegister);

    // Enter to submit
    document.getElementById('login-password')?.addEventListener('keydown', e => { if(e.key==='Enter') doLogin(); });
    document.getElementById('login-username')?.addEventListener('keydown', e => { if(e.key==='Enter') document.getElementById('login-password')?.focus(); });
    document.getElementById('reg-password')?.addEventListener('input', e => checkPwStrength(e.target.value));

    // Show/hide password toggle
    document.querySelectorAll('[data-toggle-pw]').forEach(btn => {
      btn.addEventListener('click', () => {
        const target = document.getElementById(btn.dataset.togglePw);
        if (!target) return;
        const showing = target.type === 'text';
        target.type = showing ? 'password' : 'text';
        btn.textContent = showing ? '👁' : '🙈';
      });
    });

    // Logout button
    document.getElementById('logout-btn')?.addEventListener('click', logout);
  }

  return { init, logout, onLoginSuccess };
})();
