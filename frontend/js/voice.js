// voice.js
JARVIS.voice = (() => {
  let _synth      = window.speechSynthesis;
  let _recognition = null;
  let _listening  = false;
  let _pitch  = 1;
  let _rate   = 1;
  let _volume = 0.9;
  let autoSpeak = false;

  function speak(text) {
    if (!_synth) return;
    _synth.cancel();

    // Aggressively strip code, links, markdown before speaking
    let clean = text
      .replace(/```[\s\S]*?```/g, "")
      .replace(/`[^`]+`/g, "")
      .replace(/https?:\/\/[^\s]+/g, "")
      .replace(/www\.[^\s]+/g, "")
      .replace(/[*_#\[\]{}\(\)]/g, "")
      .replace(/\n{2,}/g, ". ")
      .replace(/\n/g, " ")
      .replace(/\s{2,}/g, " ")
      .substring(0, 250)
      .trim();

    if (!clean) return;

    const utt = new SpeechSynthesisUtterance(clean);
    utt.pitch  = _pitch;
    utt.rate   = _rate;
    utt.volume = _volume;

    // Prefer a good English voice
    const voices = _synth.getVoices();
    const preferred = voices.find(v => v.lang === "en-IN") ||
                      voices.find(v => v.lang.startsWith("en") && v.localService) ||
                      voices.find(v => v.lang.startsWith("en"));
    if (preferred) utt.voice = preferred;

    _synth.speak(utt);
  }

  function stopSpeak() {
    if (_synth) _synth.cancel();
  }

  function toggleSTT() {
    if (_listening) stopSTT();
    else startSTT();
  }

  function startSTT() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      JARVIS.toast("Voice input not supported in this browser", "error");
      return;
    }

    _recognition = new SpeechRecognition();
    _recognition.lang = "en-IN";
    _recognition.interimResults = true;
    _recognition.continuous = false;

    _recognition.onstart = () => {
      _listening = true;
      const btn = document.getElementById("btn-mic");
      if (btn) { btn.style.color = "#00d4ff"; btn.style.background = "rgba(0,212,255,0.15)"; }
    };

    _recognition.onresult = (e) => {
      let interim = "";
      let final = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) final += e.results[i][0].transcript;
        else interim += e.results[i][0].transcript;
      }

      const display = document.getElementById("interim-display");
      if (display) display.textContent = interim ? "🎤 " + interim : "";

      if (final) {
        const input = document.getElementById("msg-input");
        if (input) input.value = final.trim();
        if (display) display.textContent = "";
        _listening = false;
        setTimeout(() => {
          if (JARVIS.chat) JARVIS.chat.send();
        }, 300);
      }
    };

    _recognition.onerror = (e) => {
      if (e.error !== "no-speech") JARVIS.toast("Voice error: " + e.error, "error");
      stopSTT();
    };

    _recognition.onend = () => stopSTT();

    _recognition.start();
  }

  function stopSTT() {
    _listening = false;
    if (_recognition) { try { _recognition.stop(); } catch {} _recognition = null; }
    const btn = document.getElementById("btn-mic");
    if (btn) { btn.style.color = ""; btn.style.background = ""; }
    const display = document.getElementById("interim-display");
    if (display) display.textContent = "";
  }

  function init() {
    const ttsBtn = document.getElementById("btn-tts-toggle");
    if (ttsBtn) {
      ttsBtn.addEventListener("click", () => {
        autoSpeak = !autoSpeak;
        ttsBtn.style.color = autoSpeak ? "var(--cyan)" : "";
        JARVIS.toast(autoSpeak ? "Voice replies ON" : "Voice replies OFF");
        if (!autoSpeak) stopSpeak();
      });
    }

    const voiceModalBtn = document.getElementById("btn-voice-settings");
    const voiceModal    = document.getElementById("voice-modal");
    const voiceClose    = document.getElementById("voice-modal-close");

    if (voiceModalBtn && voiceModal) {
      voiceModalBtn.addEventListener("click", () => voiceModal.style.display = "flex");
    }
    if (voiceClose && voiceModal) {
      voiceClose.addEventListener("click", () => voiceModal.style.display = "none");
    }

    const pitchEl  = document.getElementById("v-pitch");
    const rateEl   = document.getElementById("v-rate");
    const volEl    = document.getElementById("v-vol");
    const autoEl   = document.getElementById("v-auto");

    if (pitchEl)  pitchEl.addEventListener("input",  () => { _pitch  = parseFloat(pitchEl.value); });
    if (rateEl)   rateEl.addEventListener("input",   () => { _rate   = parseFloat(rateEl.value); });
    if (volEl)    volEl.addEventListener("input",    () => { _volume = parseFloat(volEl.value); });
    if (autoEl)   autoEl.addEventListener("change",  () => { autoSpeak = autoEl.checked; });
  }

  return { init, speak, stopSpeak, toggleSTT, startSTT, stopSTT, get autoSpeak() { return autoSpeak; } };
})();
