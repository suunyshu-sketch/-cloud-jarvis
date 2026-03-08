/* ═══════════════════════════════════════════════════════════
   J.A.R.V.I.S — Voice Module
   TTS (Text-to-Speech) + STT (Speech-to-Text via Web Speech API)
   ═══════════════════════════════════════════════════════════ */

JARVIS.voice = (() => {
  let recognition  = null;
  let synth        = window.speechSynthesis;
  let voiceList    = [];
  let isListening  = false;
  let isSpeaking   = false;
  let autoSpeak    = JARVIS.storage.get('j_autospeak') || false;
  let voiceSettings = JARVIS.storage.get('j_voice_settings') || { pitch: 1.0, rate: 0.95, volume: 1.0 };

  // Load voice list when available
  if (synth) {
    const loadVoices = () => { voiceList = synth.getVoices(); };
    loadVoices();
    synth.addEventListener('voiceschanged', loadVoices);
  }

  // ── TTS ───────────────────────────────────────────────
  function speak(text) {
    if (!synth || !text) return;
    synth.cancel();
    const clean = text.replace(/[*_`#\[\]{}]/g, '').substring(0, 500);
    const utterance = new SpeechSynthesisUtterance(clean);
    utterance.pitch  = voiceSettings.pitch;
    utterance.rate   = voiceSettings.rate;
    utterance.volume = voiceSettings.volume;

    // Prefer a good English or Telugu voice
    const preferred = voiceList.find(v =>
      v.lang.startsWith('en') && v.name.toLowerCase().includes('google')
    ) || voiceList.find(v => v.lang.startsWith('en')) || voiceList[0];
    if (preferred) utterance.voice = preferred;

    utterance.onstart = () => {
      isSpeaking = true;
      updateReactor('speaking');
    };
    utterance.onend = () => {
      isSpeaking = false;
      updateReactor('idle');
    };
    synth.speak(utterance);
  }

  function stopSpeaking() {
    synth?.cancel();
    isSpeaking = false;
    updateReactor('idle');
  }

  // ── STT ───────────────────────────────────────────────
  function startListening() {
    if (isListening || !('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
      JARVIS.toast('Voice recognition not supported in this browser.', 'error');
      return;
    }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SR();
    recognition.lang        = 'en-IN';
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.continuous  = false;

    recognition.onstart = () => {
      isListening = true;
      updateReactor('listening');
      updateMicBtn(true);
      document.getElementById('interim-display').textContent = '🎤 Listening…';
    };

    recognition.onresult = (e) => {
      let interim = '';
      let final   = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) final   += e.results[i][0].transcript;
        else                       interim += e.results[i][0].transcript;
      }
      const display = document.getElementById('interim-display');
      if (display) display.textContent = interim || final || '';
      if (final) {
        const inputEl = document.getElementById('msg-input');
        if (inputEl) inputEl.value = (inputEl.value + ' ' + final).trim();
      }
    };

    recognition.onend = () => {
      isListening = false;
      updateMicBtn(false);
      updateReactor('idle');
      const display = document.getElementById('interim-display');
      if (display) display.textContent = '';
      document.getElementById('mic-waveform')?.classList.remove('active');
    };

    recognition.onerror = (e) => {
      isListening = false;
      updateMicBtn(false);
      updateReactor('idle');
      if (e.error !== 'no-speech') JARVIS.toast(`Voice error: ${e.error}`, 'error');
    };

    recognition.start();
    document.getElementById('mic-waveform')?.classList.add('active');
  }

  function stopListening() {
    recognition?.stop();
    isListening = false;
    updateMicBtn(false);
    document.getElementById('mic-waveform')?.classList.remove('active');
  }

  function toggleListening() {
    if (isListening) stopListening();
    else startListening();
  }

  // ── Reactor ring ─────────────────────────────────────
  function updateReactor(state) {
    const ring = document.getElementById('reactor-ring');
    if (!ring) return;
    ring.classList.remove('listening', 'speaking', 'thinking');
    if (state !== 'idle') ring.classList.add(state);
  }

  // ── Mic button ────────────────────────────────────────
  function updateMicBtn(listening) {
    const btn = document.getElementById('mic-btn');
    if (!btn) return;
    btn.style.color     = listening ? 'var(--cyan)' : '';
    btn.style.background = listening ? 'var(--cyan-dim)' : '';
  }

  // ── Auto-speak ────────────────────────────────────────
  function toggleAutoSpeak() {
    autoSpeak = !autoSpeak;
    JARVIS.storage.set('j_autospeak', autoSpeak);
    const btn = document.getElementById('autospeak-btn');
    if (btn) {
      btn.textContent     = autoSpeak ? '🔊' : '🔇';
      btn.title           = autoSpeak ? 'Auto-speak ON (click to disable)' : 'Auto-speak OFF';
      btn.style.color     = autoSpeak ? 'var(--cyan)' : '';
    }
    JARVIS.toast(autoSpeak ? '🔊 Auto-speak ON' : '🔇 Auto-speak OFF');
  }

  // ── Voice settings modal ──────────────────────────────
  function openSettings() {
    document.getElementById('voice-modal')?.classList.add('active');
    document.getElementById('pitch-slider').value = voiceSettings.pitch;
    document.getElementById('rate-slider').value  = voiceSettings.rate;
    document.getElementById('vol-slider').value   = voiceSettings.volume;
    updateSliderLabels();
  }

  function closeSettings() {
    document.getElementById('voice-modal')?.classList.remove('active');
  }

  function updateSliderLabels() {
    document.getElementById('pitch-val').textContent = voiceSettings.pitch;
    document.getElementById('rate-val').textContent  = voiceSettings.rate;
    document.getElementById('vol-val').textContent   = voiceSettings.volume;
  }

  function saveSettings() {
    voiceSettings.pitch  = parseFloat(document.getElementById('pitch-slider')?.value || 1.0);
    voiceSettings.rate   = parseFloat(document.getElementById('rate-slider')?.value || 0.95);
    voiceSettings.volume = parseFloat(document.getElementById('vol-slider')?.value || 1.0);
    JARVIS.storage.set('j_voice_settings', voiceSettings);
    updateSliderLabels();
    speak('Testing voice settings.');
  }

  // ── Init ─────────────────────────────────────────────
  function init() {
    document.getElementById('mic-btn')?.addEventListener('click', toggleListening);
    document.getElementById('autospeak-btn')?.addEventListener('click', toggleAutoSpeak);
    document.getElementById('voice-settings-btn')?.addEventListener('click', openSettings);
    document.getElementById('voice-modal-close')?.addEventListener('click', closeSettings);
    document.getElementById('voice-test-btn')?.addEventListener('click', saveSettings);

    ['pitch-slider','rate-slider','vol-slider'].forEach(id => {
      document.getElementById(id)?.addEventListener('input', () => {
        voiceSettings.pitch  = parseFloat(document.getElementById('pitch-slider')?.value);
        voiceSettings.rate   = parseFloat(document.getElementById('rate-slider')?.value);
        voiceSettings.volume = parseFloat(document.getElementById('vol-slider')?.value);
        updateSliderLabels();
      });
    });

    // Set initial autospeak button state
    const btn = document.getElementById('autospeak-btn');
    if (btn && autoSpeak) { btn.textContent = '🔊'; btn.style.color = 'var(--cyan)'; }
  }

  return { init, speak, stopSpeaking, toggleListening, toggleAutoSpeak, openSettings, get autoSpeak() { return autoSpeak; } };
})();
