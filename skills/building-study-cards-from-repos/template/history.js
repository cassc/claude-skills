// Chat history, kept in this browser: the newest KEEP chats, each { id, mode, time, sid, msgs: [{ who, text, card, job }] }.
const KEEP = 200;

function loadChats() {
  try {
    return JSON.parse(store.get("chats")).filter((c) => modes[c.mode] && Array.isArray(c.msgs) && c.msgs.length);
  } catch { return []; }
}

function save(chat) {
  if (!chat.msgs.some((x) => x.who === "me" && !x.auto)) return; // a quiz nobody answered is not kept
  let chats = [chat, ...loadChats().filter((c) => c.id !== chat.id)].slice(0, KEEP);
  // Browser storage is full: drop the oldest chats until the write works.
  while (!store.set("chats", JSON.stringify(chats)) && chats.length > 1) chats = chats.slice(0, chats.length - Math.ceil(chats.length / 10));
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

// Downloads all saved chats (ask and quiz) as one Markdown file. Claude's replies are kept as written.
function exportChats() {
  const when = (t) => new Date(t).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
  const cardName = (ref) => {
    const l = LESSONS.find((x) => x.id === ref?.lesson), c = l?.[ref.type]?.[ref.index];
    return l ? ` (card: L${l.id} ${l.title}${c ? " - " + (c.t || c.q).replace(/<[^>]+>/g, "") : ""})` : "";
  };
  const text = `# ${document.title} - chats, exported ${when(Date.now())}\n\n` + loadChats().map((c) =>
    `## ${c.mode === "quiz" ? "Quiz" : "Ask"} - ${when(c.time)}\n\n` + c.msgs.filter((x) => !x.auto).map((x) =>
      x.who === "bot" ? `**Claude**${c.mode === "ask" ? cardName(x.card) : ""}:\n\n${x.text}`
        : x.who === "me" ? `**You:**\n\n${x.text}${x.job ? "\n\n(no reply yet)" : ""}`
          : `**Note:** ${x.text}`).join("\n\n")).join("\n\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text + "\n"], { type: "text/markdown" }));
  a.download = `study-chats-${new Date().toISOString().slice(0, 10)}.md`;
  a.click();
  URL.revokeObjectURL(a.href);
}

function showHistory(on) {
  const list = $("log-history");
  list.hidden = !on;
  for (const k in modes) modes[k].log.hidden = on || k !== mode;
  $("chat-history").classList.toggle("on", on);
  if (!on) return;
  const chats = loadChats();
  list.innerHTML = chats.length ? `<button>Export all</button>` : `<p class="hint">No saved chats yet.</p>`;
  if (chats.length) list.firstChild.onclick = exportChats;
  for (const c of chats) {
    const b = document.createElement("button"), when = document.createElement("span");
    b.className = "past";
    when.textContent = `${new Date(c.time).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })} - ${c.mode === "quiz" ? "Quiz" : "Ask"}${c.msgs.some((x) => x.job) ? " - waiting for Claude" : ""}`;
    b.append(when, (c.msgs.find((x) => x.who === "me" && !x.auto) || c.msgs[0]).text.slice(0, 80));
    b.onclick = () => openChat(c);
    list.appendChild(b);
  }
}
