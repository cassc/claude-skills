const modes = {
  ask: { sid: null, log: $("log-ask"), hint: "Ask a question about this card" },
  quiz: { sid: null, log: $("log-quiz"), hint: "Type your answer, 'hint', 'skip', or 'stop'" },
};
let mode = "ask";

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

async function send(message) {
  const m = modes[mode], log = m.log, sel = $("lesson"), card = currentCard();
  const wait = addMsg(log, "Claude is thinking...", "bot");
  try {
    const r = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode, message, session_id: m.sid, card: card.text, lesson: sel.options[sel.selectedIndex].text }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || r.status);
    m.sid = data.session_id;
    const block = data.reply.match(/```card\s*([\s\S]*?)```/);
    wait.innerHTML = markdown(data.reply.replace(/```card[\s\S]*?```/, "").trim());
    linkRefs(wait);
    if (block) proposal(log, block[1], card);
  } catch (e) {
    wait.className = "msg err";
    wait.textContent = location.protocol === "file:"
      ? "Chat needs the server. Run: python3 server.py (in this folder), then open http://127.0.0.1:8765"
      : "Error: " + e.message;
  }
}

function setMode(m) {
  mode = m;
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.mode === m));
  for (const k in modes) modes[k].log.hidden = k !== m;
  $("msg").placeholder = modes[m].hint;
  if (m === "quiz" && !modes.quiz.log.children.length) send("start");
}

function newChat() {
  modes[mode].sid = null;
  modes[mode].log.innerHTML = "";
  if (mode === "quiz") send("start");
}

$("chat-toggle").onclick = () => { $("chat").hidden = !$("chat").hidden; };
document.querySelectorAll(".tabs button").forEach((b) => { b.onclick = () => setMode(b.dataset.mode); });
$("chat-new").onclick = newChat;
$("chat-form").onsubmit = (e) => {
  e.preventDefault();
  const text = $("msg").value.trim();
  if (!text) return;
  $("msg").value = "";
  addMsg(modes[mode].log, text, "me");
  send(text);
};
$("msg").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("chat-form").requestSubmit(); }
});
