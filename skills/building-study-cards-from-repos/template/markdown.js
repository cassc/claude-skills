// Small markdown renderer for chat replies: code blocks, inline code, bold, italic, headings, lists, tables.
// Text is escaped first, so raw HTML in a reply always shows as text.
function markdown(text) {
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  // Inline code is taken out first so bold/italic never change what is inside it.
  const inline = (s) => {
    const codes = [];
    return esc(s)
      .replace(/`([^`]+)`/g, (_, c) => `\x00${codes.push(c) - 1}\x00`)
      .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
      .replace(/(^|[^\w*])\*([^*\s](?:[^*]*[^*\s])?)\*(?!\w)/g, "$1<i>$2</i>")
      .replace(/\x00(\d+)\x00/g, (_, n) => `<code>${codes[n]}</code>`);
  };
  const isRow = (l) => /^\s*\|.+\|\s*$/.test(l ?? "");
  const tr = (row, tag) => "<tr>" + row.trim().replace(/^\||\|$/g, "").split("|")
    .map((c) => `<${tag}>${inline(c.trim())}</${tag}>`).join("") + "</tr>";
  const lines = text.replace(/\x00/g, "").split("\n"), out = [];
  let n = 0, m, para = [];
  const flush = () => { if (para.length) out.push(`<p>${para.map(inline).join("<br>")}</p>`); para = []; };

  while (n < lines.length) {
    const l = lines[n];
    if (/^\s*```/.test(l)) {
      const body = [];
      for (n++; n < lines.length && !/^\s*```\s*$/.test(lines[n]); n++) body.push(lines[n]);
      n++;
      flush();
      out.push(`<pre><code>${esc(body.join("\n"))}</code></pre>`);
    } else if ((m = l.match(/^(#{1,3})\s+(.+)$/))) {
      flush();
      out.push(`<h${m[1].length + 3}>${inline(m[2])}</h${m[1].length + 3}>`);
      n++;
    } else if (/^\s*(-{3,}|\*{3,})\s*$/.test(l)) {
      flush();
      out.push("<hr>");
      n++;
    } else if ((m = l.match(/^\s*(?:[-*]|(\d+)[.)])\s+/))) {
      flush();
      const item = m[1] ? /^\s*\d+[.)]\s+(.*)$/ : /^\s*[-*]\s+(.*)$/, items = [];
      const open = m[1] ? `<ol start="${+m[1]}">` : "<ul>";
      for (; n < lines.length && (m = lines[n].match(item)); n++) items.push(`<li>${inline(m[1])}</li>`);
      out.push(open + items.join("") + (open === "<ul>" ? "</ul>" : "</ol>"));
    } else if (isRow(l) && /^\s*\|[ :|-]*-[ :|-]*\|\s*$/.test(lines[n + 1] ?? "")) {
      flush();
      let rows = tr(l, "th");
      for (n += 2; isRow(lines[n]); n++) rows += tr(lines[n], "td");
      out.push(`<div class="tbl"><table>${rows}</table></div>`);
    } else {
      if (l.trim()) para.push(l); else flush();
      n++;
    }
  }
  flush();
  return out.join("");
}
