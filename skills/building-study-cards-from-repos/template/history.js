// Chat history, kept in this browser: the newest KEEP chats, each { id, mode, time, sid, msgs: [{ who, text, card, job }] }.
const KEEP = 30;

function loadChats() {
  try {
    return JSON.parse(store.get("chats")).filter((c) => modes[c.mode] && Array.isArray(c.msgs) && c.msgs.length);
  } catch { return []; }
}

function save(chat) {
  if (!chat.msgs.some((x) => x.who === "me" && !x.auto)) return; // a quiz nobody answered is not kept
  const chats = loadChats().filter((c) => c.id !== chat.id);
  chats.unshift(chat);
  store.set("chats", JSON.stringify(chats.slice(0, KEEP)));
}

function openChat(c) {
  c = live[c.id] || c;
  modes[c.mode].chat = c;
  setMode(c.mode);
  draw(c);
}

// After a page load: chats still waiting for a reply send their message again; the server returns the kept result.
function resume() {
  let back;
  for (const c of loadChats().reverse()) {
    if (!c.msgs.some((x) => x.job)) continue;
    if (c.msgs.some((x) => x.job && Date.now() - x.at > STALE)) {
      fail(c, "No reply. Ask again.");
      save(c);
      continue;
    }
    back = modes[c.mode].chat = c;
    deliver(c);
  }
  if (!back) return;
  $("chat").hidden = false;
  setMode(back.mode);
  for (const k in modes) if (modes[k].chat) draw(modes[k].chat);
}

function showHistory(on) {
  const list = $("log-history");
  list.hidden = !on;
  for (const k in modes) modes[k].log.hidden = on || k !== mode;
  $("chat-history").classList.toggle("on", on);
  if (!on) return;
  const chats = loadChats();
  list.innerHTML = chats.length ? "" : `<p class="hint">No saved chats yet.</p>`;
  for (const c of chats) {
    const b = document.createElement("button"), when = document.createElement("span");
    b.className = "past";
    when.textContent = `${new Date(c.time).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })} - ${c.mode === "quiz" ? "Quiz" : "Ask"}${c.msgs.some((x) => x.job) ? " - waiting for Claude" : ""}`;
    b.append(when, (c.msgs.find((x) => x.who === "me" && !x.auto) || c.msgs[0]).text.slice(0, 80));
    b.onclick = () => openChat(c);
    list.appendChild(b);
  }
}
