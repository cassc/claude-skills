# telegram-repo-bot

A Claude Code skill and a small Telegram bot. From Telegram you can ask questions about your local repos or make changes to them. One bot serves many repos. Each repo is `read` or `write`.

## How it works

`bot.py` long-polls Telegram. Each message from an allowed user runs `claude -p` in the repo you picked. Follow-up messages resume the same Claude session, until you send `/new`.

- `read`: only Read, Glob, Grep, web search, and `git log/show/diff/status/blame/branch`. `.env` files are blocked, and no MCP servers load.
- `write`: full access (`bypassPermissions`). Claude can edit files, run commands, commit and push.

## Install

```sh
git clone https://github.com/cassc/claude-skills.git
ln -s "$PWD/claude-skills/skills/telegram-repo-bot" ~/.claude/skills/telegram-repo-bot
```

You need Python 3.8+ (standard library only) and a logged-in `claude` CLI.

## Set up

1. Create a bot with [@BotFather](https://t.me/BotFather) (`/newbot`) and copy the token.
2. Get your numeric user id from [@userinfobot](https://t.me/userinfobot).
3. Open Claude Code in a repo and run `/telegram-repo-bot`. Claude asks for the token, your user id and the mode. It writes the config and installs the systemd user service.
4. Run `loginctl enable-linger $USER` so the bot keeps running after you log out.
5. Send `/repos` to your bot.

Or do it by hand. Write `~/.config/tg-claude-bot/config.json` (`chmod 600`):

```json
{
  "token": "123456:ABC...",
  "users": [412587349],
  "repos": {
    "notes":    {"path": "/home/me/notes", "mode": "write"},
    "my-app":   {"path": "/home/me/projects/my-app", "mode": "read"}
  },
  "timeout": 1800
}
```

Then set up the service:

```sh
python3 ~/.claude/skills/telegram-repo-bot/bot.py --check
cp ~/.claude/skills/telegram-repo-bot/tg-claude-bot.service ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now tg-claude-bot
```

To add more repos later, run the skill in that repo or edit the config. The bot re-reads the config on every message, so no restart is needed.

## Use

| Command | What it does |
| --- | --- |
| `/repos` | List repos, tap one to switch |
| `/repo <name>` | Switch repo |
| `/status` | Current repo, mode, busy or idle |
| `/new` | Forget the chat for the current repo |
| `/compact [what to keep]` | Shorten the chat for the current repo, keep a summary |
| `/cancel` | Stop the running task and `/bg` tasks, clear the queue |
| `/bg <task>` | Run a task in parallel, in a copy of the chat. Other messages are not blocked |
| any other text | Sent to Claude in the current repo |
| a photo, file or album | Saved in `<repo>/telegram-resources/` and sent to Claude. The caption is the question |
| a voice note or audio | Transcribed (the bot replies "Heard: ..."); the text goes to Claude, and the answer also comes back as a voice note |
| (write mode) Claude makes a file | Claude saves it in `<repo>/telegram-resources/out/`; the bot sends it after the reply (audio, voice, video, photo or document) and deletes it |
| `/voice on\|off` | Voice replies to voice messages (default on) |

Messages sent while a task runs (or while the PC is off) are queued and go to Claude as one call; each answer replies to its own message. `/new`, `/repo`, `/fork`, `/restore` and `/compact` wait their turn in the queue, so the order stays.

**One topic per repo (optional).** In the @BotFather Mini App, open the bot's settings and turn on Threaded Mode (leave "users can create topics" off), then restart the bot. The bot makes one topic per repo in your private chat and keeps the ids in `state.json`. A message in a topic goes to that topic's repo, and the reply lands there, so each repo has its own history and `/repo` is not needed. Messages outside topics work as before. Each topic has its own queue, so repos run in parallel; `/cancel`, `/status`, `/new` and `/bg` in a topic act only on that topic. Voice jobs (speech to text, voice replies) still run one at a time, because they share one GPU.

Voice runs on local models in its own venv (the bot itself stays stdlib-only). `voice.py` is the client; it starts `voice_server.py` on demand, which runs Qwen3-ASR-1.7B (speech to text) and VoxCPM2 (text to audio) on the GPU and exits after 2 idle minutes so the GPU can sleep. They do not fit in 8 GB VRAM together, so the idle one waits in RAM and they swap in about 2 s; the timing aligner runs on the CPU. Install (several GB):
```
uv venv --python 3.12 ~/.local/share/tg-voice/venv
uv pip install --python ~/.local/share/tg-voice/venv/bin/python qwen-asr voxcpm
```
Models (about 6 GB) download on first use. If the GPU server fails, speech to text falls back to faster-whisper on the CPU (`transcribe.py`, venv `~/.local/share/tg-claude-bot/venv`: `faster-whisper 'av<16'`) and the text starts with "(CPU whisper)".

Config: `"pause_min"` (default 0.7 seconds) sets the shortest silence shown as `[pause 1.4s]`. `"asr_prompt"` lists words to expect (names, terms); set it at the top level, per repo, or both (they are joined). Transcripts reach Claude marked "may have errors". `"voice_limit"` (default 600) is the most characters spoken. `"whisper_model"` is for the CPU fallback (default `small`). Voice log: `~/.local/state/tg-voice.log`.

Logs: `journalctl --user -u tg-claude-bot -n 50`

## Why this instead of...

**The official Telegram plugin (`telegram@claude-plugins-official`)**
- The plugin connects a bot to *one* running Claude Code session (`claude --channels ...`). To use more repos, you need one bot token and one always-open session per repo.
- Here one bot serves all repos, and `/repos` switches between them.
- Read or write is set per repo in one config file. The plugin gets it from how you started each session.
- Nothing has to stay open. Each message starts `claude -p`, and a systemd service keeps the bot running. No Bun, no tmux.
- The plugin does more inside a chat: it can send files back, react and use groups. Pick the plugin if you need those.

**Claude Code Remote Control (the Claude app)**
- Remote Control drives a session you already started on your computer. It is good for following one live task.
- It works from the Claude app only. This bot works from Telegram, which you may already have open, and it is easy to use on a weak network.
- It has no per-repo read-only limit. Here a `read` repo cannot change anything, even if you ask it to.
- You don't need to start a session first. You message the bot and it works in the repo.

## Security

- Messages from ids not listed in `users` are ignored.
- The token is only in the config file (`chmod 600`), outside every repo.
- Files you send are saved in `<repo>/telegram-resources/` with a random name and mode `600` (not executable). The bot refuses to write if that folder is a symbolic link. Git ignores the folder through `.git/info/exclude`. The bot never deletes these files; clean the folder by hand. Files in `out/` are the exception: they are deleted once sent. Max 50 MB to send. Max 20 MB per file.
- `write` mode means anyone in `users` can run any command on this machine as you. Keep the list short, and keep your Telegram account safe (2FA).
