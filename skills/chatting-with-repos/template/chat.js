// A chat record is the source of truth: { id, time, sid, msgs }. A "me" message keeps a job id until its reply is in.
// The server keeps each result by job id, so sending the same job again (after a page refresh) returns the same reply.
const $ = (id) => document.getElementById(id);
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); return true; } catch { return false; } },
};
const live = {}; // chats with a running sender, by id
const STALE = 10 * 60 * 1000; // a waiting message older than this is not sent again
let shown = null, leaving = false;

// crypto.randomUUID needs HTTPS or localhost; this also works on plain HTTP over the local network.
// The server only takes ids shaped like a UUID (36 chars).
const newId = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, "0")).join("")
  .replace(/^(.{8})(.{4})(.{4})(.{4})(.{12})$/, "$1-$2-$3-$4-$5");

function addMsg(text, cls) {
  const log = $("log"), d = document.createElement("div");
  d.className = "msg " + cls;
  d.textContent = text;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
  return d;
}

function draw(chat) {
  if (shown !== chat) return;
  $("log").innerHTML = "";
  for (const x of chat.msgs) {
    if (x.who !== "bot") { addMsg(x.text, x.who); continue; }
    const el = addMsg("", "bot");
    el.innerHTML = markdown(x.text);
    linkRefs(el);
    colorBlocks(el);
  }
  if (chat.msgs.some((x) => x.job)) addMsg("Claude is thinking...", "bot");
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
        body: JSON.stringify({ id: x.job, message: x.text, session_id: chat.sid }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || r.status);
      chat.sid = data.session_id;
      chat.msgs.splice(chat.msgs.indexOf(x) + 1, 0, { who: "bot", text: data.reply });
      delete x.job;
    } catch (e) {
      if (leaving) return; // the page is going away: keep the job so the next load can resume it
      fail(chat, "Error: " + e.message);
    }
    save(chat);
    draw(chat);
  }
  delete live[chat.id];
  if (!$("log-history").hidden) showHistory(true);
}

function say(text) {
  shown = shown || { id: newId(), time: Date.now(), sid: null, msgs: [] };
  shown.msgs.push({ who: "me", text, job: newId(), at: Date.now() });
  save(shown);
  draw(shown);
  deliver(shown);
}

$("chat-new").onclick = () => {
  shown = null;
  $("log").innerHTML = "";
  showHistory(false);
  $("msg").focus();
};
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
