#!/usr/bin/env python3
"""Telegram bot that sends your messages to Claude Code in one of your repos.
Config (~/.config/tg-claude-bot/config.json) is re-read on every update, so edits need no restart.
Only users listed in config "users" are served. `bot.py --check` tests the config and token."""
import json
import os
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CONF = Path(os.environ.get("TG_CLAUDE_CONFIG", "~/.config/tg-claude-bot/config.json")).expanduser()
STATE = Path(os.environ.get("TG_CLAUDE_STATE", "~/.local/state/tg-claude-bot/state.json")).expanduser()

# IPv6 to Telegram can hang on some networks. Use IPv4 when there is one.
_gai = socket.getaddrinfo
socket.getaddrinfo = lambda *a, **k: [r for r in _gai(*a, **k) if r[0] == socket.AF_INET] or _gai(*a, **k)

PROMPTS = {
    "read": "You answer the repo owner through Telegram. This is read-only: do not try to change files. "
            "Reply in short plain text, no Markdown tables.",
    "write": "You work for the repo owner through Telegram. You may edit files, run commands and commit. "
             "Say briefly what you changed. Reply in short plain text, no Markdown tables.",
}
READ_TOOLS = ["Read", "Glob", "Grep", "WebSearch", "WebFetch", "Bash(ls:*)",
              *(f"Bash(git {c}:*)" for c in ("log", "show", "diff", "status", "blame", "branch"))]
COMMANDS = {"repos": "List repos and switch", "repo": "Switch repo: /repo <name>", "status": "Current repo and mode",
            "new": "Forget the chat for the current repo", "cancel": "Stop the running task"}

state = json.loads(STATE.read_text()) if STATE.exists() else {"offset": 0, "repo": {}, "session": {}}
state_lock = threading.Lock()
running = {}  # chat id -> Popen (None while starting)


def conf():
    return json.loads(CONF.read_text())


def save():
    with state_lock:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state))


def api(method, http_timeout=20, **data):
    data = {k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in data.items()}
    req = urllib.request.Request(f"https://api.telegram.org/bot{conf()['token']}/{method}",
                                 urllib.parse.urlencode(data).encode())
    try:
        with urllib.request.urlopen(req, timeout=http_timeout) as r:
            return json.load(r)["result"]
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"telegram {e.code}: {json.load(e).get('description')}") from None
    except OSError as e:
        raise RuntimeError(f"telegram request failed: {type(e).__name__}") from None  # hide token in URL


def send(chat, text, reply_to=None, buttons=None):
    """Send text in 4000-char parts; buttons go on the last part. Returns its message_id."""
    parts = [text[i:i + 4000] for i in range(0, len(text), 4000)] or ["(empty)"]
    for i, part in enumerate(parts):
        extra = {"reply_markup": {"inline_keyboard": buttons}} if buttons and i == len(parts) - 1 else {}
        if reply_to:
            extra["reply_to_message_id"] = reply_to
        mid = api("sendMessage", chat_id=chat, text=part, **extra)["message_id"]
    return mid


def current(chat, c):
    """The chat's repo name, or the only repo if there is one. None if not set."""
    name = state["repo"].get(str(chat))
    if name not in c["repos"]:
        name = next(iter(c["repos"])) if len(c["repos"]) == 1 else None
    return name


def claude_cmd(repo, session):
    mode = "write" if repo.get("mode") == "write" else "read"
    cmd = ["claude", "-p", "--output-format", "json", "--append-system-prompt", PROMPTS[mode]]
    if mode == "write":
        cmd += ["--permission-mode", "bypassPermissions"]
    else:  # dontAsk: any tool not allowed below is denied
        cmd += ["--permission-mode", "dontAsk", "--strict-mcp-config",
                "--tools", "Read,Glob,Grep,Bash,WebSearch,WebFetch", "--allowedTools", *READ_TOOLS,
                "--disallowedTools", "Read(**/.env)", "Read(**/.env.*)"]
    if session:
        cmd += ["--resume", session]
    return cmd


def ask(chat, name, repo, text, reply_to):
    """Runs in a thread, so commands like /cancel keep working."""
    key = f"{chat}:{name}"
    t = time.time()
    try:
        mid = send(chat, f"[{name}] Working...", reply_to)
        p = subprocess.Popen(claude_cmd(repo, state["session"].get(key)), cwd=Path(repo["path"]).expanduser(),
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        running[chat] = p
        try:
            out, err = p.communicate(text, timeout=conf().get("timeout", 1800))
        except subprocess.TimeoutExpired:
            p.kill()
            p.communicate()
            out, err = None, "timed out"
        if p.returncode < 0:
            ans = "Stopped." if out is not None else "Timed out."
        else:
            try:
                ans = json.loads(out).get("result") or "(no answer)"
                state["session"][key] = json.loads(out)["session_id"]
            except (ValueError, KeyError):
                state["session"].pop(key, None)  # e.g. the saved session is gone; next message starts fresh
                ans = f"claude failed ({p.returncode}): {(err or out)[-300:]}"
            save()
        print(f"{name}: {len(text)} chars asked, {len(ans)} answered ({time.time() - t:.0f}s)", flush=True)
        full = f"[{name}]\n{ans}"
        api("editMessageText", chat_id=chat, message_id=mid, text=full[:4000])
        if full[4000:]:
            send(chat, full[4000:])
    except Exception as e:
        traceback.print_exc()
        try:
            send(chat, f"Failed: {e}"[:4000])
        except Exception:
            pass
    finally:
        running.pop(chat, None)


def repo_buttons(c, cur):
    return [[{"text": f"{'> ' if n == cur else ''}{n} ({r.get('mode', 'read')})", "callback_data": f"repo:{n}"}]
            for n, r in c["repos"].items()]


def switch(chat, c, name):
    if name not in c["repos"]:
        return f"No repo '{name}'. Send /repos."
    state["repo"][str(chat)] = name
    save()
    return f"Now on {name} ({c['repos'][name].get('mode', 'read')})."


def on_message(m):
    chat, c = m["chat"]["id"], conf()
    if m.get("from", {}).get("id") not in c["users"]:
        print(f"ignored user {m.get('from', {}).get('id')}", flush=True)
        return
    text = (m.get("text") or m.get("caption") or "").strip()
    cmd, _, arg = text.partition(" ")
    cmd = cmd.split("@")[0].lower()
    name = current(chat, c)
    if cmd == "/repos":
        send(chat, "Pick a repo:" if c["repos"] else "No repos in config.", buttons=repo_buttons(c, name))
    elif cmd == "/repo":
        send(chat, switch(chat, c, arg.strip()) if arg.strip() else "Use: /repo <name>")
    elif cmd == "/status":
        mode = c["repos"][name].get("mode", "read") if name else "-"
        send(chat, f"Repo: {name or 'none'} ({mode}). {'Busy.' if chat in running else 'Idle.'}")
    elif cmd == "/new":
        state["session"].pop(f"{chat}:{name}", None)
        save()
        send(chat, f"New chat for {name}.")
    elif cmd == "/cancel":
        p = running.get(chat)
        if p:
            p.kill()
        send(chat, "Stopping." if p else "Nothing is running.")
    elif cmd.startswith("/") and cmd != "/start" or not text:
        send(chat, "Commands:\n" + "\n".join(f"/{k} - {v}" for k, v in COMMANDS.items())
             + "\nAny other text goes to Claude.")
    elif chat in running:
        send(chat, "Still working. Send /cancel to stop it.", m["message_id"])
    elif not name:
        send(chat, "Pick a repo first:", buttons=repo_buttons(c, name))
    else:
        running[chat] = None
        if cmd == "/start":
            text = "Say hi and tell me in one line what this repo is."
        threading.Thread(target=ask, args=(chat, name, c["repos"][name], text, m["message_id"]), daemon=True).start()


def on_callback(cb):
    c = conf()
    if cb["from"]["id"] not in c["users"]:
        return
    act, _, name = cb.get("data", "").partition(":")
    msg = switch(cb["message"]["chat"]["id"], c, name) if act == "repo" else "Unknown action"
    api("answerCallbackQuery", callback_query_id=cb["id"], text=msg[:190])
    api("editMessageText", chat_id=cb["message"]["chat"]["id"], message_id=cb["message"]["message_id"], text=msg)


def main():
    if "--check" in sys.argv:
        c = conf()
        print(f"bot @{api('getMe')['username']}, users {c['users']}")
        for n, r in c["repos"].items():
            ok = Path(r["path"]).expanduser().is_dir()
            print(f"  {n}: {r['path']} ({r.get('mode', 'read')}){'' if ok else '  MISSING'}")
        return
    api("setMyCommands", commands=[{"command": k, "description": v} for k, v in COMMANDS.items()])
    print("bot started", flush=True)
    while True:
        try:
            for u in api("getUpdates", http_timeout=70, timeout=50, offset=state["offset"],
                         allowed_updates=["message", "callback_query"]):
                state["offset"] = u["update_id"] + 1
                save()
                if cb := u.get("callback_query"):
                    on_callback(cb)
                elif m := u.get("message"):
                    on_message(m)
        except Exception:
            traceback.print_exc()
            time.sleep(10)


if __name__ == "__main__":
    main()
