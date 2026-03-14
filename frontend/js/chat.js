// chat.js
JARVIS.chat = (() => {
  let _streamingEl  = null;
  let _streamingText = "";
  let _streamingBody = null;
  let _lastUserMsg  = "";
  let _lastJarvisMsg = "";
  let _pendingImage = null;
  let _privateMode  = false;

  function msgList() { return document.getElementById("msg-list"); }
  function scrollToBottom() {
    const ml = msgList();
    if (ml) ml.scrollTop = ml.scrollHeight;
  }

  // ── Public API ──────────────────────────────

  function send() {
    const input = document.getElementById("msg-input");
    if (!input) return;
    const text = input.value.trim();
    if (!text && !_pendingImage) return;

    input.value = "";
    input.style.height = "auto";

    addUserMessage(text);
    _lastUserMsg = text;

    const sent = JARVIS.ws.send(text, _pendingImage, _privateMode);
    if (!sent) return;

    if (_pendingImage) {
      _pendingImage = null;
      const wrap = document.getElementById("image-preview-wrap");
      if (wrap) wrap.style.display = "none";
    }
  }

  function addUserMessage(text) {
    if (!text) return;
    const el = document.createElement("div");
    el.className = "msg user";
    el.style.cssText = "display:flex;gap:10px;padding:3px 0;flex-direction:row-reverse;animation:fadeIn 0.2s ease both;";

    const avatar = _makeAvatar("👤", true);
    const body   = document.createElement("div");
    body.style.cssText = "display:flex;flex-direction:column;gap:4px;align-items:flex-end;max-width:calc(100% - 50px);";

    const bubble = document.createElement("div");
    bubble.style.cssText = "padding:10px 14px;border-radius:12px;border-bottom-right-radius:4px;font-size:0.91rem;line-height:1.65;word-wrap:break-word;white-space:pre-wrap;color:#e8f4f8;background:rgba(0,212,255,0.12);border:1px solid rgba(0,212,255,0.25);max-width:100%;";
    bubble.innerHTML = JARVIS.formatMsg(text);

    const meta = _makeMeta();
    meta.style.textAlign = "right";

    body.appendChild(bubble);
    body.appendChild(meta);
    el.appendChild(body);
    el.appendChild(avatar);
    msgList().appendChild(el);
    scrollToBottom();
  }

  function showThinking() {
    removeThinking();
    const el = document.createElement("div");
    el.className = "msg jarvis";
    el.id = "thinking-msg";
    el.style.cssText = "display:flex;gap:10px;padding:3px 0;animation:fadeIn 0.2s ease both;";

    const avatar = _makeAvatar("🤖", false);
    const body = document.createElement("div");
    body.style.cssText = "display:flex;flex-direction:column;gap:4px;max-width:calc(100% - 50px);";

    const dots = document.createElement("div");
    dots.className = "thinking-dots";
    dots.style.cssText = "display:flex;gap:5px;padding:10px 14px;background:#111827;border:1px solid rgba(0,212,255,0.12);border-left:3px solid #00d4ff;border-radius:12px;border-bottom-left-radius:4px;";
    for (let i = 0; i < 3; i++) {
      const s = document.createElement("span");
      s.style.cssText = `width:7px;height:7px;background:#00d4ff;border-radius:50%;animation:dot-bounce 1.2s ease-in-out infinite;animation-delay:${i*0.2}s;`;
      dots.appendChild(s);
    }

    body.appendChild(dots);
    el.appendChild(avatar);
    el.appendChild(body);
    msgList().appendChild(el);
    scrollToBottom();
  }

  function removeThinking() {
    const el = document.getElementById("thinking-msg");
    if (el) el.remove();
  }

  function appendChunk(text) {
    removeThinking();
    if (!_streamingEl) {
      const el = document.createElement("div");
      el.id = "streaming-msg";
      el.style.cssText = "display:flex;gap:10px;padding:3px 0;animation:fadeIn 0.2s ease both;";

      const avatar = _makeAvatar("🤖", false);
      const body = document.createElement("div");
      body.style.cssText = "display:flex;flex-direction:column;gap:4px;max-width:calc(100% - 50px);";

      const bubble = document.createElement("div");
      bubble.id = "stream-bubble";
      bubble.style.cssText = "padding:10px 14px;border-radius:12px;border-bottom-left-radius:4px;font-size:0.91rem;line-height:1.65;word-wrap:break-word;white-space:pre-wrap;color:#e8f4f8 !important;background:#111827 !important;border:1px solid rgba(0,212,255,0.12);border-left:3px solid #00d4ff;max-width:100%;";

      const meta = _makeMeta();
      body.appendChild(bubble);
      body.appendChild(meta);
      el.appendChild(avatar);
      el.appendChild(body);
      msgList().appendChild(el);

      _streamingEl   = bubble;
      _streamingBody = body;
      _streamingText = "";
    }

    _streamingText += text;
    _streamingEl.innerHTML = JARVIS.formatMsg(_streamingText);
    _streamingEl.style.color = "#e8f4f8";
    scrollToBottom();
  }

  function finalizeStream() {
    if (!_streamingEl) return;
    _streamingEl.classList.remove("stream-cursor");
    _streamingEl.style.color = "#e8f4f8";
    _lastJarvisMsg = _streamingText;

    const msgEl = document.getElementById("streaming-msg");
    if (msgEl) {
      msgEl.removeAttribute("id");
      if (_streamingBody) _addFeedbackRow(_streamingBody, _streamingText);
    }

    if (JARVIS.voice && JARVIS.voice.autoSpeak) {
      JARVIS.voice.speak(_streamingText);
    }

    _streamingEl   = null;
    _streamingBody = null;
    _streamingText = "";
  }

  function addJarvisMessage(text) {
    removeThinking();
    _lastJarvisMsg = text;

    const el = document.createElement("div");
    el.style.cssText = "display:flex;gap:10px;padding:3px 0;animation:fadeIn 0.2s ease both;";

    const avatar = _makeAvatar("🤖", false);
    const body = document.createElement("div");
    body.style.cssText = "display:flex;flex-direction:column;gap:4px;max-width:calc(100% - 50px);";

    const bubble = document.createElement("div");
    bubble.style.cssText = "padding:10px 14px;border-radius:12px;border-bottom-left-radius:4px;font-size:0.91rem;line-height:1.65;word-wrap:break-word;white-space:pre-wrap;color:#e8f4f8 !important;background:#111827 !important;border:1px solid rgba(0,212,255,0.12);border-left:3px solid #00d4ff;max-width:100%;";
    bubble.innerHTML = JARVIS.formatMsg(text);

    const meta = _makeMeta();
    body.appendChild(bubble);
    body.appendChild(meta);
    _addFeedbackRow(body, text);
    el.appendChild(avatar);
    el.appendChild(body);
    msgList().appendChild(el);
    scrollToBottom();

    if (JARVIS.voice && JARVIS.voice.autoSpeak) JARVIS.voice.speak(text);
  }

  function addSystemMessage(text) {
    const el = document.createElement("div");
    el.className = "msg-system";
    el.style.cssText = "text-align:center;font-size:0.78rem;color:#4a6680;padding:4px 0;font-style:italic;";
    el.textContent = text;
    msgList().appendChild(el);
    scrollToBottom();
  }

  function handleImageFile(file) {
    if (!file || !file.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      _pendingImage = e.target.result.split(",")[1];
      const wrap = document.getElementById("image-preview-wrap");
      const img  = document.getElementById("image-preview");
      if (wrap) wrap.style.display = "flex";
      if (img)  img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  }

  // ── Private helpers ──────────────────────────

  function _makeAvatar(icon, isUser) {
    const av = document.createElement("div");
    av.textContent = icon;
    av.style.cssText = `width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:0.95rem;flex-shrink:0;margin-top:4px;background:${isUser ? "rgba(0,212,255,0.12)" : "#1a2236"};border:1px solid ${isUser ? "rgba(0,212,255,0.25)" : "rgba(0,212,255,0.12)"};`;
    return av;
  }

  function _makeMeta() {
    const m = document.createElement("div");
    m.style.cssText = "font-size:0.7rem;color:#4a6680;opacity:0.7;";
    m.textContent = JARVIS.fmtTime();
    return m;
  }

  function _addFeedbackRow(body, text) {
    const fb = document.createElement("div");
    fb.style.cssText = "display:flex;gap:6px;align-items:center;margin-top:2px;";

    const up = document.createElement("button");
    up.textContent = "👍";
    up.style.cssText = "background:rgba(0,255,136,0.1);border:1px solid rgba(0,255,136,0.3);border-radius:6px;padding:3px 8px;cursor:pointer;font-size:0.82rem;color:#00ff88;";
    up.onclick = () => {
      JARVIS.ws.sendFeedback(_lastUserMsg, text, "positive");
      JARVIS.toast("Thanks for the feedback!", "success");
      fb.remove();
    };

    const down = document.createElement("button");
    down.textContent = "👎";
    down.style.cssText = "background:rgba(255,68,102,0.1);border:1px solid rgba(255,68,102,0.3);border-radius:6px;padding:3px 8px;cursor:pointer;font-size:0.82rem;color:#ff4466;";
    down.onclick = () => {
      JARVIS.ws.sendFeedback(_lastUserMsg, text, "negative");
      JARVIS.toast("Got it, will improve!");
      fb.remove();
    };

    fb.appendChild(up);
    fb.appendChild(down);
    body.appendChild(fb);
  }

  function _initInput() {
    const input = document.getElementById("msg-input");
    const sendBtn = document.getElementById("btn-send");
    const micBtn  = document.getElementById("btn-mic");
    const attachBtn = document.getElementById("btn-attach");
    const fileInput = document.getElementById("file-input");
    const clearImg  = document.getElementById("image-clear");
    const privateBtn = document.getElementById("btn-private");

    if (input) {
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
      });
      input.addEventListener("input", () => {
        input.style.height = "auto";
        input.style.height = Math.min(input.scrollHeight, 120) + "px";
      });
    }

    if (sendBtn) sendBtn.addEventListener("click", send);

    if (micBtn && JARVIS.voice) {
      micBtn.addEventListener("click", () => JARVIS.voice.toggleSTT());
    }

    if (attachBtn && fileInput) {
      attachBtn.addEventListener("click", () => fileInput.click());
      fileInput.addEventListener("change", (e) => {
        if (e.target.files[0]) handleImageFile(e.target.files[0]);
      });
    }

    if (clearImg) {
      clearImg.addEventListener("click", () => {
        _pendingImage = null;
        const wrap = document.getElementById("image-preview-wrap");
        if (wrap) wrap.style.display = "none";
      });
    }

    if (privateBtn) {
      privateBtn.addEventListener("click", () => {
        _privateMode = !_privateMode;
        privateBtn.classList.toggle("private-on", _privateMode);
        privateBtn.classList.toggle("private-off", !_privateMode);
        JARVIS.toast(_privateMode ? "Private mode ON — messages not saved" : "Private mode OFF");
      });
    }

    // Paste image
    document.addEventListener("paste", (e) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      for (const item of items) {
        if (item.type.startsWith("image/")) {
          handleImageFile(item.getAsFile());
          break;
        }
      }
    });
  }

  function _initWelcomeChips() {
    const ml = msgList();
    if (!ml) return;

    const chips = [
      "What can you do?",
      "What's the weather?",
      "Tell me something interesting",
      "Set a reminder",
      "Play some music",
      "I'm bored",
    ];

    const wrap = document.createElement("div");
    wrap.className = "welcome-chips";
    wrap.style.cssText = "display:flex;flex-wrap:wrap;gap:8px;justify-content:center;padding:30px 10px 10px;";

    chips.forEach(chip => {
      const btn = document.createElement("button");
      btn.textContent = chip;
      btn.style.cssText = "padding:8px 14px;background:#1a2236;border:1px solid rgba(0,212,255,0.12);border-radius:20px;font-size:0.82rem;color:#7a9ab8;cursor:pointer;transition:all 0.15s;";
      btn.onmouseover = () => { btn.style.background = "rgba(0,212,255,0.12)"; btn.style.color = "#00d4ff"; btn.style.borderColor = "rgba(0,212,255,0.3)"; };
      btn.onmouseout  = () => { btn.style.background = "#1a2236"; btn.style.color = "#7a9ab8"; btn.style.borderColor = "rgba(0,212,255,0.12)"; };
      btn.addEventListener("click", () => {
        wrap.remove();
        const input = document.getElementById("msg-input");
        if (input) input.value = chip;
        send();
      });
      wrap.appendChild(btn);
    });

    ml.appendChild(wrap);
  }

  function init() {
    _initInput();
    _initWelcomeChips();
  }

  return { init, send, addUserMessage, addJarvisMessage, addSystemMessage, showThinking, finalizeStream, appendChunk, handleImageFile };
})();
