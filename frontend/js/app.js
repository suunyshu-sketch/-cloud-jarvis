// app.js — JARVIS v3 Entry Point
document.addEventListener("DOMContentLoaded", () => {
  // Inject dot-bounce keyframe
  const style = document.createElement("style");
  style.textContent = `
    @keyframes dot-bounce {
      0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
      40% { transform: translateY(-6px); opacity: 1; }
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }
  `;
  document.head.appendChild(style);

  // Initialise all modules in order
  if (JARVIS.voice)  JARVIS.voice.init();
  if (JARVIS.chat)   JARVIS.chat.init();
  if (JARVIS.music)  JARVIS.music.init();
  if (JARVIS.panels) JARVIS.panels.init();
  if (JARVIS.admin)  JARVIS.admin.init();
  if (JARVIS.auth)   JARVIS.auth.init();
});
