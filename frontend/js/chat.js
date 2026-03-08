/* ═══════════════════════════════════════════════════════════
   J.A.R.V.I.S — Chat Module
   Message rendering, streaming, image upload, feedback.
   ═══════════════════════════════════════════════════════════ */

JARVIS.chat = (() => {
  let streamingEl       = null;   // Current streaming bubble
  let streamingText     = '';     // Full streamed text so far
  let lastJarvisMsg     = '';     // For feedback
  let lastUserMsg       = '';     // For feedback
  let pendingImageB64   = null;
  let pendingImageBlob  = null;
  const msgList         = () => document.getElementById('chat-messages');
  const welcome         = () => document.getElementById('welcome-screen');

  // ── Add User Message ──────────────────────────────────
  function addUserMessage(text, imageBlob = null) {
    lastUserMsg = text;
    hideWelcome();

    const el = document.createElement('div');
    el.className = 'msg user fade-in';
    el.innerHTML = `
      <div class="msg-avatar" style="border-color:rgba(255,215,0,0.3)">
        ${getUserEmoji()}
      </div>
      <div class="msg-body">
        ${imageBlob ? `<img class="msg-image" src="${URL.createObjectURL(imageBlob)}" alt="image">` : ''}
        ${text ? `<div class="msg-bubble">${JARVIS.formatMsg(text)}</div>` : ''}
        <div class="msg-meta">${JARVIS.fmtTime()}</div>
      </div>`;
    msgList().appendChild(el);
    scrollToBottom();
  }

  // ── Thinking Indicator ────────────────────────────────
  function showThinking() {
    removeThinking();
    const el = document.createElement('div');
    el.className = 'msg jarvis';
    el.id = 'thinking-indicator';
    el.innerHTML = `
      <div class="msg-avatar">🤖</div>
      <div class="msg-body">
        <div class="thinking-dots">
          <span></span><span></span><span></span>
        </div>
      </div>`;
    msgList().appendChild(el);
    scrollToBottom();
  }

  function removeThinking() {
    document.getElementById('thinking-indicator')?.remove();
  }

  // ── Streaming ─────────────────────────────────────────
  function appendChunk(text) {
    removeThinking();
    if (!streamingEl) {
      const el = document.createElement('div');
      el.className = 'msg jarvis fade-in';
      el.id = 'streaming-msg';
      el.innerHTML = `
        <div class="msg-avatar">🤖</div>
        <div class="msg-body">
          <div class="msg-bubble stream-cursor" id="stream-bubble" style="color:#e8f4f8;background:#111827;border-left:3px solid #00d4ff;padding:10px 14px;border-radius:12px;font-size:0.92rem;line-height:1.65;"></div>
          <div class="msg-meta">${JARVIS.fmtTime()}</div>
        </div>`;
      msgList().appendChild(el);
      streamingEl = document.getElementById('stream-bubble');
      streamingText = '';
    }
    streamingText += text;
    streamingEl.innerHTML = JARVIS.formatMsg(streamingText);
    streamingEl.style.color = '#e8f4f8';
    streamingEl.style.background = '#111827';
    scrollToBottom();
  }

  function finalizeStream() {
    if (streamingEl) {
      streamingEl.classList.remove('stream-cursor');
      lastJarvisMsg = streamingText;
      streamingEl = null;
      const msgEl = document.getElementById('streaming-msg');
      if (msgEl) {
        msgEl.removeAttribute('id');
        addFeedbackButtons(msgEl, streamingText);
      }
      streamingText = '';
      if (JARVIS.voice?.autoSpeak) JARVIS.voice.speak(lastJarvisMsg);
    }
  }

  // ── Add pre-formed JARVIS message ────────────────────
  function addJarvisMessage(text) {
    removeThinking();
    lastJarvisMsg = text;
    const el = document.createElement('div');
    el.className = 'msg jarvis fade-in';
    el.innerHTML = `
      <div class="msg-avatar">🤖</div>
      <div class="msg-body">
        <div class="msg-bubble">${JARVIS.formatMsg(text)}</div>
        <div class="msg-meta">${JARVIS.fmtTime()}</div>
      </div>`;
    addFeedbackButtons(el, text);
    msgList().appendChild(el);
    scrollToBottom();
    if (JARVIS.voice?.autoSpeak) JARVIS.voice.speak(text);
  }

  // ── System message ────────────────────────────────────
  function addSystemMessage(text) {
    const el = document.createElement('div');
    el.className = 'msg system fade-in';
    el.innerHTML = `<div class="msg-bubble">${JARVIS.esc(text)}</div>`;
    msgList().appendChild(el);
    scrollToBottom();
  }

  // ── Feedback buttons ──────────────────────────────────
  function addFeedbackButtons(msgEl, jarvisText) {
    const div = msgEl.querySelector('.msg-body');
    if (!div) return;
    const fb = document.createElement('div');
    fb.className = 'msg-feedback';
    fb.innerHTML = `
      <button class="feedback-btn positive" title="Good response" data-fb="positive">👍</button>
      <button class="feedback-btn negative" title="Bad response" data-fb="negative">👎</button>`;
    fb.querySelectorAll('[data-fb]').forEach(btn => {
      btn.addEventListener('click', () => {
        JARVIS.ws.sendFeedback(lastUserMsg, jarvisText, btn.dataset.fb);
        JARVIS.toast(btn.dataset.fb === 'positive' ? '👍 Thanks!' : '👎 Got it, I\'ll improve.', btn.dataset.fb === 'positive' ? 'success' : '');
        fb.remove();
      });
    });
    div.appendChild(fb);
  }

  // ── Send message ──────────────────────────────────────
  function send() {
    const inputEl = document.getElementById('msg-input');
    const text    = inputEl?.value?.trim() || '';

    if (!text && !pendingImageB64) return;

    addUserMessage(text, pendingImageBlob);
    JARVIS.ws.sendMessage(text, pendingImageB64);
    if (inputEl) inputEl.value = '';
    clearImagePreview();
    inputEl?.style && (inputEl.style.height = 'auto');
  }

  // ── Image upload ──────────────────────────────────────
  function handleImageFile(file) {
    if (!file?.type.startsWith('image/')) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      pendingImageB64  = e.target.result.split(',')[1];
      pendingImageBlob = file;
      const bar   = document.getElementById('image-preview-bar');
      const thumb = document.getElementById('image-preview-thumb');
      if (bar)   bar.classList.add('active');
      if (thumb) thumb.src = e.target.result;
    };
    reader.readAsDataURL(file);
  }

  function clearImagePreview() {
    pendingImageB64  = null;
    pendingImageBlob = null;
    const bar = document.getElementById('image-preview-bar');
    if (bar) bar.classList.remove('active');
  }

  // ── Helpers ───────────────────────────────────────────
  function scrollToBottom() {
    const list = msgList();
    if (list) list.scrollTop = list.scrollHeight;
  }

  function hideWelcome() {
    welcome()?.classList.add('hidden');
  }

  function getUserEmoji() {
    const member = JARVIS.storage.get('j_family_member') || '';
    const map = { lucky: '👑', krishna: '👨', sangeetha: '👩', thapaswini: '👧', dhruva: '👦', prajwal: '👦' };
    return map[member.toLowerCase()] || '👤';
  }

  // ── Input auto-resize & enter to send ─────────────────
  function initInput() {
    const inputEl = document.getElementById('msg-input');
    if (!inputEl) return;

    inputEl.addEventListener('input', () => {
      inputEl.style.height = 'auto';
      inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
    });

    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        send();
      }
    });

    document.getElementById('send-btn')?.addEventListener('click', send);

    // Image paste
    inputEl.addEventListener('paste', (e) => {
      const file = Array.from(e.clipboardData?.files || []).find(f => f.type.startsWith('image/'));
      if (file) handleImageFile(file);
    });

    // File input
    document.getElementById('img-btn')?.addEventListener('click', () =>
      document.getElementById('file-input')?.click());
    document.getElementById('file-input')?.addEventListener('change', (e) =>
      handleImageFile(e.target.files[0]));
    document.getElementById('remove-image-btn')?.addEventListener('click', clearImagePreview);
  }

  // ── Welcome chip clicks ───────────────────────────────
  function initWelcomeChips() {
    document.querySelectorAll('.welcome-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const inputEl = document.getElementById('msg-input');
        if (inputEl) { inputEl.value = chip.textContent; inputEl.focus(); }
      });
    });
  }

  return {
    init: () => { initInput(); initWelcomeChips(); },
    addUserMessage, addJarvisMessage, addSystemMessage,
    showThinking, finalizeStream, appendChunk,
    handleImageFile,
  };
})();
