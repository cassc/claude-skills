// Code references: <code>path/file.ext:12</code> or <code>path/file.ext:12-30</code> (path from the repo root) open the file in a popup.
// The popup also lists the repo's files. "#src=path:12" in the page address opens it full-window (the "Open in new tab" link).
const REF = /^([\w.@+\/-]+):(\d+)(?:-(\d+))?$/;
const SHOWN = 200;
let files = null, current = "";

function parseRef(text) {
  const m = text.trim().match(REF);
  return m && (m[1].includes("/") || /\.[a-z]\w*$/i.test(m[1])) ? m : null;
}

function linkRefs(el) {
  el.querySelectorAll(":not(pre) > code").forEach((c) => { if (parseRef(c.textContent)) c.classList.add("ref"); });
}

function listFiles() {
  const q = $("src-filter").value.toLowerCase(), list = $("src-files");
  list.innerHTML = "";
  (files || []).filter((p) => p.toLowerCase().includes(q)).slice(0, SHOWN).forEach((p) => {
    const b = document.createElement("button");
    b.textContent = p;
    if (p === current) b.className = "on";
    list.appendChild(b);
  });
  list.querySelector(".on")?.scrollIntoView({ block: "nearest" });
}

async function showSource(ref) {
  ref = ref.trim();
  const [, path, from, to] = parseRef(ref) || [0, ref], pre = $("src-code");
  current = path;
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
  if (c) showSource(c.textContent);
  else if (e.target.id === "files") showSource("");
});

document.addEventListener("DOMContentLoaded", () => {
  $("src-filter").oninput = listFiles;
  $("src-filter").onkeydown = (e) => { if (e.key === "Enter") $("src-files").firstChild?.click(); };
  if (!location.hash.startsWith("#src=")) return;
  $("src").classList.add("full");
  showSource(decodeURIComponent(location.hash.slice(5)));
});
