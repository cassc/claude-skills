"""Serve the study cards and let Claude Code tutor/quiz you: python3 <this dir>/server.py"""
import json
import os
import re
import subprocess
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
MAX_SOURCE = 300_000  # bytes; larger files are not shown in the source popup
SESSION = re.compile(r"^[0-9a-f-]{36}$")
FIELDS = {"cards": ("t", "b"), "qa": ("q", "a")}
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
    mode, sid = body.get("mode", "quiz"), body.get("session_id")
    if mode not in PROMPTS or (sid and not SESSION.match(sid)):
        raise ValueError("bad mode or session id")
    msg = body.get("message", "").strip()
    if mode == "ask":
        msg = f"[Current card: {str(body.get('card', ''))[:3000]}]\n{msg}"
    elif not sid:
        msg = f"Quiz me on: {body.get('lesson', 'all lessons')}. {msg}".strip()
    return ask_claude(msg, mode, sid)


def save_card(body: dict) -> dict:
    lesson, typ, index, data = body.get("lesson"), body.get("type", ""), body.get("index"), body.get("data", {})
    keys = FIELDS.get(typ)
    if not (isinstance(lesson, str) and re.fullmatch(r"[\w-]{1,40}", lesson) and keys
            and (index is None or isinstance(index, int))
            and all(isinstance(data.get(k), str) and data[k].strip() for k in keys)):
        raise ValueError("bad card")
    with lock:
        items = json.loads(EXTRA.read_text()) if EXTRA.exists() else []
        items.append({"lesson": lesson, "type": typ, "index": index, "data": {k: data[k] for k in keys}})
        tmp = EXTRA.with_suffix(".tmp")
        tmp.write_text(json.dumps(items, indent=1, ensure_ascii=False) + "\n")
        tmp.replace(EXTRA)
    return {"ok": True}


def source(path: str) -> bytes:
    file = (ROOT / path).resolve()
    rel = file.relative_to(ROOT.resolve())  # ValueError if outside the repo
    if any(p.startswith(".") for p in rel.parts) or not file.is_file() or file.stat().st_size > MAX_SOURCE:
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

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path != "/api/source":
            return super().do_GET()
        if self.headers.get("Host") not in HOSTS:
            return self.send_error(403, "bad host")
        try:
            data = source(parse_qs(url.query).get("path", [""])[0])
        except (ValueError, OSError):
            return self.send_error(404)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        route = {"/api/chat": chat, "/api/cards": save_card}.get(self.path)
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
