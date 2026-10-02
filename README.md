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
| `adversarial-code-review` | Hunts for bugs instead of approving code |
| `adversarial-cv-review` | Builds the case against a CV, like a strict hiring manager |
| `building-study-cards-from-repos` | Turns a repo into study cards, a quiz, and a Claude tutor chat |
| `infra-diagnosis-context-check` | Infra debugging with competing ideas and a check for each |
| `play-prod-access` | Drafts answers for the Google Play production access form |
| `telegram-repo-bot` | Telegram bot that runs Claude Code in your local repos |

## Agents

| Agent | What it does |
|---|---|
| `commit-all` | Stages all changes, writes one commit from the diff, pushes |
| `play-release-notes` | Writes Google Play "What's new" text from git history |

## Notes

- `telegram-repo-bot` expects to live at `~/.claude/skills/telegram-repo-bot` (see its README). In `write` mode, anyone in its user list can run commands on your machine.
- `building-study-cards-from-repos` runs a local server that calls `claude -p`. Use it only on repos you trust.

## License

MIT
