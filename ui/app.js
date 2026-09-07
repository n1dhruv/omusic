// ==============================================================================
// omusic — Drop-Down Menu Bar UI Controller
// ==============================================================================

const invoke = window.__TAURI__.core.invoke;
const listen = window.__TAURI__.event.listen;

// State
let queue = [];
let currentIndex = -1;
let isPlaying = false;
let isMuted = false;
let currentDuration = 0;
let currentPosition = 0;
let shuffleEnabled = false;
let repeatEnabled = false;
let searchResults = [];
let searchLimit = 10;
let currentSearchQuery = "";
let isMiniMode = false;

// DOM Elements
const searchInput = document.getElementById("search-input");
const searchIcon = document.getElementById("search-icon");
const searchClear = document.getElementById("search-clear");
const searchPlaceholder = document.getElementById("search-placeholder");
const resultsHeader = document.getElementById("results-header");
const resultsScroll = document.getElementById("results-scroll");
const resultsList = document.getElementById("results-list");
const btnLoadMore = document.getElementById("btn-load-more");

const playerLabel = document.getElementById("player-label");
const headerEq = document.getElementById("header-eq");
const artworkImg = document.getElementById("artwork-img");
const artworkFallback = document.getElementById("artwork-fallback");
const backdrop = document.getElementById("backdrop");

const trackTitle = document.getElementById("track-title");
const trackArtist = document.getElementById("track-artist");

const btnShuffle = document.getElementById("btn-shuffle");
const btnPrev = document.getElementById("btn-prev");
const btnPlay = document.getElementById("btn-play");
const btnNext = document.getElementById("btn-next");
const btnRepeat = document.getElementById("btn-repeat");

const progressTrack = document.getElementById("progress-track");
const progressFill = document.getElementById("progress-fill");
const progressKnob = document.getElementById("progress-knob");
const posLabel = document.getElementById("pos-label");
const durLabel = document.getElementById("dur-label");

const btnMute = document.getElementById("btn-mute");
const volumeSlider = document.getElementById("volume-slider");
const volumeLabel = document.getElementById("volume-label");

const queueTitle = document.getElementById("queue-title");
const btnClearQueue = document.getElementById("btn-clear-queue");
const queueList = document.getElementById("queue-list");
const queueEmpty = document.getElementById("queue-empty");

const fullPlayer = document.getElementById("full-player");
const miniPlayer = document.getElementById("mini-player");
const btnMiniMode = document.getElementById("btn-mini-mode");
const miniExpand = document.getElementById("mini-expand");
const miniThumb = document.getElementById("mini-thumb");
const miniTitle = document.getElementById("mini-title");
const miniSub = document.getElementById("mini-sub");
const miniPrev = document.getElementById("mini-prev");
const miniPlay = document.getElementById("mini-play");
const miniNext = document.getElementById("mini-next");
const miniProgressLine = document.getElementById("mini-progress-line");

// Helpers
function formatTime(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}:${rem < 10 ? "0" : ""}${rem}`;
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------
searchInput.addEventListener("keydown", async (e) => {
  if (e.key === "Enter") {
    const query = searchInput.value.trim();
    if (!query) return;
    currentSearchQuery = query;
    searchLimit = 10;
    executeSearch(query, searchLimit);
  }
});

searchInput.addEventListener("input", () => {
  if (searchInput.value) {
    searchClear.classList.remove("hidden");
  } else {
    searchClear.classList.add("hidden");
    clearSearch();
  }
});

searchClear.addEventListener("click", () => {
  searchInput.value = "";
  searchClear.classList.add("hidden");
  clearSearch();
});

function clearSearch() {
  resultsList.innerHTML = "";
  resultsHeader.classList.add("hidden");
  resultsScroll.classList.add("hidden");
  btnLoadMore.classList.add("hidden");
  searchPlaceholder.classList.remove("hidden");
  searchPlaceholder.textContent = "Type a query and press Enter to search.";
}

async function executeSearch(query, limit) {
  searchIcon.textContent = "⟳";
  searchPlaceholder.textContent = "Searching YouTube Music…";
  searchPlaceholder.classList.remove("hidden");

  try {
    const songs = await invoke("search_music", { query, limit });
    searchResults = songs;
    renderSearchResults(songs);
  } catch (err) {
    searchPlaceholder.textContent = "Search failed. Please check network.";
  } finally {
    searchIcon.textContent = "🔍";
  }
}

function renderSearchResults(songs) {
  resultsList.innerHTML = "";
  if (!songs || songs.length === 0) {
    searchPlaceholder.textContent = "No tracks found.";
    searchPlaceholder.classList.remove("hidden");
    resultsHeader.classList.add("hidden");
    resultsScroll.classList.add("hidden");
    btnLoadMore.classList.add("hidden");
    return;
  }

  searchPlaceholder.classList.add("hidden");
  resultsHeader.classList.remove("hidden");
  resultsScroll.classList.remove("hidden");
  resultsHeader.textContent = `RESULTS (${songs.length})`;

  songs.forEach((song, idx) => {
    const row = document.createElement("div");
    row.className = "track-row";
    row.innerHTML = `
      <span class="track-idx">${idx + 1}</span>
      <img class="track-thumb" src="${song.thumbnail || ''}" alt="" />
      <div class="track-info">
        <span class="track-name">${song.title}</span>
        <span class="track-meta">${song.artist}</span>
      </div>
      <div class="track-actions">
        <span class="track-dur">${song.duration}</span>
        <button class="btn-row-action btn-next" title="Play next">⏭</button>
        <button class="btn-row-action btn-add" title="Add to queue">+</button>
      </div>
    `;

    row.addEventListener("click", (e) => {
      if (e.target.closest(".btn-next") || e.target.closest(".btn-add")) return;
      playSelectedSearchResult(song);
    });

    row.querySelector(".btn-next").addEventListener("click", (e) => {
      e.stopPropagation();
      playNextSearchResult(song);
    });

    row.querySelector(".btn-add").addEventListener("click", (e) => {
      e.stopPropagation();
      queueSearchResult(song);
    });

    resultsList.appendChild(row);
  });

  if (songs.length >= 10) {
    btnLoadMore.classList.remove("hidden");
  } else {
    btnLoadMore.classList.add("hidden");
  }
}

btnLoadMore.addEventListener("click", async () => {
  searchLimit += 10;
  btnLoadMore.textContent = "Loading…";
  try {
    const songs = await invoke("search_music", {
      query: currentSearchQuery,
      limit: searchLimit,
    });
    searchResults = songs;
    renderSearchResults(songs);
  } finally {
    btnLoadMore.textContent = "+ Load more songs";
  }
});

// ---------------------------------------------------------------------------
// Playback Flow
// ---------------------------------------------------------------------------
async function playSelectedSearchResult(song) {
  queue = [song];
  currentIndex = 0;
  renderQueue();
  await playIndex(0);

  // Auto-radio
  try {
    const radioSongs = await invoke("get_radio", {
      videoId: song.videoId,
      limit: 20,
    });
    for (const r of radioSongs) {
      if (r.videoId !== song.videoId) {
        queue.push(r);
      }
    }
    renderQueue();
  } catch (err) {
    console.error("Radio error", err);
  }
}

function queueSearchResult(song) {
  queue.push(song);
  renderQueue();
}

function playNextSearchResult(song) {
  if (currentIndex >= 0) {
    queue.splice(currentIndex + 1, 0, song);
  } else {
    queue.push(song);
    playIndex(0);
  }
  renderQueue();
}

async function playIndex(index) {
  if (index < 0 || index >= queue.length) return;
  currentIndex = index;
  const song = queue[index];

  updateActiveSongUI(song);

  try {
    await invoke("play_track", { videoId: song.videoId });
    isPlaying = true;
    updatePlayPauseButton(true);
  } catch (err) {
    console.error("Play error:", err);
  }
}

function updateActiveSongUI(song) {
  trackTitle.textContent = song.title || "YouTube Music";
  trackArtist.textContent = song.artist || "";
  miniTitle.textContent = song.title || "YouTube Music";
  miniSub.textContent = song.artist || "";

  if (song.thumbnail) {
    artworkImg.src = song.thumbnail;
    artworkImg.classList.remove("hidden");
    artworkFallback.classList.add("hidden");
    backdrop.style.backgroundImage = `url('${song.thumbnail}')`;
    backdrop.style.opacity = "0.22";
    miniThumb.src = song.thumbnail;
  } else {
    artworkImg.classList.add("hidden");
    artworkFallback.classList.remove("hidden");
    backdrop.style.backgroundImage = "";
    backdrop.style.opacity = "0.05";
    miniThumb.src = "";
  }

  // Update active row in queue
  const rows = queueList.querySelectorAll(".track-row");
  rows.forEach((r, idx) => {
    if (idx === currentIndex) {
      r.classList.add("active");
    } else {
      r.classList.remove("active");
    }
  });
}

function updatePlayPauseButton(playing) {
  isPlaying = playing;
  btnPlay.textContent = playing ? "⏸" : "▶";
  miniPlay.textContent = playing ? "⏸" : "▶";
  playerLabel.textContent = playing ? "NOW PLAYING" : "PLAYER";

  if (playing) {
    headerEq.classList.remove("hidden");
  } else {
    headerEq.classList.add("hidden");
  }
}

btnPlay.addEventListener("click", async () => {
  if (currentIndex < 0 && queue.length > 0) {
    playIndex(0);
    return;
  }
  await invoke("toggle_play_pause");
  isPlaying = !isPlaying;
  updatePlayPauseButton(isPlaying);
});

miniPlay.addEventListener("click", async () => {
  btnPlay.click();
});

btnPrev.addEventListener("click", () => {
  if (currentIndex > 0) {
    playIndex(currentIndex - 1);
  }
});

miniPrev.addEventListener("click", () => btnPrev.click());

btnNext.addEventListener("click", () => {
  if (shuffleEnabled && queue.length > 1) {
    let nextIdx = currentIndex;
    while (nextIdx === currentIndex) {
      nextIdx = Math.floor(Math.random() * queue.length);
    }
    playIndex(nextIdx);
  } else if (currentIndex + 1 < queue.length) {
    playIndex(currentIndex + 1);
  }
});

miniNext.addEventListener("click", () => btnNext.click());

btnShuffle.addEventListener("click", () => {
  shuffleEnabled = !shuffleEnabled;
  btnShuffle.classList.toggle("active", shuffleEnabled);
});

btnRepeat.addEventListener("click", () => {
  repeatEnabled = !repeatEnabled;
  btnRepeat.classList.toggle("active", repeatEnabled);
});

// ---------------------------------------------------------------------------
// Queue Management & Drag-and-Drop
// ---------------------------------------------------------------------------
function renderQueue() {
  queueList.innerHTML = "";
  if (queue.length === 0) {
    queueEmpty.classList.remove("hidden");
    btnClearQueue.classList.add("hidden");
    queueTitle.textContent = "Queue";
    return;
  }

  queueEmpty.classList.add("hidden");
  btnClearQueue.classList.remove("hidden");
  queueTitle.textContent = `Queue · ${queue.length} ${queue.length === 1 ? "song" : "songs"}`;

  queue.forEach((song, idx) => {
    const row = document.createElement("div");
    row.className = `track-row ${idx === currentIndex ? "active" : ""}`;
    row.draggable = true;
    row.dataset.index = idx;

    row.innerHTML = `
      <span class="track-idx">${idx + 1}</span>
      <img class="track-thumb" src="${song.thumbnail || ''}" alt="" />
      <div class="track-info">
        <span class="track-name">${song.title}</span>
        <span class="track-meta">${song.artist}</span>
      </div>
      <div class="track-actions">
        <span class="track-dur">${song.duration}</span>
        <button class="btn-row-action btn-remove" title="Remove">✕</button>
      </div>
      <span class="drag-handle" title="Drag to reorder">󰇡</span>
    `;

    row.addEventListener("click", (e) => {
      if (e.target.closest(".btn-remove") || e.target.closest(".drag-handle")) return;
      playIndex(idx);
    });

    row.querySelector(".btn-remove").addEventListener("click", (e) => {
      e.stopPropagation();
      removeFromQueue(idx);
    });

    // Drag-and-drop
    row.addEventListener("dragstart", (e) => {
      e.dataTransfer.setData("text/plain", idx);
      row.style.opacity = "0.4";
    });

    row.addEventListener("dragend", () => {
      row.style.opacity = "1";
    });

    row.addEventListener("dragover", (e) => {
      e.preventDefault();
      row.style.borderColor = "var(--c-accent-brt)";
    });

    row.addEventListener("dragleave", () => {
      row.style.borderColor = "transparent";
    });

    row.addEventListener("drop", (e) => {
      e.preventDefault();
      row.style.borderColor = "transparent";
      const fromIdx = parseInt(e.dataTransfer.getData("text/plain"), 10);
      const toIdx = idx;
      if (fromIdx !== toIdx) {
        moveQueueItem(fromIdx, toIdx);
      }
    });

    queueList.appendChild(row);
  });
}

function removeFromQueue(index) {
  if (index < 0 || index >= queue.length) return;
  const wasCurrent = index === currentIndex;
  queue.splice(index, 1);

  if (currentIndex > index) {
    currentIndex--;
  }

  renderQueue();

  if (wasCurrent) {
    if (index < queue.length) {
      playIndex(index);
    } else {
      invoke("pause_playback", { pause: true });
      updatePlayPauseButton(false);
    }
  }
}

function moveQueueItem(fromIdx, toIdx) {
  const item = queue.splice(fromIdx, 1)[0];
  queue.splice(toIdx, 0, item);

  if (currentIndex === fromIdx) {
    currentIndex = toIdx;
  } else if (fromIdx < toIdx && currentIndex > fromIdx && currentIndex <= toIdx) {
    currentIndex--;
  } else if (fromIdx > toIdx && currentIndex >= toIdx && currentIndex < fromIdx) {
    currentIndex++;
  }

  renderQueue();
}

btnClearQueue.addEventListener("click", () => {
  queue = [];
  currentIndex = -1;
  invoke("pause_playback", { pause: true });
  updatePlayPauseButton(false);
  renderQueue();
});

// ---------------------------------------------------------------------------
// Progress & Volume Scrubbing
// ---------------------------------------------------------------------------
progressTrack.addEventListener("click", async (e) => {
  if (currentDuration <= 0) return;
  const rect = progressTrack.getBoundingClientRect();
  const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
  const targetSecs = ratio * currentDuration;
  await invoke("seek_playback", { seconds: targetSecs });
});

volumeSlider.addEventListener("input", async () => {
  const val = parseFloat(volumeSlider.value);
  volumeLabel.textContent = `${Math.round(val)}%`;
  await invoke("set_volume", { volume: val });
});

btnMute.addEventListener("click", async () => {
  isMuted = !isMuted;
  btnMute.textContent = isMuted ? "🔇" : "🔊";
  await invoke("set_muted", { muted: isMuted });
});

// ---------------------------------------------------------------------------
// Mini Mode Toggle
// ---------------------------------------------------------------------------
btnMiniMode.addEventListener("click", () => {
  isMiniMode = true;
  fullPlayer.classList.add("hidden");
  miniPlayer.classList.remove("hidden");
});

miniExpand.addEventListener("click", () => {
  isMiniMode = false;
  miniPlayer.classList.add("hidden");
  fullPlayer.classList.remove("hidden");
});

// ---------------------------------------------------------------------------
// Background Status Updates
// ---------------------------------------------------------------------------
listen("playback-status", (event) => {
  const status = event.payload;
  if (!status) return;

  currentPosition = status.position || 0;
  currentDuration = status.duration || 0;
  updatePlayPauseButton(status.is_playing);

  posLabel.textContent = formatTime(currentPosition);
  durLabel.textContent = formatTime(currentDuration);

  if (currentDuration > 0) {
    const ratio = Math.min(1, currentPosition / currentDuration);
    progressFill.style.width = `${ratio * 100}%`;
    progressKnob.style.left = `${ratio * 100}%`;
    miniProgressLine.style.width = `${ratio * 100}%`;

    // Auto next when song ends
    if (currentPosition >= currentDuration - 1 && isPlaying) {
      if (repeatEnabled) {
        playIndex(currentIndex);
      } else {
        btnNext.click();
      }
    }
  }
});

// ---------------------------------------------------------------------------
// Global Keyboard Shortcuts
// ---------------------------------------------------------------------------
window.addEventListener("keydown", (e) => {
  // If search field is focused, only handle Escape
  if (document.activeElement === searchInput) {
    if (e.key === "Escape") {
      searchInput.blur();
      e.preventDefault();
    }
    return;
  }

  if (e.key === " ") {
    btnPlay.click();
    e.preventDefault();
  } else if (e.key === "j" || e.key === "ArrowDown") {
    if (currentIndex + 1 < queue.length) playIndex(currentIndex + 1);
    e.preventDefault();
  } else if (e.key === "k" || e.key === "ArrowUp") {
    if (currentIndex > 0) playIndex(currentIndex - 1);
    e.preventDefault();
  } else if (e.key === "/") {
    searchInput.focus();
    searchInput.select();
    e.preventDefault();
  } else if (e.key === "s") {
    btnShuffle.click();
  } else if (e.key === "r") {
    btnRepeat.click();
  } else if (e.key === "m") {
    btnMute.click();
  } else if (e.key === "Escape") {
    invoke("hide_window");
  }
});
