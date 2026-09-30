// Code references: <code>path/file.ext:12</code> or <code>path/file.ext:12-30</code> (path from the repo root) open the file in a popup.
// The popup also shows the repo's files as a folding tree (a flat list while the filter has text)."#src=path:12" in the page address opens it full-window (the "Open in new tab" link).
const REF = /^([\w.@+\/-]+):(\d+)(?:-(\d+))?$/;
const SHOWN = 200;
let files = null, current = "";
const opened = new Set(); // open folders of the tree

function parseRef(text) {
  const m = text.trim().match(REF);
  return m && (m[1].includes("/") || /\.[a-z]\w*$/i.test(m[1])) ? m : null;
}

function linkRefs(el) {
  el.querySelectorAll(":not(pre) > code").forEach((c) => { if (parseRef(c.textContent)) c.classList.add("ref"); });
}

function row(list, path, name, indent, cls) {
  const b = document.createElement("button");
  b.textContent = name;
  b.title = b.dataset.path = path;
  b.className = cls + (path === current ? " on" : "");
  b.style.paddingLeft = 6 + indent * 14 + "px";
  list.appendChild(b);
}

// One folder of the tree: sub-folders first, then files. A folder path ends with "/". Only open folders get rows.
function drawDir(list, dir, depth) {
  const dirs = new Set(), own = [];
  for (const p of files) {
    if (!p.startsWith(dir)) continue;
    const rest = p.slice(dir.length), i = rest.indexOf("/");
    if (i < 0) own.push(rest); else dirs.add(rest.slice(0, i + 1));
  }
  for (const d of [...dirs].sort()) {
    const open = opened.has(dir + d);
    row(list, dir + d, d.slice(0, -1), depth, open ? "node dir open" : "node dir");
    if (open) drawDir(list, dir + d, depth + 1);
  }
  own.slice(0, SHOWN).forEach((f) => row(list, dir + f, f, depth + 1, "node"));
  if (own.length > SHOWN) {
    const more = document.createElement("p");
    more.className = "hint";
    more.textContent = `${own.length - SHOWN} more: use the filter`;
    list.appendChild(more);
  }
}

function listFiles() {
  const q = $("src-filter").value.toLowerCase(), list = $("src-files");
  if (!files) return;
  list.innerHTML = "";
  if (q) files.filter((p) => p.toLowerCase().includes(q)).slice(0, SHOWN).forEach((p) => row(list, p, p, 0, ""));
  else drawDir(list, "", 0);
  list.querySelector(".on")?.scrollIntoView({ block: "nearest" });
}

async function showSource(ref) {
  ref = ref.trim();
  const [, path, from, to] = parseRef(ref) || [0, ref], pre = $("src-code");
  current = path;
  for (let i = path.indexOf("/"); i > 0; i = path.indexOf("/", i + 1)) opened.add(path.slice(0, i + 1));
  $("src-title").textContent = ref || "Pick a file";
  $("src-tab").href = "#src=" + encodeURIComponent(ref);
  pre.textContent = path ? "Loading..." : "";
  if (!$("src").open) $("src").showModal();
  try {
    files = files || await (await fetch("/api/files")).json();
    listFiles();
    if (!path) return $("src-filter").focus();
    const r = await fetch("/api/source?path=" + encodeURIComponent(path));
    if (!r.ok) throw new Error(r.status);
    pre.textContent = "";
    (await r.text()).replace(/\n$/, "").split("\n").forEach((text, n) => {
      const line = document.createElement("span");
      line.textContent = text;
      if (n + 1 >= +from && n + 1 <= +(to || from)) line.className = "hit";
      pre.appendChild(line);
    });
    pre.scrollTop = 0;
    pre.querySelector(".hit")?.scrollIntoView({ block: "center" });
  } catch (e) {
    pre.textContent = location.protocol === "file:"
      ? "Source view needs the server. Run: python3 server.py (in this folder), then open http://127.0.0.1:8765"
      : `Cannot open ${path || "the file list"} (${e.message})`;
  }
}

document.addEventListener("click", (e) => {
  const c = e.target.closest("code.ref, #src-files button");
  const path = c && (c.dataset.path || c.textContent);
  if (c && path.endsWith("/")) {
    if (!opened.delete(path)) opened.add(path);
    listFiles();
  } else if (c) showSource(path);
  else if (e.target.id === "files") showSource("");
});

document.addEventListener("DOMContentLoaded", () => {
  $("src-filter").oninput = listFiles;
  $("src-filter").onkeydown = (e) => { if (e.key === "Enter") $("src-files").firstChild?.click(); };
  if (!location.hash.startsWith("#src=")) return;
  $("src").classList.add("full");
  showSource(decodeURIComponent(location.hash.slice(5)));
});
