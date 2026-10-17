"""Serve the study cards and let Claude Code tutor/quiz you: python3 <this dir>/server.py"""
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import time
from functools import partial
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

HOST, PORT = os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", 8765))
CERT, KEY = os.environ.get("CERT"), os.environ.get("KEY")  # your own cert; KEY is not needed if CERT holds the key
# PUBLIC_URL: the address a proxy or tunnel serves this at (https://cards.example.com). It turns the login on;
# the proxy does TLS, and only requests from 127.0.0.1 may say the real client IP and scheme.
PUBLIC = os.environ.get("PUBLIC_URL", "").rstrip("/")
LOCAL = HOST in ("127.0.0.1", "localhost") and not PUBLIC
# On the network, HTTPS by default with a self-signed cert unless CERT is given; TLS=0 turns it off.
TLS = bool(CERT) or os.environ.get("TLS", "" if LOCAL or PUBLIC else "1") not in ("", "0")
SCHEME = "https" if TLS else "http"
SECURE = TLS or PUBLIC.startswith("https://")  # cookies only over HTTPS


def saved_secret() -> str:
    """The key that signs login cookies. It lives outside the repo; delete the file to sign everyone out."""
    file = Path.home() / ".cache" / "study-cards" / "secret"
    if not file.exists():
        file.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(fd, secrets.token_urlsafe(32).encode())
        os.close(fd)
    return file.read_text().strip()


# Any other HOST (0.0.0.0 for the local network) or a PUBLIC_URL needs a login: a phone pairs by the QR the
# server prints, then signs in other browsers by scanning their QR. TOKEN only signs the cookies; it is never sent.
TOKEN = "" if LOCAL else os.environ.get("TOKEN") or saved_secret()
LIFE = {"p": float(os.environ.get("PHONE_DAYS", 365)) * 86400, "d": float(os.environ.get("LOGIN_HOURS", 24)) * 3600}
PAIR_TTL, LOGIN_TTL, MAX_LOGINS = 600, 120, 20  # seconds a pair link / a sign-in QR works; sign-ins waiting at once
WEB = Path(__file__).resolve().parent
ROOT = WEB.parent
EXTRA = WEB / "extra-cards.json"
PROMPTS = {m: (WEB / f"{m}_prompt.md").read_text() for m in ("ask", "quiz")}
ORIGINS = {f"{SCHEME}://{HOST}:{PORT}", f"{SCHEME}://localhost:{PORT}"}
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
pairing = {"code": "", "exp": 0.0}
logins: dict[str, dict] = {}  # wait id (only the browser that signs in knows it) -> {code, exp, who, ok}
lock = threading.Lock()


def sign(text: str) -> str:
    return hmac.new(TOKEN.encode(), text.encode(), hashlib.sha256).hexdigest()


def make_cookie(role: str) -> str:
    """role p = phone (may sign in other browsers), d = desktop."""
    age = int(LIFE[role])
    text = f"{role}.{int(time.time()) + age}"
    return f"k={text}.{sign(text)}; Path=/; HttpOnly; SameSite=Lax; Max-Age={age}" + ("; Secure" if SECURE else "")


def same(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def new_pair(base: str):
    with lock:
        pairing.update(code=secrets.token_urlsafe(16), exp=time.time() + PAIR_TTL)
        link = f"{base}/pair?c={pairing['code']}"
    try:
        subprocess.run(["qrencode", "-t", "ansiutf8", link], check=True)
    except (OSError, subprocess.CalledProcessError):
        pass  # no qrencode: the link alone
    print(f"Pair your phone: scan the QR or open {link}\n(works once, for {PAIR_TTL // 60} min; press Enter for a new one)", flush=True)


def pair_on_enter(base: str):
    try:
        while True:
            input()
            new_pair(base)
    except EOFError:  # no terminal, e.g. a service
        pass


def use_pair(code: str) -> bool:
    with lock:
        ok = bool(pairing["code"]) and same(code, pairing["code"]) and pairing["exp"] > time.time()
        if ok:
            pairing["code"] = ""
    return ok


def login_start(body: dict) -> dict:
    now = time.time()
    with lock:
        for w in [w for w, x in logins.items() if x["exp"] < now]:
            del logins[w]
        if len(logins) >= MAX_LOGINS:
            raise ValueError("too many sign-ins waiting; try again in 2 minutes")
        wait, code = secrets.token_urlsafe(24), secrets.token_urlsafe(12)
        logins[wait] = {"code": code, "exp": now + LOGIN_TTL, "who": body["who"], "ok": False}
    return {"wait": wait, "code": code}


def login_approve(body: dict) -> dict:
    """The phone sends {code} to see who asks, then {code, allow: true/false}."""
    code, allow = body.get("code"), body.get("allow")
    if not isinstance(code, str):
        raise ValueError("bad code")
    with lock:
        wait = next((w for w, x in logins.items() if same(code, x["code"]) and x["exp"] > time.time() and not x["ok"]), None)
        if not wait:
            raise ValueError("this code is used or expired")
        x = logins[wait]
        if allow is True:
            x.update(ok=True, exp=time.time() + 30)  # time for the browser's next poll
        elif allow is False:
            del logins[wait]
    return {"who": x["who"]}


def login_poll(body: dict) -> dict:
    wait = body.get("wait")
    with lock:
        if not isinstance(wait, str) or not (x := logins.get(wait)) or x["exp"] < time.time():
            return {"state": "expired"}
        if x["ok"]:
            del logins[wait]
            return {"state": "ok"}
    return {"state": "wait"}


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
        # / is the login page or the app, by cookie: never reuse it. private: a proxy (Cloudflare) must not share files.
        page = self.path.split("?")[0]
        self.send_header("Cache-Control", "no-store" if page.endswith(("/", ".html")) else "private, no-cache")
        super().end_headers()

    def role(self) -> str:
        """p (phone), d (desktop), or "" (not signed in). With no login needed, everyone counts as a phone."""
        if not TOKEN:
            return "p"
        cookie = SimpleCookie(self.headers.get("Cookie", "")).get("k")
        role, _, rest = (cookie.value if cookie else "").partition(".")
        exp, _, sig = rest.partition(".")
        ok = role in LIFE and exp.isdigit() and int(exp) > time.time() and same(sig, sign(f"{role}.{exp}"))
        return role if ok else ""

    def client_ip(self) -> str:
        ip = self.client_address[0]
        if PUBLIC and ip in ("127.0.0.1", "::1"):  # the proxy: trust the address it passes on
            fwd = self.headers.get("CF-Connecting-IP") or self.headers.get("X-Forwarded-For", "").split(",")[0]
            ip = fwd.strip()[:64] or ip
        return ip

    def do_HEAD(self):
        return super().do_HEAD() if self.role() else self.send_error(403)

    def do_GET(self):
        url = urlsplit(self.path)
        if TOKEN and url.path == "/pair":  # the QR the server printed
            if not use_pair(parse_qs(url.query).get("c", [""])[0]):
                return self.send_error(403, "this pair link is used or expired: press Enter where the server runs")
            self.send_response(303)
            self.send_header("Location", "/")
            self.send_header("Set-Cookie", make_cookie("p"))
            self.send_header("Content-Length", "0")
            return self.end_headers()
        role = self.role()
        if not role and url.path in ("/", "/login.html", "/approve.html", "/style.css"):  # approve.html says when a browser is not paired
            self.path = "/login.html" if url.path == "/" else url.path
            return super().do_GET()
        if not role:
            return self.send_error(403, "sign in: scan the QR on / with your paired phone")
        if url.path not in ("/api/source", "/api/files"):
            return super().do_GET()
        if not TOKEN and self.headers.get("Host") not in HOSTS:
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
        route = {"/api/chat": chat, "/api/cards": save_card, "/api/diagram": diagram, "/api/login/start": login_start,
                 "/api/login/poll": login_poll, "/api/login/approve": login_approve}.get(self.path)
        if not route:
            return self.send_error(404)
        role = self.role()
        if route not in (login_start, login_poll) and (not role or (route is login_approve and role != "p")):
            return self.send_error(403, "sign in: scan the QR on / with your paired phone")
        if self.headers.get("Origin") not in ({f"{SCHEME}://{self.headers.get('Host')}", PUBLIC} - {""} if TOKEN else ORIGINS):
            return self.send_error(403, "bad origin")
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            if not isinstance(body, dict):
                raise ValueError("bad body")
            if route is login_start:
                body["who"] = f"{self.client_ip()}, {self.headers.get('User-Agent', '?')[:200]}"
            res, code = route(body), 200
        except ValueError as e:  # includes JSONDecodeError
            res, code = {"error": str(e)}, 400
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            res, code = {"error": str(e)}, 500
        data = json.dumps(res).encode()
        self.send_response(code)
        if route is login_poll and res.get("state") == "ok":
            self.send_header("Set-Cookie", make_cookie("d"))
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def lan_ip() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("10.255.255.255", 1))  # sends nothing; only picks the outgoing interface
        return s.getsockname()[0]


def self_signed(name: str) -> str:
    """Make a cert for this address, or reuse it. It lives outside the repo, so the key cannot be committed or served."""
    file = Path.home() / ".cache" / "study-cards" / f"{name}.pem"
    if not file.exists() or time.time() - file.stat().st_mtime > 300 * 86400:
        file.parent.mkdir(parents=True, exist_ok=True)
        try:
            kind = "IP" if ipaddress.ip_address(name) else ""
        except ValueError:
            kind = "DNS"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "365", "-subj", f"/CN={name}",
                        "-addext", f"subjectAltName={kind}:{name},DNS:localhost,IP:127.0.0.1", "-keyout", file, "-out", file],
                       check=True, capture_output=True)
    return str(file)


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), partial(Handler, directory=WEB))
    name = lan_ip() if HOST in ("0.0.0.0", "") else HOST
    if TLS:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(CERT or self_signed(name), KEY if CERT else None)
        # handshake in the request thread, so one slow client cannot block the others
        server.socket = ctx.wrap_socket(server.socket, server_side=True, do_handshake_on_connect=False)
    base = PUBLIC or f"{SCHEME}://{name}:{PORT}"
    print(f"Open {base}", flush=True)
    if TOKEN:
        new_pair(base)
        threading.Thread(target=pair_on_enter, args=(base,), daemon=True).start()
    server.serve_forever()
