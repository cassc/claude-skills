"""Chat with Claude Code about this repo (read-only): python3 <this dir>/server.py"""
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import signal
import socket
import ssl
import subprocess
import threading
import time
from functools import partial
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

HOST, PORT = os.environ.get("HOST", "127.0.0.1"), int(os.environ.get("PORT", 8765))
CERT, KEY = os.environ.get("CERT"), os.environ.get("KEY")  # your own cert; KEY is not needed if CERT holds the key
# PUBLIC_URL: the address a proxy or tunnel serves this at (https://chat.example.com). It turns the login on;
# the proxy does TLS, and only requests from 127.0.0.1 may say the real client IP and scheme.
PUBLIC = os.environ.get("PUBLIC_URL", "").rstrip("/")
LOCAL = HOST in ("127.0.0.1", "localhost") and not PUBLIC
# On the network, HTTPS by default with a self-signed cert unless CERT is given; TLS=0 turns it off.
TLS = bool(CERT) or os.environ.get("TLS", "" if LOCAL or PUBLIC else "1") not in ("", "0")
SCHEME = "https" if TLS else "http"
SECURE = TLS or PUBLIC.startswith("https://")  # cookies only over HTTPS


def saved_secret() -> str:
    """The key that signs login cookies. It lives outside the repo; delete the file to sign everyone out."""
    file = Path.home() / ".cache" / "repo-chat" / "secret"
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
PAIR_FILE = Path.home() / ".cache" / "repo-chat" / f"pair-{PORT}.txt"  # the newest pair link, for scripts
PAIR_TTL, LOGIN_TTL, MAX_LOGINS = 600, 120, 20  # seconds a pair link / a sign-in QR works; sign-ins waiting at once
WEB = Path(__file__).resolve().parent
ROOT = WEB.parent
PROMPT = (WEB / "prompt.md").read_text()
ORIGINS = {f"{SCHEME}://{HOST}:{PORT}", f"{SCHEME}://localhost:{PORT}"}
HOSTS = {o.split("//")[1] for o in ORIGINS}
ROOT_FILES: set[str] = set()  # repo-root files served at / (e.g. "dashboard.html"); never the whole root (.env)
MAX_SOURCE = 1_000_000  # bytes; larger files are not shown in the source popup
MAX_FILES = 5000  # cap for the file list when the folder is not a git repo
SESSION = re.compile(r"^[0-9a-f-]{36}$")
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
        PAIR_FILE.write_text(link + "\n")
        PAIR_FILE.chmod(0o600)
    try:
        subprocess.run(["qrencode", "-t", "ansiutf8", link], check=True)
    except (OSError, subprocess.CalledProcessError):
        pass  # no qrencode: the link alone
    print(f"Pair your phone: scan the QR or open {link}\n(works once, for {PAIR_TTL // 60} min; press Enter or send SIGUSR1 for a new one)", flush=True)


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


def ask_claude(message: str, session_id: str | None) -> dict:
    cmd = ["claude", "-p", "--output-format", "json", "--append-system-prompt", PROMPT,
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
    sid, job_id = body.get("session_id"), body.get("id")
    if (sid and not SESSION.match(sid)) or not (isinstance(job_id, str) and SESSION.match(job_id)):
        raise ValueError("bad session id or message id")
    with lock:
        job = jobs.get(job_id)
        if first := job is None:
            job = jobs[job_id] = {"done": threading.Event()}
            for old in list(jobs)[:-KEEP]:
                del jobs[old]
    if first:  # the same id again (a page refresh) waits for this run and gets the same result
        try:
            job["res"] = ask_claude(str(body.get("message", "")).strip(), sid)
        except Exception as e:
            job["err"] = e
        job["done"].set()
    job["done"].wait()
    if "err" in job:
        raise job["err"]
    return job["res"]


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
        if str(rel) in ROOT_FILES:
            return str(ROOT / rel)
        return super().translate_path(path)

    def end_headers(self):
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
        route = {"/api/chat": chat, "/api/login/start": login_start,
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
    file = Path.home() / ".cache" / "repo-chat" / f"{name}.pem"
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
        # systemctl --user kill -s USR1 <service>: a new pair link with no restart (a service has no Enter)
        signal.signal(signal.SIGUSR1, lambda *_: threading.Thread(target=new_pair, args=(base,), daemon=True).start())
    server.serve_forever()
