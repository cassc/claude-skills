const $ = (id) => document.getElementById(id);
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); return true; } catch { return false; } },
};

let slides = [], i = 0, answers = {};
const ALLOWED = new Set(["B", "I", "CODE", "PRE", "BR", "OL", "UL", "LI"]);

// Card text may come from Claude, which reads repo files: keep only simple tags, no attributes
// (but <code class="language-py"> keeps its class, for the code colors).
function clean(html) {
  const t = document.createElement("template");
  t.innerHTML = html ?? "";
  const walk = (node) => {
    for (const c of [...node.childNodes]) {
      if (c.nodeType === 1) {
        walk(c);
        if (ALLOWED.has(c.tagName)) [...c.attributes].forEach((a) => { if (c.tagName !== "CODE" || a.name !== "class" || !/^language-\w+$/.test(a.value)) c.removeAttribute(a.name); });
        else c.replaceWith(...c.childNodes);
      } else if (c.nodeType !== 3) c.remove();
    }
  };
  walk(t.content);
  return t.innerHTML;
}

// A card's graph, shown under its text: img = repo-relative path, art = a plain text drawing.
function graph(c) {
  const src = c.img && "../" + encodeURI(c.img);
  if (src) return `<a href="${src}" target="_blank" title="Open full size"><img src="${src}" alt="graph"></a>`;
  return c.art ? `<pre class="art">${c.art.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</pre>` : "";
}
const BASE = structuredClone(LESSONS);

async function loadExtras() {
  LESSONS.forEach((l, n) => { l.cards = structuredClone(BASE[n].cards); l.qa = structuredClone(BASE[n].qa); });
  try {
    const r = await fetch("extra-cards.json", { cache: "no-store" });
    for (const e of r.ok ? await r.json() : []) {
      const arr = LESSONS.find((l) => l.id === e.lesson)?.[e.type];
      if (!arr) continue;
      if (Number.isInteger(e.index) && e.index < arr.length) arr[e.index] = { ...e.data, fp: arr[e.index].fp };
      else arr.push(e.data);
    }
  } catch {}
}

async function reloadDeck() {
  await loadExtras();
  const k = i;
  slides = build($("lesson").value);
  i = Math.min(k, slides.length - 1);
  render();
}

function currentCard() {
  const s = slides[i];
  if (s.type) return { lesson: s.l.id, type: s.type, index: s.idx, text: `L${s.l.id} ${s.l.title} - ${s.kind}: ${s.t || s.q} | ${s.b || s.a}${s.img || s.art ? " | the card shows a graph" : ""}` };
  if (s.kind === "Diagram") return { lesson: s.l.id, text: `L${s.l.id} diagram "${s.d.t}", step ${s.step + 1}: ${s.d.steps[s.step].s}` };
  if (s.kind === "Module map") return { lesson: s.l.id, text: "module map: " + LESSONS.filter((l) => l.job).map((l) => `L${l.id} ${l.title} - ${l.job} (uses: ${(l.uses || []).join(", ") || "none"}; entry: ${l.entry || "none"})`).join("; ") };
  return { lesson: s.l?.id, text: s.l ? `L${s.l.id} ${s.l.title} - quiz: ${s.item.q}` : "quiz result page" };
}

function build(id, only) {
  const lessons = id === "all" ? LESSONS : LESSONS.filter((l) => l.id === id);
  const s = [];
  if (!only) {
    for (const l of lessons) {
      l.cards.forEach((c, idx) => {
        s.push({ kind: c.fp ? "First principle" : "Concept", l, type: "cards", idx, ...c });
        if (idx) return;
        if (l === LESSONS[0] && LESSONS.some((x) => x.job)) s.push({ kind: "Module map", l });
        for (const d of DIAGRAMS[l.id] || []) s.push({ kind: "Diagram", l, d, step: 0 });
      });
      l.qa.forEach((c, idx) => s.push({ kind: "Likely question", l, type: "qa", idx, ...c }));
    }
  }
  for (const l of lessons) {
    QUIZ[l.id].forEach((item, n) => {
      const key = l.id + "-" + n;
      const order = item.o.map((_, n) => n).sort(() => Math.random() - 0.5);
      const it = { ...item, o: order.map((n) => item.o[n]), a: order.indexOf(item.a) };
      if (!only || only.has(key)) s.push({ kind: "Quiz", l, item: it, key });
    });
  }
  s.push({ kind: "Result" });
  return s;
}

function start(id, only) {
  slides = build(id, only);
  answers = {};
  i = only ? 0 : Math.min(+store.get("pos:" + id) || 0, slides.length - 1);
  render();
}

function render() {
  const s = slides[i], card = $("card");
  $("kind").textContent = s.l ? `${s.kind} - L${s.l.id} ${s.l.title}` : s.kind;
  $("pos").textContent = `${i + 1} / ${slides.length}`;
  $("bar").style.width = ((i + 1) / slides.length) * 100 + "%";
  $("prev").disabled = i === 0;
  $("next").disabled = i === slides.length - 1;
  card.className = s.kind.split(" ")[0].toLowerCase();
  if (s.type === "cards") card.innerHTML = `<h2>${clean(s.t)}</h2><div>${clean(s.b)}</div>${graph(s)}`;
  else if (s.kind === "Likely question") {
    card.innerHTML = `<h2>${clean(s.q)}</h2>` + (s.shown
      ? `<div class="answer">${clean(s.a)}</div>${graph(s)}`
      : `<button class="reveal">Show answer (space)</button>`);
  } else if (s.kind === "Diagram") renderDiagram(s, card);
  else if (s.kind === "Module map") renderMap(card);
  else if (s.kind === "Quiz") renderQuiz(s, card);
  else renderResult(card);
  linkRefs(card);
  colorBlocks(card);
  store.set("pos:" + $("lesson").value, i);
}

function renderDiagram(s, card) {
  const src = s.d.img && `../${s.d.img}`, art = !src && s.d.art, cur = s.d.steps[s.step];
  card.innerHTML = `<h2>${s.d.t}</h2>
    <div class="dia${src || art ? "" : " noimg"}">${src ? `<a href="${src}" target="_blank" title="Open full size"><img src="${src}" alt="${s.d.img} diagram"></a>` : ""}${art ? '<pre class="art"></pre>' : ""}
    <div><ol class="steps">${s.d.steps.map((x, n) => `<li data-n="${n}" class="${n === s.step ? "on" : n < s.step ? "done" : ""}">${x.s}${x.loop ? ' <span class="loop">loop</span>' : ""}</li>`).join("")}</ol>
    <p class="note">${cur.n || "&nbsp;"}</p></div></div>`;
  if (art) card.querySelector(".art").textContent = art;
}

function renderMap(card) {
  const name = (id) => LESSONS.find((l) => l.id === id)?.title || id;
  card.innerHTML = `<h2>Module map</h2><div class="tbl"><table><tr><th>Module</th><th>Job</th><th>Uses</th><th>Entry</th></tr>` +
    LESSONS.filter((l) => l.job).map((l) => `<tr><td><button class="jump" data-id="${l.id}">L${l.id} ${l.title}</button></td>
      <td>${clean(l.job)}</td><td>${(l.uses || []).map(name).join(", ")}</td>
      <td>${l.entry ? `<code>${clean(l.entry)}</code>` : ""}</td></tr>`).join("") + "</table></div>";
}

function renderQuiz(s, card) {
  const picked = answers[s.key];
  card.innerHTML = `<h2>${s.item.q}</h2>` + s.item.o.map((o, n) => {
    let cls = "";
    if (picked !== undefined) cls = n === s.item.a ? "right" : n === picked ? "wrong" : "";
    return `<button class="opt ${cls}" data-n="${n}" ${picked !== undefined ? "disabled" : ""}>${o}</button>`;
  }).join("") + (picked !== undefined ? `<p class="explain">${s.item.e}</p>` : "");
}

function renderResult(card) {
  const qs = slides.filter((s) => s.kind === "Quiz");
  const right = qs.filter((s) => answers[s.key] === s.item.a).length;
  const wrong = qs.filter((s) => answers[s.key] !== s.item.a).map((s) => s.key);
  card.innerHTML = `<h2>Score: ${right} / ${qs.length}</h2>` +
    (wrong.length ? `<button id="retry">Retry wrong or skipped (${wrong.length})</button>` : "<p>All right.</p>") +
    `<button id="restart">Start again</button>` +
    `<p>Next: open <b>Claude</b> -> <b>Quiz me</b> for open "why" questions with graded answers.</p>`;
  card.dataset.wrong = wrong.join(",");
}

function go(d) { i = Math.max(0, Math.min(slides.length - 1, i + d)); render(); }

$("card").addEventListener("click", (e) => {
  const s = slides[i], t = e.target;
  if (t.classList.contains("reveal")) { s.shown = true; render(); }
  else if (t.closest(".steps li")) { s.step = +t.closest("li").dataset.n; render(); }
  else if (t.classList.contains("opt")) { answers[s.key] = +t.dataset.n; render(); }
  else if (t.classList.contains("jump")) { sel.value = t.dataset.id; sel.onchange(); }
  else if (t.id === "retry") start($("lesson").value, new Set($("card").dataset.wrong.split(",")));
  else if (t.id === "restart") { store.set("pos:" + $("lesson").value, 0); start($("lesson").value); }
});
$("prev").onclick = () => go(-1);
$("next").onclick = () => go(1);
document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT" || $("src").open) return;
  if (e.key === "ArrowRight") go(1);
  else if (e.key === "ArrowLeft") go(-1);
  else if (e.key === " " && slides[i].kind === "Likely question") {
    e.preventDefault();
    slides[i].shown = !slides[i].shown;
    render();
  } else if (e.key === " " && slides[i].kind === "Diagram") {
    e.preventDefault();
    const s = slides[i];
    s.step = (s.step + 1) % s.d.steps.length;
    render();
  }
});

const sel = $("lesson");
sel.innerHTML = `<option value="all">All lessons</option>` +
  LESSONS.map((l) => `<option value="${l.id}">L${l.id} ${l.title}</option>`).join("");
sel.value = store.get("lesson") || LESSONS[0].id;
sel.onchange = () => { store.set("lesson", sel.value); start(sel.value); };
loadExtras().then(() => start(sel.value));
