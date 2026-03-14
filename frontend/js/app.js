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

  // Hide all modals on startup
  const _hide = ["voice-modal","admin-overlay"];
  _hide.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = "none";
  });

  // Initialise all modules in order
  if (JARVIS.voice)  JARVIS.voice.init();
  if (JARVIS.chat)   JARVIS.chat.init();
  if (JARVIS.music)  JARVIS.music.init();
  if (JARVIS.panels) JARVIS.panels.init();
  if (JARVIS.admin)  JARVIS.admin.init();
  if (JARVIS.auth)   JARVIS.auth.init();

  // Settings button → admin dashboard
  document.addEventListener("click", (e) => {
    if (e.target.id === "btn-settings" || e.target.closest("#btn-settings")) {
      const overlay = document.getElementById("admin-overlay");
      if (overlay) {
        overlay.style.display = "flex";
        overlay.style.removeProperty("display");
        overlay.style.cssText = "display:flex !important;position:fixed;inset:0;background:rgba(0,0,0,0.6);align-items:center;justify-content:center;z-index:200;";
      }
      if (JARVIS.admin) JARVIS.admin.load();
    }
  });
});
