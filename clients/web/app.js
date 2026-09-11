/* Pixel bot UI — mood via animation only; reply streams below */

const $ = (id) => document.getElementById(id);

let ws = null;
let sessionId = null;
let recording = false;
let starting = false;
/** true from send-audio until TTS playback finishes (or error / no-tts done) */
let turnLocked = false;
let pcmChunks = [];
let audioCtx = null;
let recStream = null;
let processor = null;
let sourceNode = null;
let ttsChunks = [];
/** Queue of { chunks: Uint8Array[], text: string } — play in order, never concat WAVs */
let ttsPlayQueue = [];
let ttsPlaying = false;
let ttsPendingText = "";
/** Caption follows TTS sentence-by-sentence (auto-scroll) */
let captionMode = false;
let captionStarted = false;
let captionBuf = "";
let pendingSpeakText = [];
/** Set when agent.done arrives; idle only after playback queue drains */
let turnAwaitingIdle = false;
/** Segments of the last completed turn — click reply to replay */
let lastTtsSegments = [];
let turnTtsSegments = [];
let audioEl = null;
let streamTimer = null;
let streamToken = 0;

const PREFS = { url: "ad_url", token: "ad_token", tts: "ad_tts", pet: "ad_pet", reply: "ad_last_reply", device: "ad_device_id" };

function stableDeviceId() {
  let id = localStorage.getItem(PREFS.device) || "";
  if (!id) {
    id = "web-" + Math.random().toString(16).slice(2) + Date.now().toString(16).slice(-4);
    localStorage.setItem(PREFS.device, id);
  }
  return id;
}

function setMood(mood) {
  $("stage").dataset.mood = mood;
  if (window.pixelBot) window.pixelBot.setMood(mood);
}

function syncBotEnabled() {
  const online = !!sessionId;
  const canClick = online && (recording || !turnLocked);
  $("bot").classList.toggle("locked", !canClick);
  syncReplayHint();
}

function syncReplayHint() {
  const box = $("replyBox");
  const canReplay =
    !!sessionId &&
    !turnLocked &&
    !ttsPlaying &&
    !recording &&
    lastTtsSegments.length > 0 &&
    !!$("reply").textContent.trim();
  box.classList.toggle("replayable", canReplay);
  box.title = canReplay ? "点击重播语音" : "";
}

function clearReply() {
  streamToken += 1;
  if (streamTimer) {
    clearInterval(streamTimer);
    streamTimer = null;
  }
  $("reply").textContent = "";
  $("caret").hidden = false;
  $("replyBox").classList.remove("streaming");
}

function saveLastReply(text) {
  try {
    localStorage.setItem(PREFS.reply, text || "");
  } catch (_) {}
}

function restoreLastReply() {
  let t = "";
  try {
    t = localStorage.getItem(PREFS.reply) || "";
  } catch (_) {}
  $("reply").textContent = t;
  $("caret").hidden = false;
  $("replyBox").classList.remove("streaming");
  if (t) {
    requestAnimationFrame(() => {
      $("replyBox").scrollTop = $("replyBox").scrollHeight;
    });
  }
}

/** Show text immediately (e.g. STT) without wiping persisted agent reply. */
function showLiveReply(text) {
  const full = plainText(text);
  streamToken += 1;
  if (streamTimer) {
    clearInterval(streamTimer);
    streamTimer = null;
  }
  $("reply").textContent = full;
  $("caret").hidden = false;
  $("replyBox").classList.remove("streaming");
  requestAnimationFrame(() => {
    $("replyBox").scrollTop = $("replyBox").scrollHeight;
  });
}

/** Strip markdown / noise so UI shows plain readable text. */
function plainText(raw) {
  let s = String(raw || "");
  s = s.replace(/\r\n/g, "\n");
  // code fences
  s = s.replace(/```[\s\S]*?```/g, (block) => {
    return block.replace(/^```[^\n]*\n?/, "").replace(/```$/, "");
  });
  s = s.replace(/`([^`]+)`/g, "$1");
  // bold / italic / strike
  s = s.replace(/\*\*([^*]+)\*\*/g, "$1");
  s = s.replace(/__([^_]+)__/g, "$1");
  s = s.replace(/\*([^*]+)\*/g, "$1");
  s = s.replace(/_([^_]+)_/g, "$1");
  s = s.replace(/~~([^~]+)~~/g, "$1");
  // links / images
  s = s.replace(/!\[([^\]]*)\]\([^)]+\)/g, "$1");
  s = s.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
  // headings / quotes / lists
  s = s.replace(/^#{1,6}\s+/gm, "");
  s = s.replace(/^>\s?/gm, "");
  s = s.replace(/^\s*[-*+]\s+/gm, "");
  s = s.replace(/^\s*\d+\.\s+/gm, "");
  // collapse blank lines
  s = s.replace(/\n{3,}/g, "\n\n");
  return s.trim();
}

/** Append one spoken sentence when its audio starts; keep viewport pinned to the end. */
function appendCaption(sentence) {
  const s = plainText(sentence);
  if (!s) return;
  streamToken += 1;
  if (streamTimer) {
    clearInterval(streamTimer);
    streamTimer = null;
  }
  if (!captionStarted) {
    captionStarted = true;
    captionBuf = "";
    $("reply").textContent = "";
  }
  // One spoken sentence per line so the next line doesn't glue onto the previous tail
  if (captionBuf) {
    captionBuf += "\n" + s;
  } else {
    captionBuf = s;
  }
  $("reply").textContent = captionBuf;
  $("caret").hidden = false;
  $("replyBox").classList.add("streaming");
  saveLastReply(captionBuf);
  requestAnimationFrame(() => {
    $("replyBox").scrollTop = $("replyBox").scrollHeight;
  });
}

function resetCaptionState() {
  captionMode = false;
  captionStarted = false;
  captionBuf = "";
  pendingSpeakText = [];
  ttsPendingText = "";
}

function flushPendingSpeakText() {
  if (captionStarted || !pendingSpeakText.length) {
    pendingSpeakText = [];
    return;
  }
  const full = pendingSpeakText.filter(Boolean).join("");
  pendingSpeakText = [];
  if (full) streamReply(full);
}

/** Stream text like LLM output (char-by-char with caret). */
function streamReply(text) {
  const full = plainText(text);
  // Persist immediately so refresh mid-stream still keeps the new reply
  saveLastReply(full);
  streamToken += 1;
  const my = streamToken;
  if (streamTimer) {
    clearInterval(streamTimer);
    streamTimer = null;
  }
  const el = $("reply");
  const caret = $("caret");
  const box = $("replyBox");
  el.textContent = "";
  caret.hidden = false;
  if (!full) {
    box.classList.remove("streaming");
    return;
  }
  box.classList.add("streaming");
  let i = 0;
  const ms = full.length > 80 ? 12 : full.length > 30 ? 18 : 28;
  streamTimer = setInterval(() => {
    if (my !== streamToken) return;
    i += 1;
    el.textContent = full.slice(0, i);
    box.scrollTop = box.scrollHeight;
    if (i >= full.length) {
      clearInterval(streamTimer);
      streamTimer = null;
      box.classList.remove("streaming");
    }
  }, ms);
}

function enterIdle() {
  turnLocked = false;
  recording = false;
  setMood("idle");
  syncBotEnabled();
}

function enterBusy() {
  turnLocked = true;
  setMood("busy");
  syncBotEnabled();
}

function enterListen() {
  setMood("listen");
  syncBotEnabled();
}

function enterSpeak() {
  turnLocked = true;
  setMood("speak");
  syncBotEnabled();
}

function enterErr() {
  turnLocked = false;
  recording = false;
  setMood("err");
  syncBotEnabled();
}

function msg(type, payload = {}) {
  return JSON.stringify({
    type,
    id: Math.random().toString(16).slice(2, 10),
    ts: Date.now() / 1000,
    payload,
  });
}

function defaultWsUrl() {
  return "ws://127.0.0.1:8765";
}

function fillTtsSelect(providers, defaultId) {
  const sel = $("ttsId");
  const prev = (sel.value || localStorage.getItem(PREFS.tts) || "").trim();
  const list = Array.isArray(providers) ? providers : [];
  sel.innerHTML = "";
  if (!list.length) {
    const opt = document.createElement("option");
    opt.value = prev || "haibara";
    opt.textContent = opt.value;
    sel.appendChild(opt);
    return;
  }
  let pick = null;
  for (const p of list) {
    const id = p.id || p.name;
    if (!id) continue;
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = p.name ? `${p.name} (${id})` : id;
    sel.appendChild(opt);
    if (id === prev) pick = id;
  }
  if (!pick) {
    pick = (defaultId && [...sel.options].some((o) => o.value === defaultId))
      ? defaultId
      : sel.options[0]?.value;
  }
  if (pick) sel.value = pick;
}

function loadPrefs() {
  const saved = localStorage.getItem(PREFS.url) || "";
  let url = saved || defaultWsUrl();
  // Desktop preview is HTTP — don't stick on leftover wss:// from old LAN setups
  if (saved.startsWith("wss://")) {
    url = defaultWsUrl();
  }
  $("url").value = url;
  $("token").value = localStorage.getItem(PREFS.token) || "";
  const tts = localStorage.getItem(PREFS.tts) || "haibara";
  if (![...$("ttsId").options].some((o) => o.value === tts)) {
    const opt = document.createElement("option");
    opt.value = tts;
    opt.textContent = tts;
    $("ttsId").appendChild(opt);
  }
  $("ttsId").value = tts;
  $("petId").value = localStorage.getItem(PREFS.pet) || "monthly-salary-cat";
}

function savePrefs() {
  localStorage.setItem(PREFS.url, $("url").value.trim());
  localStorage.setItem(PREFS.token, $("token").value);
  localStorage.setItem(PREFS.tts, $("ttsId").value.trim() || "haibara");
  localStorage.setItem(PREFS.pet, $("petId").value || "monthly-salary-cat");
}

function onEvent(type, payload = {}) {
  if (type === "stt.final") {
    const t = (payload.text || "").trim();
    if (t) showLiveReply(t);
    enterBusy();
  } else if (type === "agent.thinking") {
    enterBusy();
  } else if (type === "agent.tool_call" || type === "agent.tool_result") {
    enterBusy();
  } else if (type === "agent.message") {
    const t = (payload.content || payload.text || "").trim();
    const speak = payload.speak !== false;
    if (speak) {
      // Defer UI text until each TTS sentence starts playing
      captionMode = true;
      if (t) pendingSpeakText.push(plainText(t));
    } else if (t) {
      streamReply(t);
    }
    enterBusy();
  } else if (type === "tts.start") {
    ttsChunks = [];
    ttsPendingText = (payload.text || "").trim();
    // New spoken turn replaces previous replay buffer once first audio arrives
    if (!turnTtsSegments.length && !ttsPlaying && !ttsPlayQueue.length) {
      lastTtsSegments = [];
      syncReplayHint();
    }
    enterSpeak();
  } else if (type === "tts.end") {
    if (ttsChunks.length) {
      const seg = { chunks: ttsChunks, text: ttsPendingText };
      ttsPlayQueue.push(seg);
      turnTtsSegments.push(seg);
      ttsChunks = [];
      ttsPendingText = "";
    }
    pumpTts();
  } else if (type === "agent.error" || type === "error") {
    enterErr();
  } else if (type === "agent.done" || type === "agent.cancel") {
    if (type === "agent.cancel") {
      ttsPlayQueue = [];
      ttsChunks = [];
      turnTtsSegments = [];
      turnAwaitingIdle = false;
      resetCaptionState();
      if (audioEl) {
        try { audioEl.pause(); } catch (_) {}
      }
      ttsPlaying = false;
      enterIdle();
      syncReplayHint();
    } else {
      // No audio this turn → still show the speak text
      if (!ttsPlaying && !ttsPlayQueue.length && !ttsChunks.length) {
        flushPendingSpeakText();
      }
      turnAwaitingIdle = true;
      maybeIdleAfterTts();
    }
  }
}

function connect() {
  savePrefs();
  const url = $("url").value.trim();
  if (!url) return;
  setMood("busy");
  turnLocked = true;
  syncBotEnabled();

  ws = new WebSocket(url);
  ws.binaryType = "arraybuffer";

  ws.onopen = () => {
    const payload = {
      device_id: stableDeviceId(),
      device_type: "web",
      protocol_version: "1.0",
    };
    const token = $("token").value;
    if (token) payload.token = token;
    const tts = $("ttsId").value.trim();
    if (tts) payload.tts_id = tts;
    ws.send(msg("device.hello", payload));
  };

  ws.onmessage = (ev) => {
    if (ev.data instanceof ArrayBuffer) {
      ttsChunks.push(new Uint8Array(ev.data));
      return;
    }
    const m = JSON.parse(ev.data);
    const p = m.payload || {};
    if (m.type === "session.accept") {
      sessionId = p.session_id;
      enterIdle();
      // Keep last reply across reconnect / refresh
      ws.send(msg("tts.list"));
      ws.send(msg("pets.list"));
      const tts = $("ttsId").value.trim();
      if (tts) {
        ws.send(msg("tts.select", { session_id: sessionId, tts_id: tts }));
      }
      return;
    }
    if (m.type === "tts.list.result") {
      fillTtsSelect(p.providers || [], p.default);
      savePrefs();
      return;
    }
    if (m.type === "pets.list.result") {
      const applied = window.PixelBot.applyRemoteCatalog(p, $("url").value.trim());
      if (applied) {
        const cur = window.PixelBot.refreshPetSelect(
          $("petId"),
          localStorage.getItem(PREFS.pet) || $("petId").value
        );
        $("petId").value = cur;
        if (window.pixelBot) {
          window.pixelBot.setPet(cur);
          window.pixelBot.reload();
        }
        savePrefs();
      }
      return;
    }
    if (m.type === "error") {
      enterErr();
      return;
    }
    onEvent(m.type, p);
  };

  ws.onclose = () => {
    sessionId = null;
    recording = false;
    turnLocked = true;
    setMood("offline");
    syncBotEnabled();
  };

  ws.onerror = () => enterErr();
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const w = (o, s) => {
    for (let i = 0; i < s.length; i++) view.setUint8(o + i, s.charCodeAt(i));
  };
  w(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  w(8, "WAVE");
  w(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  w(36, "data");
  view.setUint32(40, samples.length * 2, true);
  let o = 44;
  for (let i = 0; i < samples.length; i++, o += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(o, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buffer;
}

async function startTalk() {
  if (!ws || !sessionId || recording || starting || turnLocked) return;
  starting = true;
  try {
    // Keep previous reply visible until the next agent.message starts streaming.
    pcmChunks = [];
    if (!window.isSecureContext && !/^(localhost|127\.0\.0\.1)$/i.test(location.hostname)) {
      throw new Error(
        "Web UI 仅支持本机预览（http://127.0.0.1）。手机请用 Flutter 客户端。"
      );
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("此浏览器不支持麦克风录音");
    }
    recStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    sourceNode = audioCtx.createMediaStreamSource(recStream);
    processor = audioCtx.createScriptProcessor(4096, 1, 1);
    processor.onaudioprocess = (e) => {
      pcmChunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
    };
    sourceNode.connect(processor);
    processor.connect(audioCtx.destination);

    recording = true;
    enterListen();
  } catch (err) {
    const msg =
      (err && err.message) ||
      (err && err.name === "NotAllowedError" ? "麦克风权限被拒绝" : "无法打开麦克风");
    showLiveReply(msg);
    enterErr();
    throw err;
  } finally {
    starting = false;
  }
}

async function stopTalk() {
  if (!recording) return;
  recording = false;

  try {
    processor && processor.disconnect();
    sourceNode && sourceNode.disconnect();
    recStream && recStream.getTracks().forEach((t) => t.stop());
    if (audioCtx) await audioCtx.close();
  } catch (_) {}

  let n = 0;
  pcmChunks.forEach((c) => (n += c.length));
  const merged = new Float32Array(n);
  let off = 0;
  for (const c of pcmChunks) {
    merged.set(c, off);
    off += c.length;
  }
  const wav = encodeWav(merged, 16000);
  enterBusy();
  ttsChunks = [];
  ttsPlayQueue = [];
  ttsPlaying = false;
  turnAwaitingIdle = false;
  turnTtsSegments = [];
  resetCaptionState();
  syncReplayHint();
  ws.send(msg("audio.start", { session_id: sessionId }));
  const bytes = new Uint8Array(wav);
  for (let i = 0; i < bytes.length; i += 4096) {
    ws.send(bytes.subarray(i, i + 4096));
  }
  ws.send(msg("audio.end", { session_id: sessionId }));
}

async function toggleTalk() {
  if (recording) {
    await stopTalk();
    return;
  }
  if (turnLocked) return;
  await startTalk();
}

function maybeIdleAfterTts() {
  if (
    turnAwaitingIdle &&
    !ttsPlaying &&
    !ttsPlayQueue.length &&
    !ttsChunks.length
  ) {
    flushPendingSpeakText();
    if (captionStarted) {
      $("replyBox").classList.remove("streaming");
    }
    if (turnTtsSegments.length) {
      lastTtsSegments = turnTtsSegments.slice();
      turnTtsSegments = [];
    }
    turnAwaitingIdle = false;
    if (sessionId) enterIdle();
    syncReplayHint();
  }
}

function pumpTts() {
  if (ttsPlaying) return;
  if (!ttsPlayQueue.length) {
    maybeIdleAfterTts();
    syncReplayHint();
    return;
  }
  ttsPlaying = true;
  syncReplayHint();
  const item = ttsPlayQueue.shift();
  const chunks = item && item.chunks ? item.chunks : item;
  const text = item && item.text != null ? item.text : "";
  if (text) appendCaption(text);
  playTtsChunks(chunks).finally(() => {
    ttsPlaying = false;
    pumpTts();
  });
}

/** Replay last turn's audio (no caption rewrite). */
function replayLastTts() {
  if (turnLocked || ttsPlaying || recording || starting) return;
  if (!lastTtsSegments.length) return;
  ttsPlayQueue = lastTtsSegments.map((s) => ({ chunks: s.chunks, text: "" }));
  enterSpeak();
  turnLocked = true;
  syncBotEnabled();
  turnAwaitingIdle = true;
  pumpTts();
}

function playTtsChunks(chunks) {
  return new Promise((resolve) => {
    if (!chunks || !chunks.length) {
      resolve();
      return;
    }
    let total = 0;
    chunks.forEach((c) => (total += c.length));
    const out = new Uint8Array(total);
    let o = 0;
    for (const c of chunks) {
      out.set(c, o);
      o += c.length;
    }
    const wav = out[0] === 0x52 && out[1] === 0x49;
    const blob = new Blob([out], { type: wav ? "audio/wav" : "audio/mpeg" });
    const url = URL.createObjectURL(blob);
    if (audioEl) {
      try { audioEl.pause(); } catch (_) {}
    }
    audioEl = new Audio(url);
    enterSpeak();
    const done = () => {
      URL.revokeObjectURL(url);
      resolve();
    };
    audioEl.onended = done;
    audioEl.onerror = done;
    audioEl.play().catch(done);
  });
}

const botEl = $("bot");
let holdTimer = null;
let holdOpenedSettings = false;
const HOLD_MS = 550;

function clearHoldTimer() {
  if (holdTimer) {
    clearTimeout(holdTimer);
    holdTimer = null;
  }
}

function openSettings() {
  $("settings").showModal();
}

botEl.addEventListener("pointerdown", (e) => {
  if (e.button != null && e.button !== 0) return;
  holdOpenedSettings = false;
  clearHoldTimer();
  holdTimer = setTimeout(() => {
    holdOpenedSettings = true;
    openSettings();
  }, HOLD_MS);
});

botEl.addEventListener("pointerup", clearHoldTimer);
botEl.addEventListener("pointercancel", clearHoldTimer);
botEl.addEventListener("pointerleave", clearHoldTimer);
botEl.addEventListener("contextmenu", (e) => e.preventDefault());

botEl.addEventListener("click", (e) => {
  e.preventDefault();
  clearHoldTimer();
  if (holdOpenedSettings) {
    holdOpenedSettings = false;
    return;
  }
  toggleTalk().catch(() => {
    recording = false;
    starting = false;
  });
});

$("replyBox").addEventListener("click", (e) => {
  e.stopPropagation();
  if (!$("replyBox").classList.contains("replayable")) return;
  replayLastTts();
});

$("btnClose").onclick = () => $("settings").close();
$("btnSave").onclick = (e) => {
  e.preventDefault();
  $("settings").close();
  if (window.pixelBot) window.pixelBot.setPet($("petId").value);
  if (ws) ws.close();
  connect();
};

loadPrefs();

(async () => {
  const savedPet = localStorage.getItem(PREFS.pet) || "";
  const petId = await window.PixelBot.fillPetSelect($("petId"), savedPet);
  $("petId").value = petId;
  window.pixelBot = window.PixelBot.createPixelBot($("sprite"), petId);
  await window.pixelBot.ready;
  window.pixelBot.start();
  setMood("offline");
  restoreLastReply();
  turnLocked = true;
  syncBotEnabled();

  if (
    ($("url").value || "").includes("127.0.0.1") ||
    ($("url").value || "").includes("localhost")
  ) {
    connect();
  } else {
    $("settings").showModal();
  }

  if (location.protocol === "http:" && location.hostname !== "127.0.0.1" && location.hostname !== "localhost") {
    showLiveReply("Web UI 仅作桌面预览。手机请用 Flutter 客户端（clients/mobile）。");
  }
})();
