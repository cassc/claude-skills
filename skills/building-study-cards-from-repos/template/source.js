// Code references: <code>path/file.ext:12</code> or <code>path/file.ext:12-30</code> (path from the repo root) open the file in a popup.
const REF = /^([\w.@+\/-]+):(\d+)(?:-(\d+))?$/;

function parseRef(text) {
  const m = text.trim().match(REF);
  return m && (m[1].includes("/") || /\.[a-z]\w*$/i.test(m[1])) ? m : null;
}

function linkRefs(el) {
  el.querySelectorAll("code").forEach((c) => { if (parseRef(c.textContent)) c.classList.add("ref"); });
}

async function showSource(ref) {
  const [, path, from, to] = parseRef(ref);
  const url = "/api/source?path=" + encodeURIComponent(path), pre = $("src-code");
  $("src-title").textContent = ref.trim();
  $("src-title").href = url;
  pre.textContent = "Loading...";
  $("src").showModal();
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error(r.status);
    pre.textContent = "";
    (await r.text()).replace(/\n$/, "").split("\n").forEach((text, n) => {
      const line = document.createElement("span");
      line.textContent = text;
      if (n + 1 >= +from && n + 1 <= +(to || from)) line.className = "hit";
      pre.appendChild(line);
    });
    pre.querySelector(".hit")?.scrollIntoView({ block: "center" });
  } catch (e) {
    pre.textContent = location.protocol === "file:"
      ? "Source view needs the server. Run: python3 server.py (in this folder), then open http://127.0.0.1:8765"
      : `Cannot open ${path} (${e.message})`;
  }
}

document.addEventListener("click", (e) => {
  const c = e.target.closest("code.ref");
  if (c) showSource(c.textContent);
});
