// music.js
JARVIS.music = (() => {
  let _audio = null;
  let _currentTrack = null;

  const GENRES = ["Bollywood", "Telugu", "Lo-fi", "Devotional", "Classical", "Jazz", "Rock", "Pop", "Sad", "Happy"];

  function renderPanel() {
    const content = document.getElementById("panel-content");
    if (!content) return;

    content.innerHTML = "";

    // Search bar
    const searchWrap = document.createElement("div");
    searchWrap.className = "music-search";
    searchWrap.style.cssText = "display:flex;gap:8px;margin-bottom:12px;";

    const searchInput = document.createElement("input");
    searchInput.placeholder = "Search songs, artists...";
    searchInput.style.cssText = "flex:1;padding:9px 12px;background:#1a2236;border:1px solid rgba(0,212,255,0.12);border-radius:20px;font-size:0.88rem;outline:none;color:#e8f4f8;";

    const searchBtn = document.createElement("button");
    searchBtn.textContent = "Search";
    searchBtn.style.cssText = "padding:9px 14px;background:rgba(0,212,255,0.12);border:1px solid rgba(0,212,255,0.25);border-radius:20px;color:#00d4ff;font-weight:600;font-size:0.85rem;cursor:pointer;";
    searchBtn.addEventListener("click", () => _search(searchInput.value));
    searchInput.addEventListener("keydown", (e) => { if (e.key === "Enter") _search(searchInput.value); });

    searchWrap.appendChild(searchInput);
    searchWrap.appendChild(searchBtn);
    content.appendChild(searchWrap);

    // Genre chips
    const chipWrap = document.createElement("div");
    chipWrap.style.cssText = "display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px;";
    GENRES.forEach(genre => {
      const chip = document.createElement("button");
      chip.textContent = genre;
      chip.style.cssText = "padding:5px 12px;background:#1a2236;border:1px solid rgba(0,212,255,0.12);border-radius:16px;font-size:0.8rem;color:#7a9ab8;cursor:pointer;transition:all 0.15s;";
      chip.addEventListener("click", () => { _search(genre + " music"); });
      chip.onmouseover = () => { chip.style.background = "rgba(0,212,255,0.12)"; chip.style.color = "#00d4ff"; };
      chip.onmouseout  = () => { chip.style.background = "#1a2236"; chip.style.color = "#7a9ab8"; };
      chipWrap.appendChild(chip);
    });
    content.appendChild(chipWrap);

    // Track list container
    const trackList = document.createElement("div");
    trackList.id = "track-list";
    content.appendChild(trackList);

    // Load default
    _search("popular hindi songs");
  }

  async function _search(query) {
    const trackList = document.getElementById("track-list");
    if (!trackList) return;
    trackList.innerHTML = `<div style="color:#4a6680;font-size:0.85rem;text-align:center;padding:20px;">Searching...</div>`;

    try {
      const data = await JARVIS.api(`/music/search?q=${encodeURIComponent(query)}`);
      const tracks = data.tracks || [];

      if (!tracks.length) {
        trackList.innerHTML = `<div style="color:#4a6680;font-size:0.85rem;text-align:center;padding:20px;">No results found</div>`;
        return;
      }

      trackList.innerHTML = "";
      tracks.forEach(track => {
        if (!track.previewUrl) return;
        const item = _renderTrackItem(track);
        trackList.appendChild(item);
      });
    } catch {
      trackList.innerHTML = `<div style="color:#ff4466;font-size:0.85rem;text-align:center;padding:20px;">Search failed. Try again.</div>`;
    }
  }

  function _renderTrackItem(track) {
    const item = document.createElement("div");
    item.style.cssText = "display:flex;align-items:center;gap:10px;padding:10px;background:#1a2236;border:1px solid rgba(0,212,255,0.12);border-radius:8px;margin-bottom:6px;cursor:pointer;transition:border-color 0.15s;";
    item.onmouseover = () => item.style.borderColor = "rgba(0,212,255,0.3)";
    item.onmouseout  = () => item.style.borderColor = "rgba(0,212,255,0.12)";

    const art = document.createElement("img");
    art.src = track.artworkUrl || "";
    art.alt = "";
    art.style.cssText = "width:40px;height:40px;border-radius:6px;object-fit:cover;background:#111827;flex-shrink:0;";
    art.onerror = () => { art.style.background = "#1a2236"; art.src = ""; };

    const info = document.createElement("div");
    info.style.cssText = "flex:1;min-width:0;";

    const name = document.createElement("div");
    name.textContent = track.trackName || "Unknown";
    name.style.cssText = "font-size:0.88rem;color:#e8f4f8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;";

    const artist = document.createElement("div");
    artist.textContent = track.artistName || "";
    artist.style.cssText = "font-size:0.78rem;color:#4a6680;";

    info.appendChild(name);
    info.appendChild(artist);

    const playBtn = document.createElement("button");
    playBtn.innerHTML = "&#9654;";
    playBtn.style.cssText = "color:#00d4ff;font-size:1.1rem;width:32px;height:32px;border-radius:50%;background:rgba(0,212,255,0.1);border:1px solid rgba(0,212,255,0.2);display:flex;align-items:center;justify-content:center;cursor:pointer;flex-shrink:0;";

    item.addEventListener("click", () => _playTrack(track, playBtn));
    item.appendChild(art);
    item.appendChild(info);
    item.appendChild(playBtn);
    return item;
  }

  function _playTrack(track, btn) {
    if (_audio) { _audio.pause(); _audio = null; }

    _audio = new Audio(track.previewUrl);
    _audio.volume = 0.8;
    _currentTrack = track;

    _audio.play().then(() => {
      _showMiniPlayer(track);
      if (btn) btn.innerHTML = "&#9646;&#9646;";
    }).catch(() => {
      JARVIS.toast("Could not play preview", "error");
    });

    _audio.onended = () => {
      _hideMiniPlayer();
      if (btn) btn.innerHTML = "&#9654;";
    };
  }

  function _showMiniPlayer(track) {
    const player = document.getElementById("mini-player");
    const trackEl = document.getElementById("mini-track");
    if (player) player.style.display = "flex";
    if (trackEl) trackEl.textContent = `${track.trackName} — ${track.artistName}`;

    const playBtn = document.getElementById("mini-play");
    if (playBtn) {
      playBtn.innerHTML = "&#9646;&#9646;";
      playBtn.onclick = () => {
        if (_audio && !_audio.paused) {
          _audio.pause();
          playBtn.innerHTML = "&#9654;";
        } else if (_audio) {
          _audio.play();
          playBtn.innerHTML = "&#9646;&#9646;";
        }
      };
    }

    if (_audio) {
      _audio.ontimeupdate = () => {
        const progress = document.getElementById("mini-progress");
        if (progress && _audio.duration) {
          progress.value = (_audio.currentTime / _audio.duration) * 100;
        }
      };
    }

    const prog = document.getElementById("mini-progress");
    if (prog && _audio) {
      prog.oninput = () => {
        _audio.currentTime = (_audio.duration || 0) * (prog.value / 100);
      };
    }

    const closeBtn = document.getElementById("mini-close");
    if (closeBtn) {
      closeBtn.onclick = () => {
        if (_audio) { _audio.pause(); _audio = null; }
        _hideMiniPlayer();
      };
    }
  }

  function _hideMiniPlayer() {
    const player = document.getElementById("mini-player");
    if (player) player.style.display = "none";
  }

  function init() {
    const musicBtn = document.getElementById("btn-music");
    if (musicBtn) {
      musicBtn.addEventListener("click", () => {
        if (JARVIS.panels) JARVIS.panels.openPanel("music", "Music");
        renderPanel();
      });
    }
  }

  return { init, renderPanel };
})();
