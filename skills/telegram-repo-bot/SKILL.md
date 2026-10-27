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
- `compact_warn` (optional, default 150000): when a chat's context passes this many tokens, answers end with a hint to `/compact` or `/new`.
- State (offset, current repo, Claude sessions, checkpoints): `~/.local/state/tg-claude-bot/state.json`.

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

## Voice messages (optional)
Voice notes, audio files and round videos are transcribed with faster-whisper; the bot replies "Heard: ..." and sends the text (plus any caption) to Claude. Whisper lives in its own venv so `bot.py` stays stdlib-only (confirm the install with the user first):
```
uv venv ~/.local/share/tg-claude-bot/venv
uv pip install --python ~/.local/share/tg-claude-bot/venv/bin/python faster-whisper 'av<16'
```
`av<16`: newer PyAV breaks faster-whisper 1.2.1. The model downloads on first use (`small` is about 500 MB). Config `"whisper_model"`: `small` (default), `base` (faster), `medium` (more accurate). `TG_CLAUDE_WHISPER` env sets another Python path. `transcribe.py` runs in that venv and marks silences as `[pause 1.4s]`; config `"pause_min"` (seconds, default 0.7) sets the shortest pause shown.

## Other changes
Edit the config: remove a repo, change `mode`, add or remove a user id. No restart needed.
After editing `bot.py`: `systemctl --user restart tg-claude-bot`.

## Troubleshooting
- Logs: `journalctl --user -u tg-claude-bot -n 50`.
- "ignored user N": add N to `users`.
- `claude failed`: check `claude` is on the unit's PATH and logged in.

## Bot commands
`/repos` (buttons to switch), `/repo <name>`, `/status`, `/new` (forget chat for the current repo), `/compact [what to keep]` (shorten the chat, keep a summary), `/cancel`, `/fork [name]`, `/restore <name or id>`, `/checkpoints [all]`, `/delete <name or id>`, `/ask <question>`. Any other text goes to Claude in the current repo. Photos, files and albums are saved in `<repo>/telegram-resources/` (mode 600, ignored by git) and Claude gets their paths. Voice and audio are also transcribed (above). Follow-up messages keep the chat until `/new`. Messages sent while a task runs are queued and run in order; `/cancel` also clears the queue.
`/fork [name]` saves the current chat as a checkpoint (id = first 6 chars of the session id; no name = first words of the last question) and the next message runs in a copy (`--fork-session`). `/restore` goes back to a checkpoint; chatting after it also runs in a copy, so a checkpoint never changes and can be restored again. `/checkpoints` lists the current repo's (`all`: every repo; newest 30); tapping one sends a reply quoting the message just before the `/fork` (tap the quote to jump there) with a Restore button; restoring one from another repo switches to it. Claude Code deletes session files after `cleanupPeriodDays` (default 30) in `~/.claude/settings.json`; those checkpoints are hidden and `/restore` says expired. Raise it to keep checkpoints longer.
`/ask` is a side question: a fresh Claude run in the current repo, always read-only (even in a `write` repo), with no chat history, and the answer is not kept in the chat. It runs at once, even while a task runs, and replies to the `/ask` message; `/cancel` does not stop it. Unlike Claude Code's `/btw`, it does not see the chat; to ask with the chat as context, use `/fork`.
