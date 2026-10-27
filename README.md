# claude-skills

My Claude Code skills and agents.

## Install

As a plugin (skills are named `cassc-skills:<skill>`):

```
/plugin marketplace add cassc/claude-skills
/plugin install cassc-skills@cassc-skills
```

Or with the [skills](https://skills.sh) CLI (skills only, no agents):

```sh
npx skills add cassc/claude-skills
```

Or link one skill by hand:

```sh
git clone https://github.com/cassc/claude-skills.git
ln -s "$PWD/claude-skills/skills/<skill>" ~/.claude/skills/<skill>
```

## Skills

| Skill | What it does |
|---|---|
| `adversarial-cv-review` | Builds the case against a CV, like a strict hiring manager |
| `building-study-cards-from-repos` | Turns a repo into study cards, a quiz, and a Claude tutor chat |
| `chatting-with-repos` | Web page to chat with Claude Code about a repo (read-only), with phone login |
| `play-prod-access` | Drafts answers for the Google Play production access form |
| `telegram-repo-bot` | Telegram bot that runs Claude Code in your local repos. One bot serves many repos, and each repo has its own read or write mode |

## Agents

| Agent | What it does |
|---|---|
| `adversarial-code-review` | Hunts for bugs instead of approving code |
| `commit-all` | Stages all changes, writes one commit from the diff, pushes |
| `play-release-notes` | Writes Google Play "What's new" text from git history |

## Warnings

### `telegram-repo-bot`

- **It must live at `~/.claude/skills/telegram-repo-bot`** (see its README). The systemd service runs it from that path.
- **`write` mode gives a shell to your users.** Anyone in its user list can run any command on your machine as you.
- **Allow only one user id: your own.** Set `"users": [<your id>]`. Every extra id gets the same full access.
- **Anyone who takes over your Telegram account owns your machine.** Turn on Telegram's two-step password (Settings > Privacy and Security).

Suggested setup for the most security:

- In @BotFather, run `/setjoingroups` and choose **Disable**. Then nobody can add the bot to a group. The bot does not check the chat type: in a group, everyone sees its replies, including code and file contents.
- Never add the bot to a channel or make it a channel admin.
- Use `read` mode by default. Use `write` only for the repos where you need it.
- Don't use `write` mode on repos that hold untrusted text, like web pages or data you crawled. That text can tell Claude to run commands (prompt injection).
- Keep `~/.config/tg-claude-bot/config.json` at mode `600`. The token lets anyone read what you send the bot. If it leaks, run `/revoke` in @BotFather.

### `building-study-cards-from-repos`

- **It runs a local server that calls `claude -p`.** Use it only on repos you trust.

### `chatting-with-repos` and `building-study-cards-from-repos`

Both put Claude Code on a web page. Read this before you serve one beyond `127.0.0.1`.

- **Secret files can leak.** Claude is blocked only from `.env` and `.env.*`. It can still read any other file in the repo, including git-ignored ones (`credentials.json`, `*.pem`, `id_rsa`, `secrets.yaml`, ...). Anyone who is signed in can ask for them. Remove secrets from the repo, or serve a clean copy.
- **Every question uses your Claude account.** It runs `claude` as you and uses your quota. Giving other people access to your Claude subscription this way may break Anthropic's terms. Keep it for yourself.
- **No login without `PUBLIC_URL`.** On `127.0.0.1` there is no login. Behind nginx, a tunnel or any proxy, you must set `PUBLIC_URL`, or anyone who reaches the proxy gets in.
- **Prompt injection.** Text in the repo can steer Claude's answers. Claude has read-only tools, but do not trust replies about repos you did not write.
- **Use at your own risk.** No security audit was done. Keep the pair link and phone safe: the phone is the key that signs in other browsers.

## License

MIT
