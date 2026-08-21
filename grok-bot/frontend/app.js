const SUGGESTIONS = [
  "Explain quantum entanglement like I'm a sharp 12-year-old",
  "Roast my morning routine: coffee, doomscroll, panic",
  "Three contrarian takes on the future of AI — argued honestly",
  "Write a haiku about a segfault at 2am",
];

const state = {
  sessionId: localStorage.getItem("grok-bot-session") || "",
  sessions: [],
  currentMessages: [],
  streaming: false,
  stick: true,
  health: null,
  abort: null,
  armedDelete: "",
  armTimer: 0,
};

const els = {
  log: document.getElementById("log"),
  threads: document.getElementById("threads"),
  prompt: document.getElementById("prompt"),
  composer: document.getElementById("composer"),
  banner: document.getElementById("banner"),
  status: document.getElementById("status-line"),
  title: document.getElementById("thread-title"),
  model: document.getElementById("model-name"),
  key: document.getElementById("key-state"),
  store: document.getElementById("store-kind"),
  count: document.getElementById("msg-count"),
  send: document.getElementById("send"),
  pill: document.getElementById("scroll-pill"),
};

/* ---------- small helpers ---------- */

function showBanner(text) {
  els.banner.hidden = !text;
  els.banner.textContent = text || "";
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function fmtTime(iso) {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `Request failed (${response.status})`);
  }
  return payload;
}

async function copyText(text, button) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      const area = document.createElement("textarea");
      area.value = text;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
    flash(button, "copied");
  } catch {
    flash(button, "failed");
  }
}

function flash(button, label) {
  const original = button.dataset.label || button.textContent;
  button.dataset.label = original;
  button.textContent = label;
  setTimeout(() => {
    button.textContent = original;
  }, 1200);
}

/* ---------- markdown (assistant messages only) ---------- */

// Escape-first renderer: raw text is HTML-escaped before any tags are
// introduced, so model output can never inject markup. Handles fenced code,
// inline code, bold/italic, http(s) links, headings, lists, and blockquotes.
function renderMarkdown(raw) {
  const codeBlocks = [];
  const text = raw.replace(/```([^\n]*)\n?([\s\S]*?)(?:```|$)/g, (match, lang, code) => {
    const index = codeBlocks.length;
    codeBlocks.push({ lang: lang.trim(), code: code.replace(/\n$/, "") });
    return `\n\u0000CODE${index}\u0000\n`;
  });

  let safe = escapeHtml(text);
  safe = safe.replace(/`([^`\n]+)`/g, '<code class="inline">$1</code>');
  safe = safe.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  safe = safe.replace(/(^|[^*\w])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>");
  safe = safe.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
  );

  const out = [];
  let para = [];
  let list = null;
  let quote = [];

  const flushPara = () => {
    if (para.length) {
      out.push(`<p>${para.join("<br />")}</p>`);
      para = [];
    }
  };
  const flushList = () => {
    if (list) {
      out.push(`<${list.type}>${list.items.map((item) => `<li>${item}</li>`).join("")}</${list.type}>`);
      list = null;
    }
  };
  const flushQuote = () => {
    if (quote.length) {
      out.push(`<blockquote>${quote.join("<br />")}</blockquote>`);
      quote = [];
    }
  };
  const flushAll = () => {
    flushPara();
    flushList();
    flushQuote();
  };

  for (const line of safe.split("\n")) {
    const trimmed = line.trim();
    const codeMatch = trimmed.match(/^\u0000CODE(\d+)\u0000$/);
    if (codeMatch) {
      flushAll();
      out.push(renderCodeBlock(codeBlocks[Number(codeMatch[1])]));
      continue;
    }
    if (!trimmed) {
      flushAll();
      continue;
    }
    const heading = trimmed.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      flushAll();
      const level = Math.min(heading[1].length + 2, 6);
      out.push(`<h${level}>${heading[2]}</h${level}>`);
      continue;
    }
    if (trimmed.startsWith("&gt; ") || trimmed === "&gt;") {
      flushPara();
      flushList();
      quote.push(trimmed === "&gt;" ? "" : trimmed.slice(5));
      continue;
    }
    const bullet = trimmed.match(/^[-*]\s+(.*)$/);
    if (bullet) {
      flushPara();
      flushQuote();
      if (!list || list.type !== "ul") {
        flushList();
        list = { type: "ul", items: [] };
      }
      list.items.push(bullet[1]);
      continue;
    }
    const numbered = trimmed.match(/^\d+[.)]\s+(.*)$/);
    if (numbered) {
      flushPara();
      flushQuote();
      if (!list || list.type !== "ol") {
        flushList();
        list = { type: "ol", items: [] };
      }
      list.items.push(numbered[1]);
      continue;
    }
    flushList();
    flushQuote();
    para.push(trimmed);
  }
  flushAll();
  return out.join("");
}

function renderCodeBlock(block) {
  const lang = block.lang ? escapeHtml(block.lang) : "code";
  return `<div class="codeblock"><div class="codeblock__bar"><span class="codeblock__lang">${lang}</span><button type="button" class="codeblock__copy">copy</button></div><pre class="codeblock__pre"><code>${escapeHtml(block.code)}</code></pre></div>`;
}

/* ---------- rendering ---------- */

function renderEmpty() {
  els.log.innerHTML = `
    <li class="empty">
      <h3>The dish is pointed at Grok.</h3>
      <p>Ask something sharp — or fire one of these:</p>
      <div class="chips">${SUGGESTIONS.map(
        (s) => `<button type="button" class="chip" data-suggest="${escapeHtml(s)}">${escapeHtml(s)}</button>`
      ).join("")}</div>
    </li>`;
}

function renderMessageBody(message) {
  return message.role === "assistant" ? renderMarkdown(message.content) : escapeHtml(message.content);
}

function renderMessages(messages) {
  state.currentMessages = messages;
  updateCount(messages.length);
  if (!messages.length) {
    renderEmpty();
    return;
  }
  els.log.innerHTML = messages
    .map((message, index) => {
      const who = message.role === "assistant" ? "grok" : "you";
      const isLast = index === messages.length - 1;
      const actions =
        message.role === "assistant"
          ? `<div class="msg__actions"><button type="button" class="mini" data-copy="${index}">copy</button>${
              isLast ? '<button type="button" class="mini" data-retry>retry</button>' : ""
            }</div>`
          : "";
      return `<li class="msg msg--${who}">
        <span class="msg__who">${who}<br />${fmtTime(message.created_at)}</span>
        <div class="msg__content"><div class="msg__body">${renderMessageBody(message)}</div>${actions}</div>
      </li>`;
    })
    .join("");
  autoscroll();
}

function renderThreads() {
  els.threads.innerHTML = state.sessions
    .map((session) => {
      const active = session.id === state.sessionId ? " is-active" : "";
      const armed = state.armedDelete === session.id;
      return `<li class="thread${active}">
        <button type="button" class="thread__open" data-id="${session.id}">
          <span class="title">${escapeHtml(session.title)}</span>
          <span class="when">${fmtTime(session.updated_at)}</span>
        </button>
        <button type="button" class="thread__del${armed ? " is-armed" : ""}" data-del="${session.id}" title="delete thread">${armed ? "sure?" : "×"}</button>
      </li>`;
    })
    .join("");
}

function updateStatus() {
  if (state.streaming) {
    els.status.textContent = "transmitting…";
    return;
  }
  if (!state.health) {
    els.status.textContent = "awaiting signal";
    return;
  }
  els.status.textContent = state.health.grok_configured ? "signal locked" : "no api key";
}

function updateCount(n) {
  els.count.textContent = String(n);
}

/* ---------- scrolling ---------- */

function isNearBottom() {
  return els.log.scrollHeight - els.log.scrollTop - els.log.clientHeight < 80;
}

function autoscroll() {
  if (state.stick) {
    els.log.scrollTop = els.log.scrollHeight;
  }
  els.pill.hidden = state.stick;
}

els.log.addEventListener("scroll", () => {
  state.stick = isNearBottom();
  els.pill.hidden = state.stick;
});

els.pill.addEventListener("click", () => {
  state.stick = true;
  els.log.scrollTop = els.log.scrollHeight;
  els.pill.hidden = true;
});

/* ---------- sessions ---------- */

async function refreshSessions() {
  const data = await api("/api/sessions");
  state.sessions = data.sessions;
  renderThreads();
}

async function loadSession(sessionId) {
  const session = await api(`/api/sessions/${sessionId}`);
  state.sessionId = session.id;
  localStorage.setItem("grok-bot-session", session.id);
  els.title.textContent = session.title;
  state.stick = true;
  renderMessages(session.messages);
  await refreshSessions();
}

async function ensureSession() {
  if (state.sessionId) {
    try {
      await loadSession(state.sessionId);
      return;
    } catch {
      localStorage.removeItem("grok-bot-session");
      state.sessionId = "";
    }
  }
  const created = await api("/api/sessions", { method: "POST" });
  await loadSession(created.id);
}

async function newThread() {
  const created = await api("/api/sessions", { method: "POST" });
  await loadSession(created.id);
  els.prompt.focus();
}

async function deleteThread(sessionId) {
  await api(`/api/sessions/${sessionId}`, { method: "DELETE" });
  if (sessionId === state.sessionId) {
    localStorage.removeItem("grok-bot-session");
    state.sessionId = "";
    await refreshSessions();
    if (state.sessions.length) {
      await loadSession(state.sessions[0].id);
    } else {
      await ensureSession();
    }
  } else {
    await refreshSessions();
  }
}

/* ---------- rename ---------- */

function beginRename() {
  if (!state.sessionId || state.streaming || els.title.querySelector("input")) return;
  const current = els.title.textContent;
  els.title.innerHTML = '<input class="rename" maxlength="120" />';
  const input = els.title.querySelector("input");
  input.value = current;
  input.focus();
  input.select();
  let done = false;
  const finish = (text) => {
    if (done) return;
    done = true;
    els.title.textContent = text;
  };
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      input.blur();
    } else if (event.key === "Escape") {
      finish(current);
    }
  });
  input.addEventListener("blur", async () => {
    const next = input.value.trim();
    if (!next || next === current) {
      finish(current);
      return;
    }
    try {
      const updated = await api(`/api/sessions/${state.sessionId}`, {
        method: "PATCH",
        body: JSON.stringify({ title: next }),
      });
      finish(updated.title);
      await refreshSessions();
    } catch (error) {
      showBanner(error.message);
      finish(current);
    }
  });
}

els.title.addEventListener("click", beginRename);

/* ---------- streaming chat ---------- */

function setStreaming(on) {
  state.streaming = on;
  els.send.textContent = on ? "abort" : "transmit";
  els.send.classList.toggle("is-stop", on);
  updateStatus();
}

function appendUserBubble(text) {
  const empty = els.log.querySelector(".empty");
  if (empty) els.log.innerHTML = "";
  const item = document.createElement("li");
  item.className = "msg msg--you";
  item.innerHTML = `<span class="msg__who">you<br />now</span><div class="msg__content"><div class="msg__body">${escapeHtml(text)}</div></div>`;
  els.log.appendChild(item);
  state.stick = true;
  autoscroll();
}

function appendPending() {
  const item = document.createElement("li");
  item.className = "msg msg--grok is-live";
  item.innerHTML = `<span class="msg__who">grok<br />live</span><div class="msg__content"><div class="msg__body"><span class="thinking" aria-label="Grok is thinking"><i></i><i></i><i></i></span></div></div>`;
  els.log.appendChild(item);
  state.stick = true;
  autoscroll();
  return item.querySelector(".msg__body");
}

async function streamInto(url, payload, bodyNode) {
  let reply = "";
  state.abort = new AbortController();
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: state.abort.signal,
  });
  if (!response.ok || !response.body) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || `Request failed (${response.status})`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";
    let dirty = false;
    for (const frame of frames) {
      const line = frame.split("\n").find((part) => part.startsWith("data:"));
      if (!line) continue;
      const data = line.slice(5).trim();
      if (data === "[DONE]") continue;
      const parsed = JSON.parse(data);
      if (parsed.error) throw new Error(parsed.error);
      if (parsed.delta) {
        reply += parsed.delta;
        dirty = true;
      }
    }
    if (dirty) {
      bodyNode.innerHTML = `${renderMarkdown(reply)}<span class="cursor"></span>`;
      autoscroll();
    }
  }
  return reply;
}

async function finishStream(aborted) {
  setStreaming(false);
  state.abort = null;
  if (aborted) {
    // Give the server a beat to persist the partial reply after disconnect.
    await sleep(300);
  }
  try {
    await loadSession(state.sessionId);
  } catch {
    await ensureSession();
  }
}

async function sendMessage(text) {
  if (state.streaming || !state.sessionId) return;
  setStreaming(true);
  showBanner("");
  appendUserBubble(text);
  const bodyNode = appendPending();
  let aborted = false;
  try {
    await streamInto("/api/chat/stream", { session_id: state.sessionId, message: text }, bodyNode);
  } catch (error) {
    if (error.name === "AbortError") aborted = true;
    else showBanner(error.message);
  } finally {
    await finishStream(aborted);
  }
}

async function retryLast() {
  if (state.streaming || !state.sessionId) return;
  const last = state.currentMessages[state.currentMessages.length - 1];
  if (!last || last.role !== "assistant") return;
  setStreaming(true);
  showBanner("");
  const items = els.log.querySelectorAll("li.msg");
  if (items.length) items[items.length - 1].remove();
  const bodyNode = appendPending();
  let aborted = false;
  try {
    await streamInto("/api/chat/retry", { session_id: state.sessionId }, bodyNode);
  } catch (error) {
    if (error.name === "AbortError") aborted = true;
    else showBanner(error.message);
  } finally {
    await finishStream(aborted);
  }
}

/* ---------- events ---------- */

els.composer.addEventListener("submit", (event) => {
  event.preventDefault();
  if (state.streaming) {
    state.abort?.abort();
    return;
  }
  const text = els.prompt.value.trim();
  if (!text) return;
  els.prompt.value = "";
  els.prompt.style.height = "auto";
  sendMessage(text);
});

els.prompt.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    if (!state.streaming) els.composer.requestSubmit();
  }
});

els.prompt.addEventListener("input", () => {
  els.prompt.style.height = "auto";
  els.prompt.style.height = `${Math.min(els.prompt.scrollHeight, 180)}px`;
});

document.getElementById("new-thread").addEventListener("click", newThread);

els.threads.addEventListener("click", async (event) => {
  const del = event.target.closest("button[data-del]");
  if (del) {
    const id = del.dataset.del;
    if (state.armedDelete !== id) {
      state.armedDelete = id;
      renderThreads();
      clearTimeout(state.armTimer);
      state.armTimer = setTimeout(() => {
        state.armedDelete = "";
        renderThreads();
      }, 2600);
      return;
    }
    clearTimeout(state.armTimer);
    state.armedDelete = "";
    try {
      await deleteThread(id);
    } catch (error) {
      showBanner(error.message);
    }
    return;
  }
  const open = event.target.closest("button[data-id]");
  if (open) loadSession(open.dataset.id);
});

els.log.addEventListener("click", (event) => {
  const chip = event.target.closest(".chip");
  if (chip) {
    sendMessage(chip.dataset.suggest);
    return;
  }
  const blockCopy = event.target.closest(".codeblock__copy");
  if (blockCopy) {
    const code = blockCopy.closest(".codeblock")?.querySelector("pre code");
    if (code) copyText(code.textContent, blockCopy);
    return;
  }
  const msgCopy = event.target.closest("button[data-copy]");
  if (msgCopy) {
    const message = state.currentMessages[Number(msgCopy.dataset.copy)];
    if (message) copyText(message.content, msgCopy);
    return;
  }
  if (event.target.closest("button[data-retry]")) {
    retryLast();
  }
});

/* ---------- boot ---------- */

async function boot() {
  try {
    const health = await api("/health");
    state.health = health;
    els.model.textContent = health.model;
    els.key.textContent = health.grok_configured ? "armed" : "missing";
    els.store.textContent = health.store || "—";
    updateStatus();
    if (!health.grok_configured) {
      showBanner("Grok Bot needs an XAI_API_KEY. Copy grok-bot/.env.example to .env and restart.");
    }
    await ensureSession();
    els.prompt.focus();
  } catch (error) {
    showBanner(error.message);
  }
}

boot();
