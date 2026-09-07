// ==============================================================================
// omusic — Cyber-Minimal Drop-Down Menu Bar UI Controller
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
const btnHideWindow = document.getElementById("btn-hide-window");
const artworkImg = document.getElementById("artwork-img");
const artworkFallback = document.getElementById("artwork-fallback");
const backdrop = document.getElementById("backdrop");

const trackTitle = document.getElementById("track-title");
const trackArtist = document.getElementById("track-artist");

const btnShuffle = document.getElementById("btn-shuffle");
const btnPrev = document.getElementById("btn-prev");
const btnPlay = document.getElementById("btn-play");
const iconPlay = document.getElementById("icon-play");
const iconPause = document.getElementById("icon-pause");
const btnNext = document.getElementById("btn-next");
const btnRepeat = document.getElementById("btn-repeat");

const progressTrack = document.getElementById("progress-track");
const progressFill = document.getElementById("progress-fill");
const progressKnob = document.getElementById("progress-knob");
const posLabel = document.getElementById("pos-label");
const durLabel = document.getElementById("dur-label");

const btnMute = document.getElementById("btn-mute");
const iconVol = document.getElementById("icon-vol");
const iconMute = document.getElementById("icon-mute");
const volumeSlider = document.getElementById("volume-slider");
const volumeLabel = document.getElementById("volume-label");

const queueTitle = document.getElementById("queue-title");
const btnClearQueue = document.getElementById("btn-clear-queue");
const queueList = document.getElementById("queue-list");
const queueEmpty = document.getElementById("queue-empty");

// SVGs
const SVG_SEARCH = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>`;
const SVG_SPINNER = `<svg class="spin-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"></path></svg>`;
const SVG_GRIP = `<svg width="12" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="8" cy="5" r="2"></circle><circle cx="16" cy="5" r="2"></circle><circle cx="8" cy="12" r="2"></circle><circle cx="16" cy="12" r="2"></circle><circle cx="8" cy="19" r="2"></circle><circle cx="16" cy="19" r="2"></circle></svg>`;
const SVG_NEXT = `<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="5,4 15,12 5,20"></polygon><rect x="17.5" y="4" width="2.5" height="16" rx="0.5"></rect></svg>`;
const SVG_PLUS = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>`;
const SVG_CLOSE = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`;

const EQ_HTML = `<div class="equalizer-bars"><span class="bar b1"></span><span class="bar b2"></span><span class="bar b3"></span></div>`;

// Helpers
function formatTime(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}:${rem < 10 ? "0" : ""}${rem}`;
}

function parseDurationSecs(durStr) {
  if (!durStr) return 0;
  const parts = durStr.split(":").map(Number);
  if (parts.length === 2) {
    return (parts[0] * 60) + parts[1];
  } else if (parts.length === 3) {
    return (parts[0] * 3600) + (parts[1] * 60) + parts[2];
  }
  return 0;
}

function formatTotalDuration(seconds) {
  if (!seconds || seconds <= 0) return "";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) {
    return `${h}h ${m}m`;
  }
  return `${m}m`;
}

// Hide window button
if (btnHideWindow) {
  btnHideWindow.addEventListener("click", () => {
    invoke("hide_window");
  });
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
  searchIcon.innerHTML = SVG_SPINNER;
  searchPlaceholder.textContent = "Searching YouTube Music…";
  searchPlaceholder.classList.remove("hidden");

  try {
    const songs = await invoke("search_music", { query, limit });
    searchResults = songs;
    renderSearchResults(songs);
  } catch (err) {
    searchPlaceholder.textContent = "Search failed. Please check network.";
  } finally {
    searchIcon.innerHTML = SVG_SEARCH;
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

  const currentVid = (currentIndex >= 0 && currentIndex < queue.length) ? queue[currentIndex].videoId : "";

  songs.forEach((song, idx) => {
    const isCurrent = song.videoId === currentVid && currentVid !== "";
    const row = document.createElement("div");
    row.className = `track-row ${isCurrent ? "active" : ""}`;
    row.innerHTML = `
      <span class="track-idx">${isCurrent && isPlaying ? EQ_HTML : (idx + 1)}</span>
      <img class="track-thumb" src="${song.thumbnail || ''}" alt="" />
      <div class="track-info">
        <span class="track-name">${song.title}</span>
        <span class="track-meta">${song.artist}</span>
      </div>
      <div class="track-actions">
        <span class="track-dur">${song.duration}</span>
        <button class="btn-row-action btn-next" title="Play next">${SVG_NEXT}</button>
        <button class="btn-row-action btn-add" title="Add to queue">${SVG_PLUS}</button>
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
    btnLoadMore.textContent = "✕ Load more songs";
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

  if (song.thumbnail) {
    artworkImg.src = song.thumbnail;
    artworkImg.classList.remove("hidden");
    artworkFallback.classList.add("hidden");
    backdrop.style.backgroundImage = `url('${song.thumbnail}')`;
    backdrop.style.opacity = "0.20";
  } else {
    artworkImg.classList.add("hidden");
    artworkFallback.classList.remove("hidden");
    backdrop.style.backgroundImage = "";
    backdrop.style.opacity = "0.04";
  }

  renderQueue();
  if (searchResults.length > 0) {
    renderSearchResults(searchResults);
  }
}

function updatePlayPauseButton(playing) {
  isPlaying = playing;
  if (playing) {
    iconPlay.classList.add("hidden");
    iconPause.classList.remove("hidden");
    headerEq.classList.remove("hidden");
    playerLabel.textContent = "NOW PLAYING";
  } else {
    iconPlay.classList.remove("hidden");
    iconPause.classList.add("hidden");
    headerEq.classList.add("hidden");
    playerLabel.textContent = "PLAYER";
  }

  // Update rows
  renderQueue();
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

btnPrev.addEventListener("click", () => {
  if (currentIndex > 0) {
    playIndex(currentIndex - 1);
  }
});

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

  let totalSecs = 0;
  queue.forEach(s => {
    totalSecs += parseDurationSecs(s.duration);
  });
  const durStr = formatTotalDuration(totalSecs);
  const songLabel = queue.length === 1 ? "song" : "songs";
  queueTitle.textContent = durStr ? `Queue · ${queue.length} ${songLabel} · ${durStr}` : `Queue · ${queue.length} ${songLabel}`;

  queue.forEach((song, idx) => {
    const isCurrent = idx === currentIndex;
    const row = document.createElement("div");
    row.className = `track-row ${isCurrent ? "active" : ""}`;
    row.draggable = true;
    row.dataset.index = idx;

    row.innerHTML = `
      <span class="track-idx">${isCurrent && isPlaying ? EQ_HTML : (idx + 1)}</span>
      <img class="track-thumb" src="${song.thumbnail || ''}" alt="" />
      <div class="track-info">
        <span class="track-name">${song.title}</span>
        <span class="track-meta">${song.artist}</span>
      </div>
      <div class="track-actions">
        <span class="track-dur">${song.duration}</span>
        <button class="btn-row-action btn-remove" title="Remove">${SVG_CLOSE}</button>
      </div>
      <span class="drag-handle" title="Drag to reorder">${SVG_GRIP}</span>
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
  if (isMuted) {
    iconVol.classList.add("hidden");
    iconMute.classList.remove("hidden");
  } else {
    iconVol.classList.remove("hidden");
    iconMute.classList.add("hidden");
  }
  await invoke("set_muted", { muted: isMuted });
});

// ---------------------------------------------------------------------------
// Background Status Updates
// ---------------------------------------------------------------------------
listen("playback-status", (event) => {
  const status = event.payload;
  if (!status) return;

  currentPosition = status.position || 0;
  currentDuration = status.duration || 0;
  if (status.is_playing !== isPlaying) {
    updatePlayPauseButton(status.is_playing);
  }

  posLabel.textContent = formatTime(currentPosition);
  durLabel.textContent = formatTime(currentDuration);

  if (currentDuration > 0) {
    const ratio = Math.min(1, currentPosition / currentDuration);
    progressFill.style.width = `${ratio * 100}%`;
    progressKnob.style.left = `${ratio * 100}%`;

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
  } else if (e.key === "Enter") {
    if (currentIndex >= 0 && currentIndex < queue.length) {
      playIndex(currentIndex);
    }
    e.preventDefault();
  } else if (e.key === "q") {
    // Focus queue
    const firstRow = queueList.querySelector(".track-row");
    if (firstRow) firstRow.focus();
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
