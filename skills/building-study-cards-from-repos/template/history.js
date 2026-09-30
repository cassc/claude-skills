// Chat history, kept in this browser: the newest KEEP chats, each { id, mode, time, sid, msgs: [{ who, text, card }] }.
const KEEP = 30;

function loadChats() {
  try {
    return JSON.parse(store.get("chats")).filter((c) => modes[c.mode] && Array.isArray(c.msgs) && c.msgs.length);
  } catch { return []; }
}

function record(m, mode, msg) {
  m.chat = m.chat || { id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`, mode, time: Date.now(), msgs: [] };
  m.chat.sid = m.sid;
  m.chat.msgs.push(msg);
  if (!m.chat.msgs.some((x) => x.who === "me")) return; // a quiz nobody answered is not kept
  const chats = loadChats().filter((c) => c.id !== m.chat.id);
  chats.unshift(m.chat);
  store.set("chats", JSON.stringify(chats.slice(0, KEEP)));
}

function openChat(c) {
  if (pending) return;
  const m = modes[c.mode];
  m.sid = c.sid;
  m.chat = c;
  m.log.innerHTML = "";
  for (const x of c.msgs) {
    if (x.who === "me") addMsg(m.log, x.text, "me");
    else showReply(m.log, addMsg(m.log, "", "bot"), x.text, x.card || {});
  }
  setMode(c.mode);
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
    when.textContent = `${new Date(c.time).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })} - ${c.mode === "quiz" ? "Quiz" : "Ask"}`;
    b.append(when, (c.msgs.find((x) => x.who === "me") || c.msgs[0]).text.slice(0, 80));
    b.onclick = () => openChat(c);
    list.appendChild(b);
  }
}
