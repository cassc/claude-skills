// Chat history, kept in this browser: the newest KEEP chats, each { id, time, sid, msgs: [{ who, text, job }] }.
const KEEP = 200;
const when = (t) => new Date(t).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });

function loadChats() {
  try {
    return JSON.parse(store.get("chats")).filter((c) => Array.isArray(c.msgs) && c.msgs.length);
  } catch { return []; }
}

function save(chat) {
  let chats = [chat, ...loadChats().filter((c) => c.id !== chat.id)].slice(0, KEEP);
  // Browser storage is full: drop the oldest chats until the write works.
  while (!store.set("chats", JSON.stringify(chats)) && chats.length > 1) chats = chats.slice(0, chats.length - Math.ceil(chats.length / 10));
}

function openChat(c) {
  shown = live[c.id] || c;
  showHistory(false);
  draw(shown);
}

// After a page load: chats still waiting for a reply send their message again; the server returns the kept result.
function resume() {
  for (const c of loadChats().reverse()) {
    if (!c.msgs.some((x) => x.job)) continue;
    if (c.msgs.some((x) => x.job && Date.now() - x.at > STALE)) {
      fail(c, "No reply. Ask again.");
      save(c);
      continue;
    }
    shown = c;
    deliver(c);
  }
  if (shown) draw(shown);
}

// Downloads all saved chats as one Markdown file. Claude's replies are kept as written.
function exportChats() {
  const text = `# ${document.title} - chats, exported ${when(Date.now())}\n\n` + loadChats().map((c) =>
    `## ${when(c.time)}\n\n` + c.msgs.map((x) =>
      x.who === "bot" ? `**Claude:**\n\n${x.text}`
        : x.who === "me" ? `**You:**\n\n${x.text}${x.job ? "\n\n(no reply yet)" : ""}`
          : `**Note:** ${x.text}`).join("\n\n")).join("\n\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text + "\n"], { type: "text/markdown" }));
  a.download = `repo-chats-${new Date().toISOString().slice(0, 10)}.md`;
  a.click();
  URL.revokeObjectURL(a.href);
}

function showHistory(on) {
  const list = $("log-history");
  list.hidden = !on;
  $("log").hidden = on;
  $("chat-history").classList.toggle("on", on);
  if (!on) return;
  const chats = loadChats();
  list.innerHTML = chats.length ? `<button>Export all</button>` : `<p class="hint">No saved chats yet.</p>`;
  if (chats.length) list.firstChild.onclick = exportChats;
  for (const c of chats) {
    const b = document.createElement("button"), t = document.createElement("span");
    b.className = "past";
    t.textContent = when(c.time) + (c.msgs.some((x) => x.job) ? " - waiting for Claude" : "");
    b.append(t, (c.msgs.find((x) => x.who === "me") || c.msgs[0]).text.slice(0, 80));
    b.onclick = () => openChat(c);
    list.appendChild(b);
  }
}
