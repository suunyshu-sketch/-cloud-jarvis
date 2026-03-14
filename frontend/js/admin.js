// admin.js
JARVIS.admin = (() => {
  let _currentTab = "users";

  function init() {
    const closeBtn = document.getElementById("admin-close");
    if (closeBtn) closeBtn.addEventListener("click", () => {
      const overlay = document.getElementById("admin-overlay");
      if (overlay) { overlay.setAttribute("hidden",""); overlay.style.display = "none"; }
    });

    document.querySelectorAll(".a-tab").forEach(tab => {
      tab.addEventListener("click", () => {
        document.querySelectorAll(".a-tab").forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        _currentTab = tab.dataset.t;
        _loadTab(_currentTab);
      });
    });
  }

  function load() {
    _loadTab(_currentTab);
  }

  function _loadTab(tab) {
    const body = document.getElementById("admin-body");
    if (!body) return;
    body.innerHTML = `<div style="color:#4a6680;font-size:0.85rem;text-align:center;padding:20px;">Loading...</div>`;

    switch (tab) {
      case "users":     _loadUsers(); break;
      case "stats":     _loadStats(); break;
      case "facts":     _loadFacts(); break;
      case "broadcast": _loadBroadcast(); break;
      case "danger":    _loadDanger(); break;
    }
  }

  async function _loadUsers() {
    const body = document.getElementById("admin-body");
    try {
      const users = await JARVIS.api("/admin/users");
      const pending = users.filter(u => !u.approved);
      const approved = users.filter(u => u.approved);

      body.innerHTML = "";

      if (pending.length) {
        const h = document.createElement("div");
        h.style.cssText = "font-size:0.8rem;color:#ffaa00;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;font-weight:700;";
        h.textContent = "Pending Approval";
        body.appendChild(h);

        pending.forEach(u => {
          const row = _userRow(u, true);
          body.appendChild(row);
        });

        const div = document.createElement("div");
        div.style.cssText = "font-size:0.8rem;color:#4a6680;text-transform:uppercase;letter-spacing:1px;margin:12px 0 8px;font-weight:700;";
        div.textContent = "Approved Members";
        body.appendChild(div);
      }

      approved.forEach(u => {
        const row = _userRow(u, false);
        body.appendChild(row);
      });
    } catch {
      body.innerHTML = `<div style="color:#ff4466;">Failed to load users</div>`;
    }
  }

  function _userRow(u, showApprove) {
    const row = document.createElement("div");
    row.className = "admin-user-row";
    row.style.cssText = "display:flex;align-items:center;gap:12px;padding:12px;background:#1a2236;border:1px solid rgba(0,212,255,0.12);border-radius:8px;margin-bottom:6px;";

    const info = document.createElement("div");
    info.style.cssText = "flex:1;";

    const name = document.createElement("div");
    name.style.cssText = "font-weight:600;color:#e8f4f8;font-size:0.9rem;";
    name.textContent = u.display_name || u.username;

    const meta = document.createElement("div");
    meta.style.cssText = "font-size:0.75rem;color:#4a6680;margin-top:2px;";
    meta.textContent = `@${u.username} | ${u.role} | Logins: ${u.login_count || 0}`;

    info.appendChild(name);
    info.appendChild(meta);
    row.appendChild(info);

    if (showApprove) {
      const approveBtn = document.createElement("button");
      approveBtn.textContent = "Approve";
      approveBtn.style.cssText = "padding:6px 12px;background:#00ff88;color:#0a0e17;border-radius:6px;font-size:0.82rem;font-weight:700;cursor:pointer;";
      approveBtn.addEventListener("click", async () => {
        await JARVIS.api("/admin/approve", "POST", { username: u.username });
        JARVIS.toast(`${u.username} approved!`, "success");
        _loadUsers();
      });
      row.appendChild(approveBtn);
    }

    return row;
  }

  async function _loadStats() {
    const body = document.getElementById("admin-body");
    try {
      const stats = await JARVIS.api("/admin/stats");
      body.innerHTML = "";

      const grid = document.createElement("div");
      grid.style.cssText = "display:grid;grid-template-columns:1fr 1fr;gap:10px;";

      const items = [
        { label: "Messages", value: stats.total_messages || 0 },
        { label: "Facts", value: stats.total_facts || 0 },
        { label: "Archives", value: stats.archive_entries || 0 },
        { label: "Feedback", value: stats.total_feedback || 0 },
      ];

      items.forEach(item => {
        const card = document.createElement("div");
        card.style.cssText = "padding:14px;background:#1a2236;border:1px solid rgba(0,212,255,0.12);border-radius:8px;text-align:center;";

        const num = document.createElement("div");
        num.textContent = item.value.toLocaleString();
        num.style.cssText = "font-size:1.6rem;font-weight:700;color:#00d4ff;";

        const lbl = document.createElement("div");
        lbl.textContent = item.label;
        lbl.style.cssText = "font-size:0.75rem;color:#4a6680;margin-top:2px;";

        card.appendChild(num);
        card.appendChild(lbl);
        grid.appendChild(card);
      });

      body.appendChild(grid);
    } catch {
      body.innerHTML = `<div style="color:#ff4466;">Failed to load stats</div>`;
    }
  }

  async function _loadFacts() {
    const body = document.getElementById("admin-body");
    try {
      const facts = await JARVIS.api("/admin/facts");
      body.innerHTML = "";

      const searchInp = document.createElement("input");
      searchInp.placeholder = "Search facts...";
      searchInp.style.cssText = "width:100%;padding:8px 12px;background:#1a2236;border:1px solid rgba(0,212,255,0.12);border-radius:8px;color:#e8f4f8;font-size:0.85rem;outline:none;margin-bottom:10px;";

      const list = document.createElement("div");
      const entries = Object.entries(facts);

      function renderFacts(filter = "") {
        list.innerHTML = "";
        entries.filter(([k, v]) => !filter || k.includes(filter) || v.includes(filter))
          .forEach(([key, val]) => {
            const row = document.createElement("div");
            row.style.cssText = "display:flex;gap:10px;padding:8px 10px;background:#1a2236;border-radius:6px;margin-bottom:4px;font-size:0.83rem;";

            const k = document.createElement("span");
            k.textContent = key;
            k.style.cssText = "color:#00d4ff;min-width:130px;word-break:break-all;";

            const v = document.createElement("span");
            v.textContent = val;
            v.style.cssText = "color:#7a9ab8;flex:1;word-break:break-all;";

            row.appendChild(k);
            row.appendChild(v);
            list.appendChild(row);
          });
      }

      searchInp.addEventListener("input", () => renderFacts(searchInp.value.trim().toLowerCase()));
      renderFacts();

      body.appendChild(searchInp);
      body.appendChild(list);
    } catch {
      body.innerHTML = `<div style="color:#ff4466;">Failed to load facts</div>`;
    }
  }

  function _loadBroadcast() {
    const body = document.getElementById("admin-body");
    body.innerHTML = "";

    const wrap = document.createElement("div");
    wrap.style.cssText = "display:flex;flex-direction:column;gap:10px;";

    const label = document.createElement("div");
    label.textContent = "Send a message to all family members:";
    label.style.cssText = "font-size:0.85rem;color:#7a9ab8;";

    const ta = document.createElement("textarea");
    ta.placeholder = "Type your announcement...";
    ta.style.cssText = "padding:12px;background:#1a2236;border:1px solid rgba(0,212,255,0.12);border-radius:8px;color:#e8f4f8;font-size:0.88rem;resize:vertical;min-height:80px;outline:none;";

    const sendBtn = document.createElement("button");
    sendBtn.textContent = "Send Broadcast";
    sendBtn.style.cssText = "padding:10px;background:rgba(0,212,255,0.12);border:1px solid rgba(0,212,255,0.25);border-radius:8px;color:#00d4ff;font-weight:700;cursor:pointer;";
    sendBtn.addEventListener("click", async () => {
      if (!ta.value.trim()) return;
      await JARVIS.api("/admin/broadcast", "POST", { message: ta.value.trim() });
      JARVIS.toast("Broadcast sent!", "success");
      ta.value = "";
    });

    wrap.appendChild(label);
    wrap.appendChild(ta);
    wrap.appendChild(sendBtn);
    body.appendChild(wrap);
  }

  function _loadDanger() {
    const body = document.getElementById("admin-body");
    body.innerHTML = "";

    const warn = document.createElement("div");
    warn.style.cssText = "font-size:0.82rem;color:#ff4466;margin-bottom:14px;padding:10px;background:rgba(255,68,102,0.08);border:1px solid rgba(255,68,102,0.2);border-radius:8px;";
    warn.textContent = "⚠️ These actions are irreversible. Type the confirmation text exactly before proceeding.";
    body.appendChild(warn);

    _dangerAction(body, "Wipe Chat History", "Type CONFIRM to wipe all chats", "CONFIRM", async () => {
      await JARVIS.api("/admin/wipe-chats", "POST");
      JARVIS.toast("Chat history wiped", "success");
    });

    _dangerAction(body, "Wipe ALL Data", "Type WIPE ALL to delete everything", "WIPE ALL", async () => {
      await JARVIS.api("/admin/wipe-all", "POST");
      JARVIS.toast("All data wiped", "success");
    });
  }

  function _dangerAction(parent, title, placeholder, confirmation, action) {
    const wrap = document.createElement("div");
    wrap.style.cssText = "margin-bottom:14px;";

    const h = document.createElement("div");
    h.textContent = title;
    h.style.cssText = "font-weight:600;color:#ff4466;font-size:0.88rem;margin-bottom:6px;";

    const inp = document.createElement("input");
    inp.placeholder = placeholder;
    inp.style.cssText = "width:100%;padding:9px 12px;background:#1a2236;border:1px solid rgba(255,68,102,0.3);border-radius:8px;color:#e8f4f8;font-size:0.88rem;outline:none;margin-bottom:6px;";

    const btn = document.createElement("button");
    btn.textContent = title;
    btn.style.cssText = "width:100%;padding:10px;background:rgba(255,68,102,0.12);border:1px solid rgba(255,68,102,0.3);border-radius:8px;color:#ff4466;font-weight:700;font-size:0.85rem;cursor:pointer;";
    btn.addEventListener("click", async () => {
      if (inp.value.trim() !== confirmation) {
        JARVIS.toast(`Type "${confirmation}" exactly`, "error");
        return;
      }
      await action();
      inp.value = "";
    });

    wrap.appendChild(h);
    wrap.appendChild(inp);
    wrap.appendChild(btn);
    parent.appendChild(wrap);
  }

  return { init, load };
})();
