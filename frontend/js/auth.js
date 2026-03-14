// auth.js
JARVIS.auth = (() => {
  function showAuthScreen() {
    const auth = document.getElementById("auth-screen");
    const app  = document.getElementById("app");
    if (auth) auth.style.display = "flex";
    if (app)  app.classList.add("hidden");
  }

  function showApp(username) {
    const auth = document.getElementById("auth-screen");
    const app  = document.getElementById("app");
    if (auth) auth.style.display = "none";
    if (app)  app.classList.remove("hidden");
    const lbl = document.getElementById("username-label");
    if (lbl) lbl.textContent = username;
    const crown = document.getElementById("user-crown");
    if (crown) crown.style.display = username.toLowerCase() === "lucky" ? "inline" : "none";
    if (username.toLowerCase() === "lucky") {
      const settingsBtn = document.getElementById("btn-settings");
      if (settingsBtn) settingsBtn.style.display = "flex";
    }
  }

  async function verifyExistingToken(token) {
    try {
      const data = await JARVIS.api("/auth/verify");
      if (data.valid) {
        JARVIS.storage.set("j_username", data.username);
        showApp(data.username);
        JARVIS.ws.connect(token);
        return true;
      }
    } catch {
      JARVIS.storage.del("j_token");
      JARVIS.storage.del("j_username");
    }
    showAuthScreen();
    return false;
  }

  function bindEvents() {
    // Tab switching
    document.querySelectorAll(".auth-tab").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".auth-tab").forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".auth-panel").forEach(p => p.classList.remove("active"));
        btn.classList.add("active");
        const tab = btn.dataset.tab;
        const panel = document.getElementById(`tab-${tab}`);
        if (panel) panel.classList.add("active");
      });
    });

    // Login
    const loginBtn = document.getElementById("login-btn");
    if (loginBtn) loginBtn.addEventListener("click", doLogin);

    const loginInputs = ["login-username","login-password"];
    loginInputs.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.addEventListener("keydown", e => { if (e.key === "Enter") doLogin(); });
    });

    // Register
    const regBtn = document.getElementById("reg-btn");
    if (regBtn) regBtn.addEventListener("click", doRegister);

    // Password strength
    const pwInput = document.getElementById("reg-password");
    if (pwInput) pwInput.addEventListener("input", updatePwStrength);

    // Logout
    const logoutBtn = document.getElementById("btn-logout");
    if (logoutBtn) logoutBtn.addEventListener("click", doLogout);

    // Admin open
    const settingsBtn = document.getElementById("btn-settings");
    if (settingsBtn) settingsBtn.addEventListener("click", () => {
      const overlay = document.getElementById("admin-overlay");
      if (overlay) overlay.style.display = "flex";
      if (JARVIS.admin) JARVIS.admin.load();
    });
  }

  async function doLogin() {
    const username = document.getElementById("login-username")?.value.trim();
    const password = document.getElementById("login-password")?.value;
    const errEl    = document.getElementById("login-error");
    const btn      = document.getElementById("login-btn");

    if (!username || !password) {
      if (errEl) errEl.textContent = "Please enter username and password";
      return;
    }

    if (btn) { btn.disabled = true; btn.textContent = "Signing in..."; }
    if (errEl) errEl.textContent = "";

    try {
      const data = await JARVIS.api("/auth/login", "POST", {
        username, password, device_id: JARVIS.uuid()
      });
      JARVIS.storage.set("j_token", data.token);
      JARVIS.storage.set("j_username", data.username);
      showApp(data.username);
      JARVIS.ws.connect(data.token);
    } catch (e) {
      if (errEl) errEl.textContent = "Invalid username or password";
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Sign In"; }
    }
  }

  async function doRegister() {
    const username = document.getElementById("reg-username")?.value.trim();
    const display  = document.getElementById("reg-display")?.value.trim();
    const password = document.getElementById("reg-password")?.value;
    const msgEl    = document.getElementById("reg-msg");
    const btn      = document.getElementById("reg-btn");

    if (!username || !password) {
      if (msgEl) { msgEl.style.color = "var(--red)"; msgEl.textContent = "Please fill all fields"; }
      return;
    }

    if (btn) { btn.disabled = true; btn.textContent = "Registering..."; }
    try {
      await JARVIS.api("/auth/register", "POST", { username, password, display_name: display });
      if (msgEl) {
        msgEl.style.color = "var(--green)";
        msgEl.textContent = "Registered! Waiting for admin approval.";
      }
    } catch {
      if (msgEl) { msgEl.style.color = "var(--red)"; msgEl.textContent = "Username already taken"; }
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = "Register"; }
    }
  }

  function doLogout() {
    JARVIS.storage.del("j_token");
    JARVIS.storage.del("j_username");
    if (JARVIS.ws) JARVIS.ws.disconnect();
    showAuthScreen();
  }

  function updatePwStrength() {
    const pw = document.getElementById("reg-password")?.value || "";
    const bar = document.getElementById("pw-bar");
    if (!bar) return;
    let score = 0;
    if (pw.length >= 6) score++;
    if (pw.length >= 10) score++;
    if (/[A-Z]/.test(pw)) score++;
    if (/[0-9]/.test(pw)) score++;
    if (/[^A-Za-z0-9]/.test(pw)) score++;
    const colors = ["#ff4466","#ff6644","#ffaa00","#88cc00","#00ff88"];
    bar.style.width = (score * 20) + "%";
    bar.style.background = colors[score - 1] || "#ff4466";
  }

  async function init() {
    const token = JARVIS.storage.get("j_token");
    if (token) {
      await verifyExistingToken(token);
    } else {
      showAuthScreen();
    }
    bindEvents();
  }

  return { init, showAuthScreen, showApp };
})();
