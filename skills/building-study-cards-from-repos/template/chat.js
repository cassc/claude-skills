// A chat record is the source of truth: { id, mode, time, sid, msgs }. A "me" message keeps a job id until its reply is in.
// The server keeps each result by job id, so sending the same job again (after a page refresh) returns the same reply.
const modes = {
  ask: { chat: null, log: $("log-ask"), hint: "Ask a question about this card" },
  quiz: { chat: null, log: $("log-quiz"), hint: "Type your answer, 'hint', 'skip', or 'stop'" },
};
const live = {}; // chats with a running sender, by id
const STALE = 10 * 60 * 1000; // a waiting message older than this is not sent again
let mode = "ask", leaving = false;

function addMsg(log, text, cls) {
  const d = document.createElement("div");
  d.className = "msg " + cls;
  d.textContent = text;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
  return d;
}

function saveButton(box, label, body) {
  const b = document.createElement("button");
  b.textContent = label;
  b.onclick = async () => {
    b.disabled = true;
    const r = await fetch("/api/cards", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(await body()),
    });
    b.textContent = r.ok ? "Saved" : "Save failed";
    if (r.ok) reloadDeck();
  };
  box.appendChild(b);
}

// Shows a graph from a reply. kind art = a text drawing; any other kind is drawn by the server.
// Returns its box and `graph`, a promise of the card fields that hold it: { img } or { art }, or null when it cannot be drawn.
function diagram(log, kind, src) {
  const box = document.createElement("div"), pre = document.createElement("pre");
  box.className = "msg graph";
  pre.textContent = src;
  log.appendChild(box);
  if (kind === "art") {
    pre.className = "art";
    box.appendChild(pre);
    return { box, graph: Promise.resolve({ art: src }) };
  }
  box.textContent = "Drawing the graph...";
  const graph = fetch("/api/diagram", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ kind, src }),
  }).then(async (r) => {
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || r.status);
    const url = "../" + encodeURI(data.path);
    box.innerHTML = `<a href="${url}" target="_blank" title="Open full size"><img src="${url}" alt="graph"></a>`;
    return { img: data.path };
  }).catch((e) => {
    box.textContent = `Cannot draw the graph (${e.message}). Its source:`;
    box.appendChild(pre);
    return null;
  }).finally(() => { log.scrollTop = log.scrollHeight; });
  return { box, graph };
}

function proposal(log, raw, target, graph) {
  let c;
  try { c = JSON.parse(raw); } catch { return false; }
  const type = c.type === "qa" ? "qa" : "cards";
  const data = type === "qa" ? { q: c.q, a: c.a } : { t: c.t, b: c.b };
  const box = document.createElement("div");
  box.className = "msg proposal";
  box.innerHTML = `<p class="label">Suggested card${graph ? " (with the graph above)" : ""}</p><h3>${clean(data.t || data.q)}</h3><div>${clean(data.b || data.a)}</div>`;
  const save = (index, label) => saveButton(box, label, async () => ({ lesson: target.lesson, type, index, data: { ...data, ...(await graph) } }));
  linkRefs(box);
  colorBlocks(box);
  if (!target.lesson) return false;
  if (c.replace && target.type === type) save(target.index, "Replace this card");
  save(null, "Add as new card");
  log.appendChild(box);
  log.scrollTop = log.scrollHeight;
  return true;
}

const CARD = /```card\s*([\s\S]*?)```/, DIAGRAM = /```diagram[ \t]+(\w+)[^\n]*\n([\s\S]*?)```/;

function showReply(log, el, reply, card) {
  const block = reply.match(CARD), dia = reply.match(DIAGRAM);
  el.innerHTML = markdown(reply.replace(CARD, "").replace(DIAGRAM, "").trim());
  linkRefs(el);
  el.hidden = !el.innerHTML;
  const d = dia && diagram(log, dia[1], dia[2].replace(/\s+$/, ""));
  if (block && proposal(log, block[1], card, d?.graph)) return;
  // A graph with no suggested card: the learner can put it on the card they asked about.
  d?.graph.then((g) => {
    if (!g || !card.type) return;
    saveButton(d.box, "Add to this card", () => {
      const cur = LESSONS.find((l) => l.id === card.lesson)?.[card.type][card.index] || {};
      const data = card.type === "qa" ? { q: cur.q, a: cur.a } : { t: cur.t, b: cur.b };
      return { lesson: card.lesson, type: card.type, index: card.index, data: { ...data, ...g } };
    });
  });
}

function draw(chat) {
  const log = modes[chat.mode].log;
  if (modes[chat.mode].chat !== chat) return;
  log.innerHTML = "";
  for (const x of chat.msgs) {
    if (x.who === "bot") showReply(log, addMsg(log, "", "bot"), x.text, x.card || {});
    else if (!x.auto) addMsg(log, x.text, x.who);
  }
  if (chat.msgs.some((x) => x.job)) addMsg(log, "Claude is thinking...", "bot");
}

function fail(chat, text) {
  chat.msgs.forEach((x) => { delete x.job; });
  chat.msgs.push({ who: "err", text });
}

// Sends the chat's waiting messages one at a time, in order.
async function deliver(chat) {
  if (live[chat.id]) return;
  live[chat.id] = chat;
  for (let x; (x = chat.msgs.find((y) => y.job));) {
    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: x.job, mode: chat.mode, message: x.text, session_id: chat.sid, card: x.card.text, lesson: x.card.name }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || r.status);
      chat.sid = data.session_id;
      chat.msgs.splice(chat.msgs.indexOf(x) + 1, 0, { who: "bot", text: data.reply, card: x.card.ref });
      delete x.job;
      delete x.card;
    } catch (e) {
      if (leaving) return; // the page is going away: keep the job so the next load can resume it
      fail(chat, location.protocol === "file:"
        ? "Chat needs the server. Run: python3 server.py (in this folder), then open http://127.0.0.1:8765"
        : "Error: " + e.message);
    }
    save(chat);
    draw(chat);
  }
  delete live[chat.id];
  if (!$("log-history").hidden) showHistory(true);
}

function say(text, auto) {
  const m = modes[mode], card = currentCard(), sel = $("lesson");
  m.chat = m.chat || { id: crypto.randomUUID(), mode, time: Date.now(), sid: null, msgs: [] };
  m.chat.msgs.push({
    who: "me", text, auto, job: crypto.randomUUID(), at: Date.now(),
    card: { text: card.text.slice(0, 20000), name: sel.options[sel.selectedIndex].text, ref: { lesson: card.lesson, type: card.type, index: card.index } },
  });
  save(m.chat);
  draw(m.chat);
  deliver(m.chat);
}

function setMode(m) {
  mode = m;
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.mode === m));
  showHistory(false);
  $("msg").placeholder = modes[m].hint;
  if (m === "quiz" && !modes.quiz.chat) say("start", true);
}

function newChat() {
  modes[mode].chat = null;
  modes[mode].log.innerHTML = "";
  showHistory(false);
  if (mode === "quiz") say("start", true);
}

function setWidth(w) {
  const main = $("chat").parentNode;
  main.classList.toggle("sized", w > 0);
  main.style.setProperty("--chat-w", w + "px");
  store.set("chat-w", w);
}

const grip = $("chat-grip");
grip.onpointerdown = (e) => grip.setPointerCapture(e.pointerId);
grip.onpointermove = (e) => {
  if (grip.hasPointerCapture(e.pointerId)) setWidth(Math.max(380, Math.round($("chat").getBoundingClientRect().right - e.clientX - 8)));
};
grip.ondblclick = () => setWidth(0);
setWidth(+store.get("chat-w") || 0);

$("chat-toggle").onclick = () => { $("chat").hidden = !$("chat").hidden; };
document.querySelectorAll(".tabs button").forEach((b) => { b.onclick = () => setMode(b.dataset.mode); });
$("chat-new").onclick = newChat;
$("chat-history").onclick = () => showHistory($("log-history").hidden);
$("chat-form").onsubmit = (e) => {
  e.preventDefault();
  const text = $("msg").value.trim();
  if (!text) return;
  $("msg").value = "";
  showHistory(false);
  say(text);
};
$("msg").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("chat-form").requestSubmit(); }
});
addEventListener("beforeunload", () => { leaving = true; });
resume();
