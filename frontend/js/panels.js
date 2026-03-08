/* ═══════════════════════════════════════════════════════════
   J.A.R.V.I.S — Panels Module
   Todos, Notes, Reminders, Birthdays — right panel + mobile sheets.
   ═══════════════════════════════════════════════════════════ */

JARVIS.panels = (() => {
  let activePanel = null;
  const DEVICE_ID = () => JARVIS.getDeviceId();

  // ── Panel switching ────────────────────────────────────
  function showPanel(name) {
    const rightPanel = document.getElementById('right-panel');
    if (!rightPanel) return;

    if (activePanel === name && rightPanel.classList.contains('open')) {
      rightPanel.classList.remove('open');
      activePanel = null;
      return;
    }

    activePanel = name;
    document.querySelectorAll('.panel-tab-btn').forEach(btn =>
      btn.classList.toggle('active', btn.dataset.panel === name));

    document.querySelectorAll('.panel-section').forEach(sec =>
      sec.classList.toggle('hidden', sec.dataset.panel !== name));

    rightPanel.classList.add('open');

    // Load data for the active panel
    if (name === 'todos')     loadTodos();
    if (name === 'notes')     loadNotes();
    if (name === 'reminders') loadReminders();
    if (name === 'music')     { /* music loads on search */ }
    if (name === 'birthdays') loadBirthdays();
  }

  // ── TODOS ─────────────────────────────────────────────
  async function loadTodos() {
    const list = document.getElementById('todo-list');
    if (!list) return;
    list.innerHTML = '<div class="text-muted text-sm" style="padding:8px">Loading…</div>';
    try {
      const data = await JARVIS.api(`/todos/${DEVICE_ID()}`);
      renderTodos(data.todos || []);
    } catch (e) {
      list.innerHTML = '<div class="text-muted text-sm" style="padding:8px">Failed to load.</div>';
    }
  }

  function renderTodos(todos) {
    const list = document.getElementById('todo-list');
    if (!list) return;
    if (!todos.length) {
      list.innerHTML = '<div class="text-muted text-sm" style="text-align:center;padding:20px">No tasks. Say "todo: buy milk" to add one!</div>';
      return;
    }
    list.innerHTML = todos.map(t => `
      <div class="todo-item ${t.done ? 'done' : ''}" data-id="${t.id}">
        <div class="todo-check" data-toggle="${t.id}"></div>
        <div class="todo-text">${JARVIS.esc(t.text)}</div>
        <div class="todo-cat-badge">${JARVIS.esc(t.category || 'general')}</div>
        <button class="todo-del" data-del="${t.id}" title="Delete">✕</button>
      </div>`).join('');

    list.querySelectorAll('[data-toggle]').forEach(el => {
      el.addEventListener('click', () => toggleTodo(el.dataset.toggle));
    });
    list.querySelectorAll('[data-del]').forEach(el => {
      el.addEventListener('click', (e) => { e.stopPropagation(); deleteTodo(el.dataset.del); });
    });
  }

  async function addTodo() {
    const input = document.getElementById('todo-add-input');
    const text  = input?.value?.trim();
    if (!text) return;
    try {
      await JARVIS.api('/todos', {
        method: 'POST',
        body: JSON.stringify({ text, device_id: DEVICE_ID() }),
      });
      input.value = '';
      loadTodos();
    } catch (e) { JARVIS.toast('Failed to add task.', 'error'); }
  }

  async function toggleTodo(id) {
    try {
      await JARVIS.api(`/todos/toggle/${id}`, { method: 'POST' });
      loadTodos();
    } catch (e) { JARVIS.toast('Failed to update task.', 'error'); }
  }

  async function deleteTodo(id) {
    try {
      await JARVIS.api(`/todos/${id}`, { method: 'DELETE' });
      loadTodos();
    } catch (e) { JARVIS.toast('Failed to delete task.', 'error'); }
  }

  // ── NOTES ─────────────────────────────────────────────
  async function loadNotes() {
    const list = document.getElementById('notes-list');
    if (!list) return;
    list.innerHTML = '<div class="text-muted text-sm" style="padding:8px">Loading…</div>';
    try {
      const data = await JARVIS.api(`/notes/${DEVICE_ID()}`);
      renderNotes(data.notes || []);
    } catch {
      list.innerHTML = '<div class="text-muted text-sm">Failed to load.</div>';
    }
  }

  function renderNotes(notes) {
    const list = document.getElementById('notes-list');
    if (!list) return;
    if (!notes.length) {
      list.innerHTML = '<div class="text-muted text-sm" style="text-align:center;padding:20px">No notes. Say "note: ..." to save one!</div>';
      return;
    }
    list.innerHTML = notes.map(n => `
      <div class="note-item" data-id="${n.id}">
        <div class="note-item-title">${JARVIS.esc(n.title || 'Untitled')}</div>
        <div class="note-item-preview">${JARVIS.esc((n.content || '').substring(0, 80))}${(n.content||'').length>80?'…':''}</div>
      </div>`).join('');
  }

  async function addNote() {
    const titleEl   = document.getElementById('note-title-input');
    const contentEl = document.getElementById('note-content-input');
    const title   = titleEl?.value?.trim();
    const content = contentEl?.value?.trim();
    if (!content) return;
    try {
      await JARVIS.api('/notes', {
        method: 'POST',
        body: JSON.stringify({ title: title || content.substring(0,30), content, device_id: DEVICE_ID() }),
      });
      if (titleEl)   titleEl.value   = '';
      if (contentEl) contentEl.value = '';
      loadNotes();
    } catch { JARVIS.toast('Failed to save note.', 'error'); }
  }

  // ── REMINDERS ─────────────────────────────────────────
  async function loadReminders() {
    const list = document.getElementById('reminders-list');
    if (!list) return;
    try {
      const data = await JARVIS.api(`/reminders/${DEVICE_ID()}`);
      renderReminders(data.reminders || []);
    } catch {
      list.innerHTML = '<div class="text-muted text-sm">Failed to load.</div>';
    }
  }

  function renderReminders(reminders) {
    const list = document.getElementById('reminders-list');
    if (!list) return;
    if (!reminders.length) {
      list.innerHTML = '<div class="text-muted text-sm" style="text-align:center;padding:20px">No reminders. Say "remind me at 6pm to..." to set one!</div>';
      return;
    }
    list.innerHTML = reminders.map(r => `
      <div class="reminder-item">
        <div class="reminder-time">⏰ ${new Date(r.time).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',hour12:true})}</div>
        <div class="reminder-text">${JARVIS.esc(r.text)}</div>
      </div>`).join('');
  }

  // ── BIRTHDAYS ─────────────────────────────────────────
  async function loadBirthdays() {
    const list = document.getElementById('birthdays-list');
    if (!list) return;
    try {
      const data = await JARVIS.api('/birthdays');
      renderBirthdays(data.upcoming || []);
    } catch {
      list.innerHTML = '<div class="text-muted text-sm">Failed to load.</div>';
    }
  }

  function renderBirthdays(bdays) {
    const list = document.getElementById('birthdays-list');
    if (!list) return;
    if (!bdays.length) {
      list.innerHTML = '<div class="text-muted text-sm" style="text-align:center;padding:20px">No upcoming birthdays in next 30 days. Say "Dad\'s birthday is March 15" to add one!</div>';
      return;
    }
    list.innerHTML = bdays.map(b => `
      <div class="reminder-item" style="border-left-color:var(--pink)">
        <div class="reminder-time" style="color:var(--pink)">🎂 ${b.days_until === 0 ? 'TODAY!' : b.days_until + 'd'}</div>
        <div class="reminder-text">${JARVIS.esc(b.name)}'s Birthday<br><span class="text-xs text-muted">${b.next_birthday}</span></div>
      </div>`).join('');
  }

  // ── Private mode ──────────────────────────────────────
  function togglePrivate() {
    const current = JARVIS.storage.get('j_private') || false;
    const next    = !current;
    JARVIS.storage.set('j_private', next);

    const toggle = document.getElementById('private-toggle');
    const banner = document.getElementById('private-banner');
    if (toggle) toggle.classList.toggle('on', next);
    if (banner) banner.classList.toggle('active', next);

    JARVIS.toast(next ? '🔒 Private mode ON' : '🔓 Private mode OFF');
  }

  // ── Init ─────────────────────────────────────────────
  function init() {
    // Panel tab buttons
    document.querySelectorAll('.panel-tab-btn').forEach(btn => {
      btn.addEventListener('click', () => showPanel(btn.dataset.panel));
    });

    // Header quick-access buttons
    document.getElementById('btn-show-todos')?.addEventListener('click', () => showPanel('todos'));
    document.getElementById('btn-show-notes')?.addEventListener('click', () => showPanel('notes'));
    document.getElementById('btn-show-music')?.addEventListener('click', () => showPanel('music'));

    // Add buttons
    document.getElementById('todo-add-btn')?.addEventListener('click', addTodo);
    document.getElementById('todo-add-input')?.addEventListener('keydown', e => { if(e.key==='Enter') addTodo(); });

    document.getElementById('note-add-btn')?.addEventListener('click', addNote);

    // Private mode
    document.getElementById('private-toggle-row')?.addEventListener('click', togglePrivate);

    // Restore private mode state
    const isPrivate = JARVIS.storage.get('j_private') || false;
    document.getElementById('private-toggle')?.classList.toggle('on', isPrivate);
    document.getElementById('private-banner')?.classList.toggle('active', isPrivate);
  }

  return { init, showPanel, loadTodos, loadNotes, loadReminders };
})();
