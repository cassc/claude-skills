---
name: telegram-repo-bot
description: Set up or change a Telegram bot that lets the user ask Claude Code about, or work on, their local repos from Telegram. One bot serves many repos, each with read or write access. Use when the user wants to "chat with my repo from Telegram", "add this repo to the telegram bot", change a repo's read/write mode, add or remove a bot user, or check/fix the bot service.
---

# Telegram repo bot

Files in this skill folder:
- `bot.py` — the bot (Python stdlib only). `python3 bot.py --check` tests config + token.
- `tg-claude-bot.service` — systemd user unit.

Config: `~/.config/tg-claude-bot/config.json` (chmod 600). The bot re-reads it on every message, so config edits need no restart.
```json
{
  "token": "123456:ABC...",
  "users": [412587349],
  "repos": {"my-repo": {"path": "/abs/path/to/repo", "mode": "read"}},
  "timeout": 1800
}
```
- `users`: numeric Telegram user ids (ints). Others are ignored.
- `mode`: `read` = read tools + git log/show/diff/status only. `write` = full access (bypassPermissions: edit, any command, commit, push).
- State (offset, current repo, Claude sessions): `~/.local/state/tg-claude-bot/state.json`.

## Add a repo (default action)
1. If config exists, read it. Only ask for what is missing.
2. First time only: ask for the bot token (from @BotFather `/newbot`) and the user's numeric id (from @userinfobot).
3. Ask read or write for the current repo. Name = folder name unless the user gives one.
4. Before the first `write` repo, warn once: anyone in `users` can then run any command on this machine as this user.
5. Write/merge the config, keep other repos, `chmod 600`. Use the absolute repo path.
6. First time only (confirm with the user first):
   ```
   mkdir -p ~/.config/systemd/user
   cp <this skill dir>/tg-claude-bot.service ~/.config/systemd/user/
   systemctl --user daemon-reload && systemctl --user enable --now tg-claude-bot
   ```
   Tell the user to run `loginctl enable-linger $USER` so it runs without a login.
7. Run `python3 <skill dir>/bot.py --check`. Tell the user to send `/repos` to the bot.

## Other changes
Edit the config: remove a repo, change `mode`, add or remove a user id. No restart needed.
After editing `bot.py`: `systemctl --user restart tg-claude-bot`.

## Troubleshooting
- Logs: `journalctl --user -u tg-claude-bot -n 50`.
- "ignored user N": add N to `users`.
- `claude failed`: check `claude` is on the unit's PATH and logged in.

## Bot commands
`/repos` (buttons to switch), `/repo <name>`, `/status`, `/new` (forget chat for the current repo), `/cancel`. Any other text goes to Claude in the current repo. Follow-up messages keep the chat until `/new`.
