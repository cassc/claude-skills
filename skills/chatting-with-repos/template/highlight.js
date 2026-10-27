// Code colors, by highlight.js from the CDN (see index.html). With no internet, hljs is missing and code stays plain text.
const MAX_COLOR = 200000; // characters; a larger file stays plain

// Colors every <pre><code> in el. <code class="language-py"> names the language; with no class, hljs guesses.
function colorBlocks(el) {
  if (!window.hljs) return;
  el.querySelectorAll("pre code").forEach((c) => {
    const lang = c.className.replace("language-", "");
    c.innerHTML = (hljs.getLanguage(lang) ? hljs.highlight(c.textContent, { language: lang }) : hljs.highlightAuto(c.textContent)).value;
  });
}

// One HTML string per line of a file. The language comes from the file name's last part (py, js, Makefile).
// A span that crosses a line end (a long comment or string) is closed there and opened again on the next line.
function colorLines(text, path) {
  const lang = path.split(/[./]/).pop();
  if (!window.hljs || text.length > MAX_COLOR || !hljs.getLanguage(lang)) {
    return text.split("\n").map((l) => l.replace(/&/g, "&amp;").replace(/</g, "&lt;"));
  }
  const open = [];
  return hljs.highlight(text, { language: lang }).value.split("\n").map((line) => {
    const start = open.join("");
    for (const [tag] of line.matchAll(/<span[^>]*>|<\/span>/g)) tag[1] === "/" ? open.pop() : open.push(tag);
    return start + line + "</span>".repeat(open.length);
  });
}
