/* GROK BOT — The Wire. Vanilla JS client for the grokbot API. */

const el = {
  dateline: document.getElementById("dateline"),
  modelStamp: document.getElementById("model-stamp"),
  bulletin: document.getElementById("bulletin"),
  bulletinText: document.getElementById("bulletin-text"),
  bulletinDismiss: document.getElementById("bulletin-dismiss"),
  sessionList: document.getElementById("session-list"),
  newSession: document.getElementById("new-session"),
  transcript: document.getElementById("transcript"),
  quiet: document.getElementById("quiet"),
  composer: document.getElementById("composer"),
  input: document.getElementById("input"),
  send: document.getElementById("send"),
};

const state = { sessionId: null, model: "grok", streaming: false };

/* ---------------------------------------------------------- helpers */

function timeStamp(seconds) {
  const d = seconds ? new Date(seconds * 1000) : new Date();
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function showBulletin(text) {
  el.bulletinText.textContent = text;
  el.bulletin.hidden = false;
}

function hideBulletin() {
  el.bulletin.hidden = true;
}

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = `Request failed (${response.status}).`;
    try {
      const body = await response.json();
      if (body && body.detail) detail = String(body.detail);
    } catch (_) { /* non-JSON error body */ }
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  return response.json();
}

/* ---------------------------------------------------------- transcript */

function addMessage(role, content, createdAt) {
  el.quiet.hidden = true;
  const article = document.createElement("article");
  article.className = `msg ${role === "user" ? "user" : "grok"}`;

  const meta = document.createElement("header");
  meta.className = "msg-meta";
  meta.textContent =
    role === "user"
      ? `telex → grok · ${timeStamp(createdAt)}`
      : `grok bot · ${state.model} · ${timeStamp(createdAt)}`;

  const body = document.createElement(role === "user" ? "pre" : "div");
  body.className = "msg-body";
  body.textContent = content;

  article.append(meta, body);
  el.transcript.appendChild(article);
  el.transcript.scrollTop = el.transcript.scrollHeight;
  return { article, body };
}

function clearTranscript() {
  for (const node of [...el.transcript.children]) {
    if (node !== el.quiet) node.remove();
  }
  el.quiet.hidden = false;
}

/* ---------------------------------------------------------- sessions */

async function refreshSessionList() {
  const { sessions } = await api("/api/sessions");
  el.sessionList.replaceChildren();
  for (const session of sessions) {
    const item = document.createElement("li");
    item.className = "session-item" + (session.id === state.sessionId ? " active" : "");

    const open = document.createElement("button");
    open.type = "button";
    open.className = "session-open";
    const title = document.createElement("span");
    title.className = "s-title";
    title.textContent = session.title || "untitled dispatch";
    const meta = document.createElement("span");
    meta.className = "s-meta";
    meta.textContent = `${session.message_count} msg · ${timeStamp(session.updated_at)}`;
    open.append(title, meta);
    open.addEventListener("click", () =>
      openSession(session.id).catch((e) => showBulletin(e.message))
    );

    const del = document.createElement("button");
    del.type = "button";
    del.className = "session-del";
    del.title = "Delete dispatch";
    del.textContent = "×";
    del.addEventListener("click", async (event) => {
      event.stopPropagation();
      try {
        await api(`/api/sessions/${session.id}`, { method: "DELETE" });
      } catch (error) {
        showBulletin(error.message);
        return;
      }
      if (session.id === state.sessionId) {
        state.sessionId = null;
        localStorage.removeItem("grokbot.session");
        clearTranscript();
      }
      refreshSessionList();
    });

    item.append(open, del);
    el.sessionList.appendChild(item);
  }
}

async function openSession(id) {
  const session = await api(`/api/sessions/${id}`);
  state.sessionId = session.id;
  localStorage.setItem("grokbot.session", session.id);
  clearTranscript();
  for (const message of session.messages) {
    addMessage(message.role, message.content, message.created_at);
  }
  refreshSessionList();
}

async function createSession() {
  const session = await api("/api/sessions", { method: "POST" });
  state.sessionId = session.id;
  localStorage.setItem("grokbot.session", session.id);
  clearTranscript();
  refreshSessionList();
  el.input.focus();
}

/* ---------------------------------------------------------- sending */

function setStreaming(on) {
  state.streaming = on;
  el.send.disabled = on;
  el.input.disabled = on;
  el.send.textContent = on ? "on wire…" : "transmit";
}

async function send() {
  const content = el.input.value.trim();
  if (!content || state.streaming) return;

  hideBulletin();
  if (!state.sessionId) {
    try {
      await createSession();
    } catch (error) {
      showBulletin(error.message);
      return;
    }
  }

  el.input.value = "";
  autosize();
  setStreaming(true);

  const userMsg = addMessage("user", content);
  const grokMsg = addMessage("assistant", "");
  const caret = document.createElement("span");
  caret.className = "caret";
  grokMsg.body.appendChild(caret);

  const fail = (message) => {
    grokMsg.article.remove();
    userMsg.article.remove();
    if (!el.transcript.querySelector(".msg")) el.quiet.hidden = false;
    el.input.value = content;
    autosize();
    showBulletin(message);
  };

  try {
    const response = await fetch(`/api/sessions/${state.sessionId}/messages/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });

    if (!response.ok) {
      let detail = `Request failed (${response.status}).`;
      try {
        const body = await response.json();
        if (body && body.detail) detail = String(body.detail);
      } catch (_) { /* non-JSON error body */ }
      fail(detail);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let text = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let boundary;
      while ((boundary = buffer.indexOf("\n\n")) >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        for (const line of frame.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          const event = JSON.parse(line.slice(6));
          if (event.type === "delta") {
            text += event.text;
            grokMsg.body.textContent = text;
            grokMsg.body.appendChild(caret);
            el.transcript.scrollTop = el.transcript.scrollHeight;
          } else if (event.type === "error") {
            fail(event.message);
            return;
          } else if (event.type === "done") {
            caret.remove();
            refreshSessionList();
          }
        }
      }
    }
  } catch (error) {
    fail(`The wire dropped: ${error.message}`);
  } finally {
    caret.remove();
    setStreaming(false);
    el.input.focus();
  }
}

/* ---------------------------------------------------------- boot */

function autosize() {
  el.input.style.height = "auto";
  el.input.style.height = Math.min(el.input.scrollHeight, 180) + "px";
}

async function boot() {
  el.dateline.textContent = new Date()
    .toLocaleDateString([], { weekday: "long", year: "numeric", month: "long", day: "numeric" })
    .toUpperCase();

  el.composer.addEventListener("submit", (event) => {
    event.preventDefault();
    send();
  });
  el.input.addEventListener("input", autosize);
  el.input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  });
  el.newSession.addEventListener("click", () => createSession().catch((e) => showBulletin(e.message)));
  el.bulletinDismiss.addEventListener("click", hideBulletin);

  try {
    const health = await api("/api/health");
    state.model = health.model;
    el.modelStamp.textContent = `MODEL: ${String(health.model).toUpperCase()}`;
    if (!health.api_key_configured) {
      showBulletin("No XAI_API_KEY configured — Grok can't answer. Copy .env.example to .env and add your key from console.x.ai.");
    }
  } catch (error) {
    showBulletin(`Can't reach the Grok Bot server: ${error.message}`);
  }

  try {
    await refreshSessionList();
    const remembered = localStorage.getItem("grokbot.session");
    if (remembered) {
      await openSession(remembered).catch(() => {
        localStorage.removeItem("grokbot.session");
      });
    }
  } catch (error) {
    showBulletin(error.message);
  }

  el.input.focus();
}

boot();
