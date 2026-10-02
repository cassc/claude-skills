"""Serve the study cards and let Claude Code tutor/quiz you: python3 <this dir>/server.py"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

HOST, PORT = "127.0.0.1", int(os.environ.get("PORT", 8765))
WEB = Path(__file__).resolve().parent
ROOT = WEB.parent
EXTRA = WEB / "extra-cards.json"
PROMPTS = {m: (WEB / f"{m}_prompt.md").read_text() for m in ("ask", "quiz")}
ORIGINS = {f"http://{HOST}:{PORT}", f"http://localhost:{PORT}"}
HOSTS = {o.split("//")[1] for o in ORIGINS}
ASSETS = {f"{WEB.name}/diagrams"}  # repo-relative image dirs the page may load
MAX_SOURCE = 1_000_000  # bytes; larger files are not shown in the source popup
MAX_FILES = 5000  # cap for the file list when the folder is not a git repo
SESSION = re.compile(r"^[0-9a-f-]{36}$")
FIELDS = {"cards": ("t", "b"), "qa": ("q", "a")}
DIAGRAMS = WEB / "diagrams"  # graphs made in chat are saved here
MAX_DIAGRAM = 20_000  # characters of diagram source
IMG = re.compile(rf"{re.escape(WEB.name)}/diagrams/[0-9a-f]{{16}}\.svg")
# Diagram kind -> local command that reads the source on stdin and writes SVG to stdout, in the order to try.
# mermaid has no such mode: see render().
TOOLS = {"plantuml": ["plantuml", "-tsvg", "-pipe"], "dot": ["dot", "-Tsvg"], "mermaid": ["mmdc"], "d2": ["d2", "-", "-"]}
UNSAFE_SVG = re.compile(r"<script|<foreignObject|\bon\w+\s*=|javascript:|(?:href|src)\s*=\s*[\"'](?!#)|url\(\s*[\"']?(?!#)", re.I)
PROMPTS["ask"] += f"\nDiagram tools on this machine: {', '.join(k for k, c in TOOLS.items() if shutil.which(c[0])) or 'none'}.\n"
KEEP = 20  # chat results kept in memory, by message id
jobs: dict[str, dict] = {}
lock = threading.Lock()


def ask_claude(message: str, mode: str, session_id: str | None) -> dict:
    cmd = ["claude", "-p", "--output-format", "json", "--append-system-prompt", PROMPTS[mode],
           "--tools", "Read,Grep,Glob", "--strict-mcp-config",
           "--permission-mode", "dontAsk", "--disallowedTools", "Read(**/.env)", "Read(**/.env.*)"]
    if session_id:
        cmd += ["--resume", session_id]
    out = subprocess.run(cmd, input=message, cwd=ROOT, capture_output=True, text=True, timeout=300)
    if out.returncode:
        raise RuntimeError(out.stderr.strip() or out.stdout.strip() or "claude failed")
    data = json.loads(out.stdout)
    return {"reply": data.get("result", ""), "session_id": data.get("session_id")}


def chat(body: dict) -> dict:
    mode, sid, job_id = body.get("mode", "quiz"), body.get("session_id"), body.get("id")
    if mode not in PROMPTS or (sid and not SESSION.match(sid)) or not (isinstance(job_id, str) and SESSION.match(job_id)):
        raise ValueError("bad mode, session id or message id")
    with lock:
        job = jobs.get(job_id)
        if first := job is None:
            job = jobs[job_id] = {"done": threading.Event()}
            for old in list(jobs)[:-KEEP]:
                del jobs[old]
    if first:  # the same id again (a page refresh) waits for this run and gets the same result
        msg = body.get("message", "").strip()
        if mode == "ask":
            msg = f"[Current card: {str(body.get('card', ''))[:20000]}]\n{msg}"
        elif not sid:
            msg = f"Quiz me on: {body.get('lesson', 'all lessons')}. {msg}".strip()
        try:
            job["res"] = ask_claude(msg, mode, sid)
        except Exception as e:
            job["err"] = e
        job["done"].set()
    job["done"].wait()
    if "err" in job:
        raise job["err"]
    return job["res"]


def render(kind: str, src: str) -> str:
    if kind == "svg":
        if not src.lstrip().startswith("<svg") or UNSAFE_SVG.search(src):
            raise ValueError("the SVG must start with <svg and have no scripts, links or outside files")
        return src
    try:
        if kind == "mermaid":
            with tempfile.TemporaryDirectory() as d:
                Path(d, "in.mmd").write_text(src)
                out = subprocess.run(["mmdc", "-q", "-i", f"{d}/in.mmd", "-o", f"{d}/out.svg"],
                                     capture_output=True, text=True, timeout=60)
                svg = Path(d, "out.svg").read_text() if not out.returncode else ""
        else:
            out = subprocess.run(TOOLS[kind], input=src, capture_output=True, text=True, timeout=60)
            svg = out.stdout
    except OSError:
        raise ValueError(f"{kind} is not installed")
    if out.returncode or "<svg" not in svg:
        raise ValueError((out.stderr.strip() or f"{kind} failed")[:500])
    return svg


def diagram(body: dict) -> dict:
    """Draw a graph that Claude wrote in chat. The same source gives the same file."""
    kind, src = body.get("kind"), body.get("src")
    if kind not in (*TOOLS, "svg") or not isinstance(src, str) or not src.strip() or len(src) > MAX_DIAGRAM:
        raise ValueError("bad diagram")
    file = DIAGRAMS / (hashlib.sha256(f"{kind}\n{src}".encode()).hexdigest()[:16] + ".svg")
    if not file.exists():
        svg = render(kind, src)
        DIAGRAMS.mkdir(exist_ok=True)
        tmp = file.with_suffix(".tmp")
        tmp.write_text(svg)
        tmp.replace(file)
    return {"path": file.relative_to(ROOT).as_posix()}


def save_card(body: dict) -> dict:
    lesson, typ, index, data = body.get("lesson"), body.get("type", ""), body.get("index"), body.get("data", {})
    keys = FIELDS.get(typ)
    if not (isinstance(lesson, str) and re.fullmatch(r"[\w-]{1,40}", lesson) and keys
            and (index is None or isinstance(index, int))
            and all(isinstance(data.get(k), str) and data[k].strip() for k in keys)):
        raise ValueError("bad card")
    graph = {k: data[k] for k in ("img", "art") if k in data}  # optional: a graph made in chat
    if (not all(isinstance(v, str) and len(v) <= MAX_DIAGRAM for v in graph.values())
            or ("img" in graph and not IMG.fullmatch(graph["img"]))):
        raise ValueError("bad graph")
    with lock:
        items = json.loads(EXTRA.read_text()) if EXTRA.exists() else []
        items.append({"lesson": lesson, "type": typ, "index": index, "data": {k: data[k] for k in keys} | graph})
        tmp = EXTRA.with_suffix(".tmp")
        tmp.write_text(json.dumps(items, indent=1, ensure_ascii=False) + "\n")
        tmp.replace(EXTRA)
    return {"ok": True}


def files() -> list[str]:
    """Repo files the popup may show: tracked or new, not git-ignored, no dot parts."""
    try:
        out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\0")
    except (OSError, subprocess.CalledProcessError):  # no git, or not a git repo: walk the folder
        out = []
        for d, dirs, names in os.walk(ROOT):
            dirs[:] = [x for x in dirs if not x.startswith(".")]
            out += [(Path(d) / n).relative_to(ROOT).as_posix() for n in names]
            if len(out) >= MAX_FILES:
                break
        out = out[:MAX_FILES]
    return sorted(p for p in out if p and not any(x.startswith(".") for x in p.split("/")))


def source(path: str) -> bytes:
    file = (ROOT / path).resolve()
    rel = file.relative_to(ROOT)  # ValueError if outside the repo
    if rel.as_posix() not in files() or not file.is_file() or file.stat().st_size > MAX_SOURCE:
        raise ValueError("bad path")
    data = file.read_bytes()
    data.decode()  # binary files raise UnicodeDecodeError, a ValueError
    return data


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        rel = Path(path.split("?")[0].lstrip("/"))
        if str(rel.parent) in ASSETS and rel.name not in ("", ".", ".."):
            return str(ROOT / rel.parent / rel.name)
        return super().translate_path(path)

    def end_headers(self):
        if self.path.split("?")[0].endswith(".svg"):  # an SVG opened as a page must not run scripts or load outside files
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; img-src data:")
        super().end_headers()

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path not in ("/api/source", "/api/files"):
            return super().do_GET()
        if self.headers.get("Host") not in HOSTS:
            return self.send_error(403, "bad host")
        try:
            if url.path == "/api/files":
                data, kind = json.dumps(files()).encode(), "application/json"
            else:
                data, kind = source(parse_qs(url.query).get("path", [""])[0]), "text/plain; charset=utf-8"
        except (ValueError, OSError):
            return self.send_error(404)
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        route = {"/api/chat": chat, "/api/cards": save_card, "/api/diagram": diagram}.get(self.path)
        if not route:
            return self.send_error(404)
        if self.headers.get("Origin") not in ORIGINS:
            return self.send_error(403, "bad origin")
        try:
            res, code = route(json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))), 200
        except ValueError as e:  # includes JSONDecodeError
            res, code = {"error": str(e)}, 400
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            res, code = {"error": str(e)}, 500
        data = json.dumps(res).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    print(f"Open http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), partial(Handler, directory=WEB)).serve_forever()
