/* ═══════════════════════════════════════════════════════════
   J.A.R.V.I.S — Music Module
   iTunes Preview API search, 30s previews, mini player.
   ═══════════════════════════════════════════════════════════ */

JARVIS.music = (() => {
  let queue          = [];
  let currentIndex   = -1;
  let audio          = new Audio();
  let isPlaying      = false;
  let youtubeUrl     = '';

  audio.volume = 0.8;
  audio.addEventListener('ended', () => nextTrack());
  audio.addEventListener('timeupdate', updateProgress);

  // ── Search ────────────────────────────────────────────
  async function search(query) {
    setLoading(true);
    try {
      const data = await JARVIS.api(`/music/search?q=${encodeURIComponent(query)}`);
      youtubeUrl = data.youtube || '';
      renderTracks(data.results || []);
    } catch (e) {
      JARVIS.toast('Music search failed: ' + e.message, 'error');
    } finally {
      setLoading(false);
    }
  }

  async function searchGenre(genre) {
    setLoading(true);
    try {
      const data = await JARVIS.api(`/music/genre/${genre}`);
      renderTracks(data.results || []);
    } catch (e) {
      JARVIS.toast('Genre search failed.', 'error');
    } finally {
      setLoading(false);
    }
  }

  function setLoading(loading) {
    const btn = document.getElementById('music-search-btn');
    if (btn) btn.disabled = loading;
  }

  // ── Render Tracks ─────────────────────────────────────
  function renderTracks(tracks) {
    queue = tracks;
    const list = document.getElementById('track-list');
    const ytBtn = document.getElementById('yt-search-btn');
    if (!list) return;

    if (ytBtn) { ytBtn.href = youtubeUrl; ytBtn.classList.toggle('hidden', !youtubeUrl); }

    if (!tracks.length) {
      list.innerHTML = '<div class="text-muted text-sm" style="text-align:center;padding:20px">No results found.</div>';
      return;
    }

    list.innerHTML = tracks.map((t, i) => `
      <div class="track-item" data-index="${i}" ${i === currentIndex ? 'class="track-item playing"' : ''}>
        <img class="track-art" src="${JARVIS.esc(t.artwork)}" alt="" loading="lazy" onerror="this.src=''">
        <div class="track-info">
          <div class="track-title">${JARVIS.esc(t.title)}</div>
          <div class="track-artist">${JARVIS.esc(t.artist)}</div>
        </div>
        <div class="track-duration">${fmtDuration(t.duration_ms)}</div>
        ${i === currentIndex && isPlaying ? '<div class="eq-bars"><div class="eq-bar"></div><div class="eq-bar"></div><div class="eq-bar"></div></div>' : ''}
        <button class="track-play-btn" data-index="${i}" title="Play">▶</button>
      </div>`).join('');

    list.querySelectorAll('[data-index]').forEach(el => {
      el.addEventListener('click', (e) => {
        const idx = parseInt(el.dataset.index);
        if (!isNaN(idx)) playTrack(idx);
      });
    });
  }

  // ── Playback ──────────────────────────────────────────
  function playTrack(index) {
    if (index < 0 || index >= queue.length) return;
    currentIndex = index;
    const track  = queue[index];

    audio.src = track.preview_url;
    audio.play();
    isPlaying = true;

    updateMiniPlayer(track);
    updateTrackHighlight(index);
  }

  function togglePlayPause() {
    if (audio.paused) { audio.play(); isPlaying = true; }
    else              { audio.pause(); isPlaying = false; }
    updatePlayBtn();
  }

  function nextTrack() {
    if (currentIndex < queue.length - 1) playTrack(currentIndex + 1);
    else { isPlaying = false; updatePlayBtn(); }
  }

  function prevTrack() {
    if (currentIndex > 0) playTrack(currentIndex - 1);
  }

  function setVolume(v) {
    audio.volume = parseFloat(v);
  }

  // ── Mini Player ───────────────────────────────────────
  function updateMiniPlayer(track) {
    const player = document.getElementById('mini-player');
    const art    = document.getElementById('mini-player-art');
    const title  = document.getElementById('mini-player-title');
    const artist = document.getElementById('mini-player-artist');
    if (!player) return;

    if (art)    art.src            = track.artwork;
    if (title)  title.textContent  = track.title;
    if (artist) artist.textContent = track.artist;

    player.classList.add('active');
    updatePlayBtn();
  }

  function updatePlayBtn() {
    const btn = document.getElementById('mini-play-btn');
    if (btn) btn.textContent = isPlaying ? '⏸' : '▶';
  }

  function updateProgress() {
    const fill = document.querySelector('.mini-player-progress-fill');
    if (!fill || !audio.duration) return;
    fill.style.width = (audio.currentTime / audio.duration * 100) + '%';
  }

  function updateTrackHighlight(index) {
    document.querySelectorAll('.track-item').forEach((el, i) => {
      el.classList.toggle('playing', i === index);
    });
  }

  // ── Utils ─────────────────────────────────────────────
  function fmtDuration(ms) {
    if (!ms) return '0:30';
    const secs = Math.floor(ms / 1000);
    return `${Math.floor(secs/60)}:${(secs%60).toString().padStart(2,'0')}`;
  }

  // ── Init ─────────────────────────────────────────────
  function init() {
    document.getElementById('music-search-btn')?.addEventListener('click', () => {
      const q = document.getElementById('music-search-input')?.value?.trim();
      if (q) search(q);
    });
    document.getElementById('music-search-input')?.addEventListener('keydown', e => {
      if (e.key === 'Enter') {
        const q = e.target.value.trim();
        if (q) search(q);
      }
    });

    document.querySelectorAll('.genre-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.genre-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        searchGenre(chip.dataset.genre);
      });
    });

    document.getElementById('mini-play-btn')?.addEventListener('click', togglePlayPause);
    document.getElementById('mini-prev-btn')?.addEventListener('click', prevTrack);
    document.getElementById('mini-next-btn')?.addEventListener('click', nextTrack);

    document.querySelector('.mini-player-progress')?.addEventListener('click', (e) => {
      const rect = e.currentTarget.getBoundingClientRect();
      const pct  = (e.clientX - rect.left) / rect.width;
      audio.currentTime = pct * audio.duration;
    });
  }

  return { init, search, searchGenre, playTrack, togglePlayPause };
})();
