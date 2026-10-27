// Small markdown renderer for chat replies: code blocks, inline code, bold, italic, links, headings, lists, tables.
// Text is escaped first, so raw HTML in a reply always shows as text.
// Links: [text](url) and bare URLs, only http(s) or a same-site path, so javascript: and data: never become links.
function markdown(text) {
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const link = (keep, label, url) => {
    url = url.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
    if (!/^(https?:\/\/|\/(?![\/\\]))/i.test(url)) return label;
    const href = esc(url).replace(/"/g, "&quot;");
    return `\x01${keep.push(`<a href="${href}" title="${href}" target="_blank" rel="noopener noreferrer">${label}</a>`) - 1}\x01`;
  };
  // A bare URL leaves out the end punctuation of the sentence, and a ")" it did not open.
  const bare = (url) => {
    let end = "";
    for (let m; (m = url.match(/(&amp;|[.,;:!?']|\))$/)) && (m[1] !== ")" || url.split("(").length < url.split(")").length);) {
      end = m[1] + end;
      url = url.slice(0, -m[1].length);
    }
    return link(bare.keep, url, url) + end;
  };
  // Inline code and links are taken out first so bold/italic never change what is inside them.
  const inline = (s) => {
    const codes = [], links = bare.keep = [];
    return esc(s)
      .replace(/`([^`]+)`/g, (_, c) => `\x00${codes.push(c) - 1}\x00`)
      .replace(/\[([^\]\x00]+)\]\(([^()\s]+)\)/g, (_, label, url) => link(links, label, url))
      .replace(/https?:\/\/(?:(?!&[lg]t;)[^\s\x00\x01"*])+/g, bare)
      .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
      .replace(/(^|[^\w*])\*([^*\s](?:[^*]*[^*\s])?)\*(?!\w)/g, "$1<i>$2</i>")
      .replace(/\x00(\d+)\x00/g, (_, n) => `<code>${codes[n]}</code>`)
      .replace(/\x01(\d+)\x01/g, (_, n) => links[n]);
  };
  const isRow = (l) => /^\s*\|.+\|\s*$/.test(l ?? "");
  const tr = (row, tag) => "<tr>" + row.trim().replace(/^\||\|$/g, "").split("|")
    .map((c) => `<${tag}>${inline(c.trim())}</${tag}>`).join("") + "</tr>";
  const lines = text.replace(/[\x00\x01]/g, "").split("\n"), out = [];
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
