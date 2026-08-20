const state = {
  sessionId: localStorage.getItem("grok-bot-session") || "",
  sessions: [],
  streaming: false,
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
  send: document.getElementById("send"),
};

function showBanner(text) {
  els.banner.hidden = !text;
  els.banner.textContent = text || "";
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function fmtTime(iso) {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
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

function renderEmpty() {
  els.log.innerHTML = `
    <li class="empty">
      <h3>The dish is pointed at Grok.</h3>
      <p>Ask something sharp. Grok Bot keeps this thread in memory until the server restarts.</p>
    </li>`;
}

function renderMessages(messages) {
  if (!messages.length) {
    renderEmpty();
    return;
  }
  els.log.innerHTML = messages
    .map((message) => {
      const who = message.role === "assistant" ? "grok" : "you";
      return `<li class="msg msg--${who}">
        <span class="msg__who">${who}<br />${fmtTime(message.created_at)}</span>
        <p class="msg__body">${escapeHtml(message.content)}</p>
      </li>`;
    })
    .join("");
  els.log.scrollTop = els.log.scrollHeight;
}

function renderThreads() {
  els.threads.innerHTML = state.sessions
    .map((session) => {
      const active = session.id === state.sessionId ? "is-active" : "";
      return `<li class="${active}">
        <button type="button" data-id="${session.id}">
          <span class="title">${escapeHtml(session.title)}</span>
          <span class="when">${fmtTime(session.updated_at)}</span>
        </button>
      </li>`;
    })
    .join("");
}

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

function appendPending(text) {
  const empty = els.log.querySelector(".empty");
  if (empty) empty.remove();
  const item = document.createElement("li");
  item.className = "msg msg--grok";
  item.innerHTML = `<span class="msg__who">grok<br />live</span><p class="msg__body">${escapeHtml(text)}<span class="cursor"></span></p>`;
  els.log.appendChild(item);
  els.log.scrollTop = els.log.scrollHeight;
  return item.querySelector(".msg__body");
}

async function sendMessage(text) {
  if (state.streaming) return;
  state.streaming = true;
  els.send.disabled = true;
  showBanner("");

  const userItem = {
    role: "user",
    content: text,
    created_at: new Date().toISOString(),
  };
  if (els.log.querySelector(".empty")) {
    renderMessages([userItem]);
  } else {
    const li = document.createElement("li");
    li.className = "msg msg--you";
    li.innerHTML = `<span class="msg__who">you<br />now</span><p class="msg__body">${escapeHtml(text)}</p>`;
    els.log.appendChild(li);
  }

  const bodyNode = appendPending("");
  let reply = "";

  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: state.sessionId, message: text }),
    });
    if (!response.ok || !response.body) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || `Request failed (${response.status})`);
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
      for (const frame of frames) {
        const line = frame.split("\n").find((part) => part.startsWith("data:"));
        if (!line) continue;
        const data = line.slice(5).trim();
        if (data === "[DONE]") continue;
        const parsed = JSON.parse(data);
        if (parsed.error) throw new Error(parsed.error);
        if (parsed.delta) {
          reply += parsed.delta;
          bodyNode.innerHTML = `${escapeHtml(reply)}<span class="cursor"></span>`;
          els.log.scrollTop = els.log.scrollHeight;
        }
      }
    }
    bodyNode.textContent = reply;
    await loadSession(state.sessionId);
  } catch (error) {
    showBanner(error.message);
    bodyNode.parentElement?.remove();
  } finally {
    state.streaming = false;
    els.send.disabled = false;
  }
}

els.composer.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = els.prompt.value.trim();
  if (!text) return;
  els.prompt.value = "";
  els.prompt.style.height = "auto";
  sendMessage(text);
});

els.prompt.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    els.composer.requestSubmit();
  }
});

els.prompt.addEventListener("input", () => {
  els.prompt.style.height = "auto";
  els.prompt.style.height = `${Math.min(els.prompt.scrollHeight, 180)}px`;
});

document.getElementById("new-thread").addEventListener("click", newThread);

els.threads.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-id]");
  if (button) loadSession(button.dataset.id);
});

async function boot() {
  try {
    const health = await api("/health");
    els.model.textContent = health.model;
    els.key.textContent = health.grok_configured ? "armed" : "missing";
    els.status.textContent = health.grok_configured ? "signal locked" : "no api key";
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
