---
name: chatting-with-repos
description: Use when the user wants a web page (local, on the phone, or behind nginx/a tunnel) to chat with Claude Code about a repo, ask questions about its code or data, without study cards or a quiz.
---

# Chatting with a repo

## Overview
A small web page: a chat where Claude Code runs in the repo, read-only
(Read/Grep/Glob, no `.env`), and answers questions. Replies show code
references as links to a file popup. Same phone login as
`building-study-cards-from-repos`. No cards, no quiz, no diagrams.

## Setup
1. Copy `template/` (next to this file) into the repo as `chat/`. The
   server treats the folder's parent as the repo root.
2. Replace `{{TITLE}}` (`index.html`, `prompt.md`) and `{{SOURCES}}`
   (`prompt.md`: the doc and code paths Claude should read first).
3. Optional: to serve a page from the repo root (a dashboard), add its file
   names to `ROOT_FILES` in `server.py` (e.g. `{"dashboard.html",
   "data.json"}`) and a link in the `index.html` header. Only list exact
   files, never the root.
4. Ask the user before adding `chat/` to `.gitignore` or committing it.
5. Run `python3 chat/server.py`, open http://127.0.0.1:8765. `PORT=8766`
   for a second copy.

Login: any `HOST` other than 127.0.0.1, or a `PUBLIC_URL`, turns it on.
`HOST=0.0.0.0` for the local network (HTTPS, self-signed). Details:
`phone-login.md`.

## Behind nginx on a server
1. User systemd service on this PC: `WorkingDirectory=<repo>`,
   `ExecStart=/usr/bin/python3 chat/server.py`, `Environment=PORT=<p>`,
   `Environment=PUBLIC_URL=https://<name>`, `Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin`
   (so `claude` is found), `Restart=always`.
2. Reverse tunnel service: `ssh -N -o BatchMode=yes -o ExitOnForwardFailure=yes
   -o ServerAliveInterval=30 -R 127.0.0.1:<1p>:127.0.0.1:<p> <server>`.
3. nginx: port 80 redirect block, and a 443 block with
   `proxy_pass http://127.0.0.1:<1p>`, `proxy_set_header Host $host`,
   `proxy_read_timeout 300s`, and an Origin fix. The app checks
   `Origin == http://<Host>`, so add a `map $http_origin $x_origin`
   turning `https://<name>` into `http://<name>` and
   `proxy_set_header Origin $x_origin`.
4. Pair a phone: the newest pair link is in
   `~/.cache/repo-chat/pair-<PORT>.txt` (and the journal). It works once,
   for 10 min. For a new one with no restart:
   `systemctl --user kill --kill-whom=main -s USR1 <service>` (`main`, so
   the `claude` children do not get the signal). To send it to someone:
   `qrencode -s 8 -o ~/pair.png "$(cat ~/.cache/repo-chat/pair-<PORT>.txt)"`
   and send the image. Never send the link through a chat app (the link
   preview uses it).

## Verify
- `node --check` each `.js`; the server starts.
- Before login: `/` is the login page; `/api/files` and any `ROOT_FILES`
  give 403.
- After login: ask one question, the reply comes back with a clickable
  `path:line`; reload while waiting, the reply still arrives; History
  opens the old chat; Export all downloads a `.md`; Files shows the tree.

## Common mistakes
| Mistake | Fix |
|---|---|
| Serving the repo root for a dashboard | List exact files in `ROOT_FILES` |
| `PUBLIC_URL` not set behind a proxy | Anyone who reaches it gets in with no login |
| No Origin map in nginx | Every POST fails with "bad origin" |
| Old server still running after editing `prompt.md` | The prompt loads at start: restart |
| `claude` not found under systemd | Set `PATH` in the service |
