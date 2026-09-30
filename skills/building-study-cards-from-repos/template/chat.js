const modes = {
  ask: { sid: null, chat: null, log: $("log-ask"), hint: "Ask a question about this card" },
  quiz: { sid: null, chat: null, log: $("log-quiz"), hint: "Type your answer, 'hint', 'skip', or 'stop'" },
};
let mode = "ask", pending = 0;

function addMsg(log, text, cls) {
  const d = document.createElement("div");
  d.className = "msg " + cls;
  d.textContent = text;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
  return d;
}

function proposal(log, raw, target) {
  let c;
  try { c = JSON.parse(raw); } catch { return; }
  const type = c.type === "qa" ? "qa" : "cards";
  const data = type === "qa" ? { q: c.q, a: c.a } : { t: c.t, b: c.b };
  const box = document.createElement("div");
  box.className = "msg proposal";
  box.innerHTML = `<p class="label">Suggested card</p><h3>${clean(data.t || data.q)}</h3><div>${clean(data.b || data.a)}</div>`;
  const save = (index, label) => {
    const b = document.createElement("button");
    b.textContent = label;
    b.onclick = async () => {
      b.disabled = true;
      const r = await fetch("/api/cards", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lesson: target.lesson, type, index, data }),
      });
      b.textContent = r.ok ? "Saved" : "Save failed";
      if (r.ok) reloadDeck();
    };
    box.appendChild(b);
  };
  linkRefs(box);
  if (!target.lesson) return;
  if (c.replace && target.type === type) save(target.index, "Replace this card");
  save(null, "Add as new card");
  log.appendChild(box);
  log.scrollTop = log.scrollHeight;
}

function showReply(log, el, reply, card) {
  const block = reply.match(/```card\s*([\s\S]*?)```/);
  el.innerHTML = markdown(reply.replace(/```card[\s\S]*?```/, "").trim());
  linkRefs(el);
  if (block) proposal(log, block[1], card);
}

async function send(message) {
  const at = mode, m = modes[at], log = m.log, sel = $("lesson"), card = currentCard();
  const wait = addMsg(log, "Claude is thinking...", "bot");
  pending++;
  try {
    const r = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: at, message, session_id: m.sid, card: card.text, lesson: sel.options[sel.selectedIndex].text }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || r.status);
    m.sid = data.session_id;
    showReply(log, wait, data.reply, card);
    record(m, at, { who: "bot", text: data.reply, card: { lesson: card.lesson, type: card.type, index: card.index } });
  } catch (e) {
    wait.className = "msg err";
    wait.textContent = location.protocol === "file:"
      ? "Chat needs the server. Run: python3 server.py (in this folder), then open http://127.0.0.1:8765"
      : "Error: " + e.message;
  }
  pending--;
}

function setMode(m) {
  mode = m;
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.mode === m));
  showHistory(false);
  $("msg").placeholder = modes[m].hint;
  if (m === "quiz" && !modes.quiz.log.children.length) send("start");
}

function newChat() {
  if (pending) return;
  modes[mode].sid = modes[mode].chat = null;
  modes[mode].log.innerHTML = "";
  showHistory(false);
  if (mode === "quiz") send("start");
}

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
  addMsg(modes[mode].log, text, "me");
  record(modes[mode], mode, { who: "me", text });
  send(text);
};
$("msg").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("chat-form").requestSubmit(); }
});
