// panels.js
JARVIS.panels = (() => {
  function openPanel(type, title) {
    const panel = document.getElementById("right-panel");
    const titleEl = document.getElementById("panel-title");
    if (panel) panel.classList.remove("panel-hidden");
    if (titleEl) titleEl.textContent = title;
  }

  function closePanel() {
    const panel = document.getElementById("right-panel");
    if (panel) panel.classList.add("panel-hidden");
  }

  function setContent(html) {
    const content = document.getElementById("panel-content");
    if (content) content.innerHTML = html;
  }

  // ── TODOS ────────────────────────────────────
  async function loadTodos() {
    openPanel("todos", "📋 Todos");
    const content = document.getElementById("panel-content");
    if (!content) return;
    content.innerHTML = `<div style="color:#4a6680;font-size:0.85rem;">Loading...</div>`;

    try {
      const todos = await JARVIS.api("/todos/");
      content.innerHTML = "";

      // Add input
      const addRow = document.createElement("div");
      addRow.className = "panel-add";
      const inp = document.createElement("input");
      inp.placeholder = "Add a todo...";
      const btn = document.createElement("button");
      btn.textContent = "Add";
      btn.addEventListener("click", async () => {
        if (!inp.value.trim()) return;
        await JARVIS.api("/todos/", "POST", { text: inp.value.trim() });
        loadTodos();
      });
      inp.addEventListener("keydown", e => { if (e.key === "Enter") btn.click(); });
      addRow.appendChild(inp);
      addRow.appendChild(btn);
      content.appendChild(addRow);

      if (!todos.length) {
        const empty = document.createElement("div");
        empty.style.cssText = "color:#4a6680;font-size:0.85rem;text-align:center;padding:20px;";
        empty.textContent = "No todos yet!";
        content.appendChild(empty);
        return;
      }

      todos.forEach(todo => {
        const item = document.createElement("div");
        item.className = "panel-item" + (todo.done ? " done" : "");
        item.style.cssText = "display:flex;align-items:center;gap:10px;padding:10px;background:#1a2236;border:1px solid rgba(0,212,255,0.12);border-radius:8px;margin-bottom:6px;font-size:0.88rem;";

        const text = document.createElement("span");
        text.textContent = todo.text;
        text.style.cssText = "flex:1;color:#e8f4f8;" + (todo.done ? "text-decoration:line-through;opacity:0.5;" : "");

        const toggleBtn = document.createElement("button");
        toggleBtn.textContent = todo.done ? "↩" : "✓";
        toggleBtn.style.cssText = "color:#00ff88;font-size:1rem;width:28px;height:28px;border-radius:6px;background:rgba(0,255,136,0.08);border:1px solid rgba(0,255,136,0.2);cursor:pointer;";
        toggleBtn.addEventListener("click", async () => {
          await JARVIS.api(`/todos/${todo.id}/toggle`, "PATCH");
          loadTodos();
        });

        const delBtn = document.createElement("button");
        delBtn.textContent = "✕";
        delBtn.style.cssText = "color:#ff4466;font-size:0.8rem;width:28px;height:28px;border-radius:6px;background:rgba(255,68,102,0.08);border:1px solid rgba(255,68,102,0.2);cursor:pointer;";
        delBtn.addEventListener("click", async () => {
          await JARVIS.api(`/todos/${todo.id}`, "DELETE");
          loadTodos();
        });

        item.appendChild(text);
        item.appendChild(toggleBtn);
        item.appendChild(delBtn);
        content.appendChild(item);
      });
    } catch {
      if (content) content.innerHTML = `<div style="color:#ff4466;font-size:0.85rem;">Failed to load todos</div>`;
    }
  }

  // ── NOTES ────────────────────────────────────
  async function loadNotes() {
    openPanel("notes", "📝 Notes");
    const content = document.getElementById("panel-content");
    if (!content) return;
    content.innerHTML = `<div style="color:#4a6680;font-size:0.85rem;">Loading...</div>`;

    try {
      const notes = await JARVIS.api("/notes/");
      content.innerHTML = "";

      const addRow = document.createElement("div");
      addRow.style.cssText = "display:flex;flex-direction:column;gap:6px;margin-bottom:12px;";

      const titleInp = document.createElement("input");
      titleInp.placeholder = "Note title...";
      titleInp.style.cssText = "padding:8px 12px;background:#1a2236;border:1px solid rgba(0,212,255,0.12);border-radius:8px;font-size:0.88rem;color:#e8f4f8;outline:none;";

      const bodyInp = document.createElement("textarea");
      bodyInp.placeholder = "Note content...";
      bodyInp.style.cssText = "padding:8px 12px;background:#1a2236;border:1px solid rgba(0,212,255,0.12);border-radius:8px;font-size:0.88rem;color:#e8f4f8;outline:none;resize:vertical;min-height:60px;";

      const saveBtn = document.createElement("button");
      saveBtn.textContent = "Save Note";
      saveBtn.style.cssText = "padding:8px;background:rgba(0,212,255,0.12);border:1px solid rgba(0,212,255,0.25);border-radius:8px;color:#00d4ff;font-weight:600;cursor:pointer;";
      saveBtn.addEventListener("click", async () => {
        if (!titleInp.value.trim()) return;
        await JARVIS.api("/notes/", "POST", { title: titleInp.value.trim(), content: bodyInp.value.trim() });
        loadNotes();
      });

      addRow.appendChild(titleInp);
      addRow.appendChild(bodyInp);
      addRow.appendChild(saveBtn);
      content.appendChild(addRow);

      if (!notes.length) {
        const empty = document.createElement("div");
        empty.style.cssText = "color:#4a6680;font-size:0.85rem;text-align:center;padding:20px;";
        empty.textContent = "No notes yet!";
        content.appendChild(empty);
        return;
      }

      notes.forEach(note => {
        const item = document.createElement("div");
        item.style.cssText = "padding:10px;background:#1a2236;border:1px solid rgba(0,212,255,0.12);border-radius:8px;margin-bottom:6px;";

        const header = document.createElement("div");
        header.style.cssText = "display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;";

        const title = document.createElement("span");
        title.textContent = note.title;
        title.style.cssText = "font-weight:600;font-size:0.88rem;color:#e8f4f8;";

        const delBtn = document.createElement("button");
        delBtn.textContent = "✕";
        delBtn.style.cssText = "color:#ff4466;font-size:0.75rem;cursor:pointer;";
        delBtn.addEventListener("click", async () => {
          await JARVIS.api(`/notes/${note.id}`, "DELETE");
          loadNotes();
        });

        header.appendChild(title);
        header.appendChild(delBtn);

        const body = document.createElement("div");
        body.textContent = note.content;
        body.style.cssText = "font-size:0.82rem;color:#7a9ab8;white-space:pre-wrap;";

        item.appendChild(header);
        item.appendChild(body);
        content.appendChild(item);
      });
    } catch {
      if (content) content.innerHTML = `<div style="color:#ff4466;font-size:0.85rem;">Failed to load notes</div>`;
    }
  }

  // ── REMINDERS ────────────────────────────────
  async function loadReminders() {
    openPanel("reminders", "⏰ Reminders");
    const content = document.getElementById("panel-content");
    if (!content) return;
    content.innerHTML = `<div style="color:#4a6680;font-size:0.85rem;">Loading...</div>`;

    try {
      const reminders = await JARVIS.api("/reminders/");
      content.innerHTML = "";

      const hint = document.createElement("div");
      hint.style.cssText = "font-size:0.78rem;color:#4a6680;margin-bottom:10px;";
      hint.textContent = 'Say "Remind me at 6pm to call doctor" to add reminders via chat.';
      content.appendChild(hint);

      if (!reminders.length) {
        const empty = document.createElement("div");
        empty.style.cssText = "color:#4a6680;font-size:0.85rem;text-align:center;padding:20px;";
        empty.textContent = "No reminders yet!";
        content.appendChild(empty);
        return;
      }

      reminders.forEach(r => {
        const item = document.createElement("div");
        item.style.cssText = "padding:10px;background:#1a2236;border:1px solid rgba(0,212,255,0.12);border-radius:8px;margin-bottom:6px;";

        const text = document.createElement("div");
        text.textContent = r.text;
        text.style.cssText = "font-size:0.88rem;color:#e8f4f8;margin-bottom:4px;";

        const time = document.createElement("div");
        const dt = new Date(r.remind_at);
        time.textContent = "⏰ " + dt.toLocaleString("en-IN", { dateStyle: "short", timeStyle: "short" });
        time.style.cssText = "font-size:0.78rem;color:#00d4ff;";

        item.appendChild(text);
        item.appendChild(time);
        content.appendChild(item);
      });
    } catch {
      if (content) content.innerHTML = `<div style="color:#ff4466;font-size:0.85rem;">Failed to load reminders</div>`;
    }
  }

  function init() {
    const todosBtn = document.getElementById("btn-todos");
    const notesBtn = document.getElementById("btn-notes");
    const closeBtn = document.getElementById("panel-close");

    if (todosBtn) todosBtn.addEventListener("click", loadTodos);
    if (notesBtn) notesBtn.addEventListener("click", loadNotes);
    if (closeBtn) closeBtn.addEventListener("click", closePanel);
  }

  return { init, openPanel, closePanel, loadTodos, loadNotes, loadReminders };
})();
